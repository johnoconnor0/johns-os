#!/usr/bin/env python3
"""Shared helpers for the Engineering Lifecycle plugin scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(".project") / ".engineering"

# Two roots, two audiences. The workspace above is machine state: ledger, reports,
# context, council, hygiene, dashboards, questions, registry. DOCS_ROOT below holds
# the narrative deliverables a person actually reads - PRDs, technical design
# documents, app flows, design systems and engineering plans - so they are not
# buried inside a dot-directory of runtime state.
DOCS_ROOT = Path(".project") / "docs" / "engineering"

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

# Stage subdirectories inside `initiatives/<initiative-id>/`, per the workspace
# contract. Previously these existed only as prose in three documents and were
# created ad hoc by whichever skill wrote first.
INITIATIVE_STAGES = (
    "discovery",
    "requirements",
    "ux",
    "system-map",
    "architecture",
    "data",
    "api",
    "design-system",
    "prototype",
    "implementation",
    "review",
    "testing",
    "release",
    "maintenance",
)

# Subdirectories inside `docs/engineering/<initiative-id>/`. The narrative
# deliverables sit at the top level; these two hold sets of files rather than one.
DOCS_SUBDIRS = ("design-system", "data", "system-map", "api")

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


def docs_root(root: Path | None = None) -> Path:
    """Where the human-readable deliverables live."""
    return (root or repo_root()) / DOCS_ROOT


def artifact_roots(root: Path | None = None) -> list[Path]:
    """Both artifact trees, for anything that scans or validates the lot."""
    base = root or repo_root()
    return [engineering_root(base), docs_root(base)]


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


def read_json_safe(path: Path) -> dict[str, Any]:
    """A JSON object, or an empty one, never an exception.

    `read_json` raises on malformed content, which is right when a caller must
    know the file is broken. Detection and context-gathering callers want the
    opposite: a corrupt generated file should degrade the answer, not abort the
    scan that was reading it.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _atomic_write(path: Path, payload: str) -> None:
    """Write through a sibling temp file and one `os.replace`.

    Seven PostToolUse hooks fire on a single edit, several of them writing into
    this tree at the same time, and `open(path, "w")` truncates before it writes
    anything. A reader arriving mid-write - or a session ending mid-write - saw a
    half-written or empty file. `read_json_safe` exists precisely to swallow that,
    which is evidence it happened rather than a reason to keep causing it.

    The temp file is a sibling, not in the system temp directory: `os.replace` is
    only atomic within one filesystem. It is atomic on POSIX and on Windows, where
    it maps to MoveFileEx with MOVEFILE_REPLACE_EXISTING.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None  # type: ignore[assignment]
    finally:
        if tmp is not None:
            with suppress(OSError):
                tmp.unlink()


def write_json(path: Path, data: Any) -> None:
    _atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, text: str) -> None:
    _atomic_write(path, text)


def hygiene_report_path(root: Path | None = None) -> Path:
    return engineering_root(root) / "hygiene" / "hygiene-report.json"


def write_hygiene_part(root: Path, producer: str, section: dict[str, Any]) -> dict[str, Any]:
    """Record one producer's keys, then rebuild the combined hygiene report.

    `detect-new-env-vars` and `suggest-gitignore-updates` are adjacent entries in
    the same PostToolUse matcher group, so they run concurrently on every edit.
    Both used to read the whole report, replace their own key, and write it back,
    swallowing a parse failure with an empty dict - so whichever finished second
    erased the other's section rather than failing.

    Atomic writes alone do not fix that; the read-modify-write is the bug. Each
    producer now owns a file under `hygiene/parts/`, and the report becomes a view
    rebuilt from them. Two concurrent rebuilds both read every fragment from disk,
    so they converge on the same content and a lost race costs nothing.

    Keys no fragment claims - `risks`, `docs_updates`, whatever the
    update-repo-hygiene skill wrote - are preserved, so the combined file stays
    the single thing readers and the schema know about.
    """
    write_json(hygiene_report_path(root).parent / "parts" / f"{producer}.json", section)
    return rebuild_hygiene_report(root)


def rebuild_hygiene_report(root: Path | None = None) -> dict[str, Any]:
    report = hygiene_report_path(root)
    merged = read_json_safe(report)
    for part in sorted((report.parent / "parts").glob("*.json")):
        merged.update(read_json_safe(part))
    merged.setdefault("risks", [])
    write_json(report, merged)
    return merged


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


# A markdown checklist line, which is how a plan states a discrete piece of work.
# This lived in `emit-action-items.py`, whose hyphenated name makes it unimportable,
# so anything else needing to read a plan the same way had to re-declare the pattern
# and drift from it. It belongs beside the other shared parsers.
ACTION_RE = re.compile(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+(?P<title>.+)$")


def item_from_text(line: str, source: str, index: int) -> dict[str, Any] | None:
    """One ledger action item from one checklist line, or None."""
    match = ACTION_RE.match(line)
    if not match:
        return None
    return {
        "id": f"{slugify(Path(source).stem)}-{index:03d}",
        "title": match.group("title").strip(),
        "status": "done" if match.group("state").lower() == "x" else "open",
        "source": source,
        "created_at": now_iso(),
        "owner": "unassigned",
        "priority": "normal",
    }


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


# Explicit accessors only. A bare `$NAME` used to be part of this pattern and was
# the single largest source of noise in the hygiene reports: in a shell script it
# matches locals far more often than environment variables (65 hits on this repo,
# 6 of them genuine), and in TypeScript it matches every `${...}` template
# literal. Shell references are handled by `shell_env_names` below, which can tell
# an inherited variable from a local. `$env:` stays — it is unambiguous PowerShell.
ENV_VAR_RE = re.compile(r"(?:process\.env\.|os\.environ(?:\.get)?[\(\[]['\"]|getenv\(['\"]|\$env:)([A-Z][A-Z0-9_]{2,})")

# Names that are always supplied by the shell, the OS or the agent harness, and so
# never belong in a project's .env.example. Without these the shell pass below
# reports `BASH_SOURCE` and friends, which are read-but-never-assigned by
# definition and so pass its test.
IGNORED_ENV_NAMES = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "PWD",
        "OLDPWD",
        "IFS",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "TERM",
        "EDITOR",
        "VISUAL",
        "SHLVL",
        "HOSTNAME",
        "LOGNAME",
        "OSTYPE",
        "MACHTYPE",
        "HOSTTYPE",
        "UID",
        "EUID",
        "PPID",
        "SECONDS",
        "RANDOM",
        "LINENO",
        "REPLY",
        "FUNCNAME",
        "PIPESTATUS",
        "GROUPS",
        "COLUMNS",
        "LINES",
        "BASH",
        "BASH_SOURCE",
        "BASH_VERSION",
        "BASHOPTS",
        "BASHPID",
        # Supplied by the Claude Code harness, never by a project .env. ARGUMENTS is
        # the skill/slash-command placeholder, which appears as `$ARGUMENTS` in hook
        # scripts that check for it.
        "CLAUDE_PLUGIN_ROOT",
        "CLAUDE_PROJECT_DIR",
        "CLAUDE_CONFIG_DIR",
        "ARGUMENTS",
    }
)

SHELL_SUFFIXES = frozenset({".sh", ".bash", ".zsh", ".ksh"})

# An assignment is not always at the start of a line: `cmd && X=0 || X=$?` assigns
# X twice, mid-line, and anchoring to ^ misses both. Accepting any shell separator
# before the name is what keeps the five `*_EXIT` variables in this repo's own
# audit scripts from being reported as undocumented environment variables.
_SHELL_ASSIGN_RE = re.compile(
    r"(?:^|[\s;&|(){}])(?:export\s+|local\s+|readonly\s+|declare\s+(?:-\w+\s+)*)?([A-Za-z_]\w*)\+?=", re.M
)
# `declare -a NAMES HOSTS PORTS` declares locals without ever writing `=`. Missing
# this form reported six array locals in one audit script as environment variables.
_SHELL_DECLARE_RE = re.compile(r"\b(?:declare|local|readonly|typeset)\b(?:\s+-\w+)*((?:\s+[A-Za-z_]\w*)+)")
_SHELL_FOR_RE = re.compile(r"\bfor\s+([A-Za-z_]\w*)\s+in\b")
# Only `read` in command position. Matching it anywhere on the line would let the
# word "read" in a comment or an echo mark a genuine variable as locally assigned.
_SHELL_READ_RE = re.compile(r"(?:^|[;&|])\s*read\b(?P<rest>[^\n]*)", re.M)
_SHELL_REF_RE = re.compile(r"\$\{?([A-Z][A-Z0-9_]{2,})")


def _shell_assigned_names(text: str) -> set[str]:
    """Every shell variable `text` sets, by assignment, loop binding or `read`."""
    assigned = set(_SHELL_ASSIGN_RE.findall(text))
    assigned |= set(_SHELL_FOR_RE.findall(text))
    for names in _SHELL_DECLARE_RE.findall(text):
        assigned |= set(names.split())
    for rest in _SHELL_READ_RE.findall(text):
        # `read -r -d '' MESSAGE` — drop quoted flag arguments first, then the flags,
        # and whatever bare identifiers remain are the variables being bound.
        cleaned = re.sub(r"'[^']*'|\"[^\"]*\"", " ", rest)
        cleaned = re.sub(r"(?:^|\s)-\w+", " ", cleaned)
        assigned |= set(re.findall(r"\b([A-Za-z_]\w*)\b", cleaned))
    return assigned


def shell_env_names(text: str) -> set[str]:
    """Shell variables `text` reads but never assigns — i.e. inherited from the environment.

    A `$NAME` reference on its own proves nothing, because most shell variables are
    locals. What distinguishes an environment variable is that the script reads it
    without ever setting it: `SUPABASE_DB_URL` is read three times and assigned
    never, while `PYTHON_BIN` and `DRY_RUN` are assigned a few lines above their use.
    """
    assigned = _shell_assigned_names(text)
    return {name for name in _SHELL_REF_RE.findall(text) if name not in assigned}


# A helper is an env accessor when its body reaches the environment through its own
# parameter rather than a literal — indexing the env object with the argument it was
# handed. Matching the definition and the dynamic access separately, then requiring
# the parameter to connect them, is what keeps this from firing on any function that
# happens to sit near an env read. (Written without a literal example on purpose:
# `builds_env_names_dynamically` below would match the comment itself.)
_ENV_HELPER_DEF_RE = re.compile(
    r"(?:function\s+(?P<fn>\w+)\s*\(\s*(?P<fnarg>\w+)"
    r"|(?:const|let|var)\s+(?P<js>\w+)\s*=\s*(?:async\s+)?\(?\s*(?P<jsarg>\w+)"
    r"|def\s+(?P<py>\w+)\s*\(\s*(?P<pyarg>\w+))"
)
_DYNAMIC_ACCESS_TEMPLATE = r"(?:process\.env\[\s*{p}|os\.environ\[\s*{p}|os\.environ\.get\(\s*{p}|getenv\(\s*{p})"
# The same accessors reached with something other than a string literal. Used to
# report where enumeration is impossible rather than implying coverage.
_DYNAMIC_ENV_RE = re.compile(r"(?:process\.env\[|os\.environ\[|os\.environ\.get\(|getenv\()\s*(?!['\"])")


def env_accessor_names(text: str, window: int = 400) -> set[str]:
    """Names of single-argument helpers in `text` that read the environment by their parameter."""
    names: set[str] = set()
    for match in _ENV_HELPER_DEF_RE.finditer(text):
        name = match.group("fn") or match.group("js") or match.group("py")
        arg = match.group("fnarg") or match.group("jsarg") or match.group("pyarg")
        if not name or not arg:
            continue
        body = text[match.end() : match.end() + window]
        if re.search(_DYNAMIC_ACCESS_TEMPLATE.format(p=re.escape(arg)), body):
            names.add(name)
    return names


def indirect_env_names(text: str, accessors: Iterable[str] = ()) -> set[str]:
    """Variables read through a helper, e.g. `required('REPORT_LINK_SECRET')`.

    A regex anchored on `process.env.` sees the helper's single internal access and
    none of the call sites that name real variables, so a codebase that centralises
    its config reads — the disciplined case — is exactly the one a plain scan
    reports as clean.
    """
    names: set[str] = set()
    for helper in env_accessor_names(text) | {name for name in accessors if name}:
        names |= set(re.findall(rf"\b{re.escape(helper)}\s*\(\s*['\"]([A-Z][A-Z0-9_]{{2,}})['\"]", text))
    return names


def builds_env_names_dynamically(text: str) -> bool:
    """True when `text` reaches the environment with a computed name.

    Names assembled at runtime (an interpolated prefix, a loop over a list) cannot
    be enumerated statically by anything short of executing the code. Callers
    surface this so a file the detector cannot read is reported as unknown rather
    than silently counted as clean.
    """
    return bool(_DYNAMIC_ENV_RE.search(text))


def configured_env_accessors(root: Path) -> list[str]:
    """Accessor helper names the repo declares, for wrappers auto-detection cannot reach."""
    config = engineering_root(root) / "workspace.json"
    if not config.exists():
        return []
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except Exception:
        return []
    declared = data.get("env_accessors")
    return [str(name) for name in declared if str(name).strip()] if isinstance(declared, list) else []


def env_names_in(path: Path, text: str, accessors: Iterable[str] = ()) -> set[str]:
    """Every environment variable `text` references, by whichever mechanism.

    The single place any tool asks "what env vars does this file use?". Two
    detectors maintaining their own patterns is how they came to disagree about the
    same repository in the first place.
    """
    names = set(ENV_VAR_RE.findall(text))
    names |= indirect_env_names(text, accessors)
    if path.suffix.lower() in SHELL_SUFFIXES:
        names |= shell_env_names(text)
    return names - IGNORED_ENV_NAMES


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


def env_example_keys(start: Path | None = None, stop: Path | None = None) -> set[str]:
    """Union of keys from every .env.example from `start` (or cwd) up to `stop` (or the repo root).

    Ancestor-walk only. A repo-wide descendant scan is deliberately avoided: on a
    hygiene/secrets tool it would let one package's .env.example mask another
    package's genuinely undocumented variable — a false negative worse than the
    noisy false positives this replaces.

    Because the walk only ever goes up, callers must start it from the file that
    references the variable, not from the working directory. Starting from a
    monorepo root resolves nothing but a root-level template and reports every
    package-level variable as undocumented forever.
    """
    start = (start or Path.cwd()).resolve()
    stop = (stop or repo_root(start)).resolve()
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
