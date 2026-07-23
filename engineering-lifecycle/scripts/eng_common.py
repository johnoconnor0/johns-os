#!/usr/bin/env python3
"""Shared helpers for the Engineering Lifecycle plugin scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(".project") / ".engineering"

# Directories the fallback scan never descends into. Pruned during traversal —
# filtering them out of the results afterwards still pays the full walk cost.
# These are the trees `git ls-files` would omit anyway (VCS internals, vendored
# dependencies, build output, caches), so pruning keeps the fallback closer to
# the git path it stands in for.
SCAN_PRUNE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".project",
        "node_modules",
        "vendor",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cache",
        "dist",
        "build",
        "target",
        "coverage",
        ".next",
        ".turbo",
        ".gradle",
    }
)
SCAN_MAX_FILES = 20_000
SCAN_MAX_DEPTH = 12

REQUIRED_FRONT_MATTER = [
    "initiative_id",
    "skill",
    "created_at",
    "status",
    "confidence",
    "source_artifacts",
]


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            return candidate
        if (candidate / ".claude-plugin" / "plugin.json").exists():
            return candidate
    return cur


def engineering_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / WORKSPACE


def workspace_exists(root: Path | None = None) -> bool:
    """True once the Engineering Lifecycle workspace exists for this repo.

    The workspace is opt-in per repo: it is created only by explicit user action
    (the /project-init command, ``eng-life init``, or a lifecycle skill writing its
    first artifact) — never by automatic session/post-tool/stop hooks. Until it
    exists, those hooks stay dormant and must not create it. Anchored to the repo
    root via ``engineering_root`` so a hook firing from a subfolder never drops a
    stray ``.project`` in that subfolder.
    """
    return engineering_root(root).exists()


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def emit_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, sort_keys=True) + "\n")


def git(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or repo_root()),
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def is_scannable_root(root: Path) -> bool:
    """True when `root` plausibly holds a single project's sources.

    ``repo_root`` falls back to the cwd when it finds no ``.git`` or plugin
    manifest above it, so outside a repo this can be handed a home directory, a
    filesystem root, or an agent config tree. ``~/.claude`` in particular
    vendors plugin caches and one git clone per installed marketplace — walking
    it costs hundreds of thousands of files and yields nothing a stack detector
    or context pack can use. Refuse those roots instead of scanning them.
    """
    if root.parent == root:  # filesystem or drive root
        return False
    try:
        if root == Path.home().resolve():
            return False
    except (OSError, RuntimeError):  # home undefined in some sandboxes
        pass
    return ".claude" not in root.parts


def scan_files(
    root: Path,
    max_files: int = SCAN_MAX_FILES,
    max_depth: int = SCAN_MAX_DEPTH,
) -> list[Path]:
    """Bounded, pruned stand-in for ``git ls-files`` when `root` is not a repo.

    Bounded in three independent ways — refused roots, pruned directories, and
    hard depth/file caps — so a mis-resolved root degrades to a partial listing
    rather than an unbounded walk. Truncation is silent by design: every caller
    treats the listing as best-effort evidence, and a hook is not a place to
    emit diagnostics.
    """
    root = root.resolve()
    if not is_scannable_root(root):
        return []
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        relative = Path(dirpath).relative_to(root)
        if len(relative.parts) >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = sorted(name for name in dirnames if name not in SCAN_PRUNE_DIRS)
        for name in filenames:
            found.append(relative / name)
            if len(found) >= max_files:
                return sorted(found)
    return sorted(found)


def git_files(root: Path | None = None) -> list[Path]:
    """Files tracked by git under `root`, or a bounded scan when it is not a repo."""
    root = root or repo_root()
    code, out, _ = git(["ls-files"], root)
    if code != 0:
        return scan_files(root)
    return [Path(line) for line in out.splitlines() if line.strip()]


def changed_files(root: Path | None = None) -> list[Path]:
    root = root or repo_root()
    code, out, _ = git(["status", "--porcelain"], root)
    if code != 0:
        return []
    files: list[Path] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        files.append(Path(raw))
    return sorted(set(files))


def untracked_files(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    code, out, _ = git(["status", "--porcelain"], root)
    if code != 0:
        return []
    return sorted(line[3:] for line in out.splitlines() if line.startswith("?? "))


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if value == "[]" or value == "":
                data[key] = []
            elif value.lower() in {"true", "false"}:
                data[key] = value.lower() == "true"
            else:
                data[key] = value.strip('"')
    return data, body


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def load_hook_payload() -> dict[str, Any]:
    try:
        if os.isatty(0):
            return {}
        raw = os.read(0, 1024 * 1024).decode("utf-8", errors="replace").strip()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def hook_output(event_name: str, **values: Any) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event_name, **values}}


def hook_additional_context(event_name: str, message: str) -> dict[str, Any]:
    return hook_output(event_name, additionalContext=message)


def permission_output(event_name: str, decision: str, reason: str, **values: Any) -> dict[str, Any]:
    return hook_output(
        event_name,
        permissionDecision=decision,
        permissionDecisionReason=reason,
        **values,
    )


def relpath(path: Path, root: Path | None = None) -> str:
    root = (root or repo_root()).resolve()
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def classify_file_path(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = path.suffix.lower()
    text = str(path).replace("\\", "/").lower()
    if name.startswith(".env") or suffix in {".pem", ".key", ".p12"} or "credential" in name or "secret" in name:
        return "secret-risk"
    if any(part in parts for part in {"tests", "test", "__tests__", "spec", "specs"}) or name.endswith(
        (".test.ts", ".test.js", ".spec.ts", ".spec.js", "_test.py")
    ):
        return "test"
    if suffix in {".md", ".mdx", ".rst"}:
        return "docs"
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"} or name.startswith("."):
        return "config"
    if "migration" in parts or "migrations" in parts:
        return "migration"
    if suffix in {".schema", ".graphql"} or "schema" in parts or name.endswith(".schema.json"):
        return "schema"
    if any(part in parts for part in {"dist", "build", "coverage", "__pycache__", ".next", ".turbo"}):
        return "build-artifact"
    if "generated" in text or name.endswith((".generated.ts", ".generated.js", ".gen.ts", ".pb.go")):
        return "generated"
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".cs", ".rb", ".php", ".sh"}:
        return "source"
    return "unknown"


ENV_VAR_RE = re.compile(
    r"(?:process\.env\.|os\.environ(?:\.get)?\(['\"]|getenv\(['\"]|\$env:|\$\{?)([A-Z][A-Z0-9_]{2,})"
)


def placeholder_for_env(name: str) -> str:
    lname = name.lower()
    if "stripe" in lname and "webhook" in lname:
        return "whsec_example"
    if "stripe" in lname and "secret" in lname:
        return "sk_test_example"
    if "anthropic" in lname or "claude" in lname:
        return "sk-ant-example"
    if "openai" in lname:
        return "sk-example"
    if "url" in lname:
        return "https://example.invalid"
    if "token" in lname or "secret" in lname or "key" in lname:
        return "replace-me"
    return "example"


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def parse_env_example_keys(path: Path) -> set[str]:
    """Variable names declared in one .env.example file (handles `export`/comments/quotes)."""
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" in stripped:
            keys.add(stripped.split("=", 1)[0].strip())
    return keys


def nearest_env_example(start: Path, stop: Path | None = None) -> Path | None:
    """Nearest .env.example at or above `start`, never searching past the repo root.

    Fixes the monorepo case where code lives in `apps/cloud/src` but the env template
    is one level up at `apps/cloud/.env.example`.
    """
    start = start.resolve()
    stop = (stop or repo_root(start)).resolve()
    current = start if start.is_dir() else start.parent
    while True:
        candidate = current / ".env.example"
        if candidate.exists():
            return candidate
        if current == stop or current == current.parent:
            return None
        current = current.parent


def env_example_keys(start: Path | None = None) -> set[str]:
    """Union of keys from every .env.example from `start` (or cwd) up to the repo root.

    Ancestor-walk only. A repo-wide descendant scan is deliberately avoided: on a
    hygiene/secrets tool it would let one package's .env.example mask another
    package's genuinely undocumented variable — a false negative worse than the
    noisy false positives this replaces.
    """
    start = (start or Path.cwd()).resolve()
    stop = repo_root(start)
    keys: set[str] = set()
    current = start if start.is_dir() else start.parent
    while True:
        candidate = current / ".env.example"
        if candidate.exists():
            keys |= parse_env_example_keys(candidate)
        if current == stop or current == current.parent:
            break
        current = current.parent
    return keys
