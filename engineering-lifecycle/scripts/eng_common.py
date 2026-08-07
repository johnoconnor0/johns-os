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
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
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

# Markdown inside the workspace that this plugin *renders* rather than a human
# authors: a readable view of a JSON store beside it, rewritten from scratch on
# every turn. Listed by exact path, not by directory, so a future authored
# artifact cannot fall through the gap by landing in the same folder.
#
# `validate-artifact.py` skips them, and it has to. They are not artifacts:
# `REQUIRED_FRONT_MATTER` asks a digest for one initiative_id, one skill and one
# confidence when a digest spans every initiative and was written by no skill, so
# the only way to satisfy it is to invent all six values - a validator passing on
# metadata that means nothing. Worse, the bodies quote text the plugin does not
# author (a human's question, a detector's issue title), so a question containing
# the word TBD would trip the placeholder check forever with nothing the user
# could edit to fix it. This hook is wired PostToolUse: it fired on every edit for
# the life of the project, reporting its own output as broken.
GENERATED_DIGESTS = frozenset(
    {
        "questions/open-questions.md",
        "tracker/surfaced-issues.md",
        "tracker/workstreams.md",
        "context/repo-context.md",
        "reports/mermaid-index.md",
    }
)


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _refused_roots() -> frozenset[Path]:
    """Directories that must never anchor a resolved root, however they are marked.

    A stray ``.project/.engineering`` in a home or system temp directory is not a
    project - it is debris from before the workspace became opt-in, and machines
    that ran an early version of this plugin carry them. Without this guard,
    promoting the workspace to a resolution marker makes every temporary directory
    resolve to the system temp root and every path under $HOME resolve to $HOME.
    The whole test suite runs in temporary directories, so this is load-bearing
    rather than defensive.
    """
    refused: set[Path] = set()
    with suppress(OSError, RuntimeError):  # home is undefined in some sandboxes
        home = Path.home().resolve()
        refused.add(home)
        refused.update(home.parents)
    with suppress(OSError, RuntimeError):
        # The temp directory itself, not its parents: CI sometimes points TMPDIR
        # inside a checkout, and refusing that checkout's own root would disable
        # the plugin for the build it is meant to be running in.
        refused.add(Path(tempfile.gettempdir()).resolve())
    return frozenset(refused)


def is_addressable_root(path: Path) -> bool:
    """True when `path` may anchor a workspace, whatever markers it carries."""
    if path.parent == path:  # filesystem or drive root
        return False
    if path in _refused_roots():
        return False
    parts = set(path.parts)
    # `.claude` vendors one git clone per installed marketplace. `.project` is
    # this plugin's own state tree, so a workspace found inside one is a scaffold
    # some skill wrote rather than a project root - `SCAN_PRUNE_DIRS` already
    # prunes `.project` everywhere else, and resolution has to agree with scanning.
    return ".claude" not in parts and ".project" not in parts


@dataclass(frozen=True)
class RootResolution:
    """A resolved root and the evidence for it.

    The hardest failure to see in this plugin was a correct-looking run against
    the wrong root: nothing errored, nothing was empty, the answers were simply
    about a different project. Every tool can now report where it decided it was
    and which file proved it.
    """

    root: Path
    reason: str  # explicit | workspace | repo | fallback
    marker: str  # the path that proved it, or ""
    start: Path
    start_source: str  # argument | CLAUDE_PROJECT_DIR | cwd
    has_workspace: bool
    # Every addressable ancestor carrying a workspace, nearest first.
    workspace_ancestors: tuple[Path, ...]


def _start_dir(start: Path | None) -> tuple[Path, str]:
    """Where the upward walk begins, and what chose it.

    ``CLAUDE_PROJECT_DIR`` is the harness saying which directory the session is
    about. It sets the START of the walk, never the answer: a session opened at a
    monorepo root while the work happens in a package must still resolve to the
    package, and a session opened three directories deep in a repo with no
    workspace must still resolve to the repo root.
    """
    if start is not None:
        candidate, source = Path(start).expanduser(), "argument"
    else:
        raw = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
        candidate, source = (Path(raw).expanduser(), "CLAUDE_PROJECT_DIR") if raw else (Path.cwd(), "cwd")
    try:
        resolved = candidate.resolve()
    except OSError:
        return Path.cwd().resolve(), "cwd"
    if resolved.is_dir():
        return resolved, source
    # A value naming a *file* means its directory. A value naming nothing at all
    # is a misconfiguration, and walking from its parent anyway would silently
    # honour a path the user got wrong.
    if resolved.is_file():
        return resolved.parent, source
    return Path.cwd().resolve(), "cwd"


def workspace_ancestors(start: Path) -> tuple[Path, ...]:
    return tuple(c for c in [start, *start.parents] if is_addressable_root(c) and (c / WORKSPACE).is_dir())


def resolve_root(start: Path | None = None, explicit: Path | None = None) -> RootResolution:
    """Where this invocation's workspace is anchored, and why.

    One upward walk, three markers, nearest wins, and the workspace marker is
    tested first so a directory carrying both answers "workspace".

    The workspace marker exists because it is the only *deliberate* one. `.git` is
    incidental - a nested package inside a monorepo has none of its own - so while
    `.git` was the only marker, a workspace created by `/project-init here` could
    never be addressed by anything that later read it. The create path and the
    resolve path disagreed, which is the whole defect.

    The walk never descends. That is what preserves the property
    ``workspace_exists`` documents: an ancestor walk can only land on a directory
    somebody deliberately initialised, and it creates nothing, so a hook firing
    from a generated subfolder still cannot drop a stray `.project` there.
    """
    if explicit is not None:
        exact = Path(explicit).expanduser().resolve()
        return RootResolution(
            root=exact,
            reason="explicit",
            marker=str(exact),
            start=exact,
            start_source="argument",
            has_workspace=(exact / WORKSPACE).is_dir(),
            workspace_ancestors=workspace_ancestors(exact),
        )

    begin, source = _start_dir(start)
    chosen: Path | None = None
    reason = marker = ""
    found: list[Path] = []
    for candidate in [begin, *begin.parents]:
        if not is_addressable_root(candidate):
            continue
        if (candidate / WORKSPACE).is_dir():
            found.append(candidate)
            if chosen is None:
                chosen, reason, marker = candidate, "workspace", str(candidate / WORKSPACE)
            continue
        if chosen is None:
            if (candidate / ".git").exists():
                chosen, reason, marker = candidate, "repo", str(candidate / ".git")
            elif (candidate / ".claude-plugin" / "plugin.json").exists():
                chosen, reason, marker = candidate, "repo", str(candidate / ".claude-plugin" / "plugin.json")
    if chosen is None:
        chosen, reason, marker = begin, "fallback", ""
    return RootResolution(
        root=chosen,
        reason=reason,
        marker=marker,
        start=begin,
        start_source=source,
        has_workspace=(chosen / WORKSPACE).is_dir(),
        workspace_ancestors=tuple(found),
    )


def repo_root(start: Path | None = None) -> Path:
    """The resolved root. Thin wrapper - most call sites only want the path."""
    return resolve_root(start).root


def resolve_cli_root(root: str | None) -> RootResolution:
    """The root for one CLI invocation.

    An explicit `--root` is taken **verbatim**. Passing it back through the walk
    is what made it useless as an escape hatch: pointing the tooling at a nested
    package silently walked back up to the monorepo root and operated on the wrong
    project. Omitting `--root` resolves from the working directory.
    """
    return resolve_root(explicit=Path(root)) if root else resolve_root()


def engineering_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / WORKSPACE


def docs_root(root: Path | None = None) -> Path:
    """Where the human-readable deliverables live."""
    return (root or repo_root()) / DOCS_ROOT


def is_generated_digest(path: Path, root: Path | None = None) -> bool:
    """True when `path` is one of the digests this plugin renders for itself."""
    try:
        relative = Path(path).resolve().relative_to(engineering_root(root).resolve())
    except (OSError, ValueError):
        return False
    return relative.as_posix() in GENERATED_DIGESTS


def artifact_roots(root: Path | None = None) -> list[Path]:
    """Both artifact trees, for anything that scans or validates the lot."""
    base = root or repo_root()
    return [engineering_root(base), docs_root(base)]


def workspace_exists(root: Path | None = None) -> bool:
    """True once the Engineering Lifecycle workspace exists for this repo.

    The workspace is opt-in per repo: it is created only by explicit user action
    (the /project-init command, ``eng-life init``, or a lifecycle skill writing its
    first artifact) — never by automatic session/post-tool/stop hooks. Until it
    exists, those hooks stay dormant and must not create it.

    Anchored to the nearest deliberately-initialised workspace, else the repo root
    (see ``resolve_root``). A hook firing from a subfolder still cannot drop a
    stray ``.project`` there, because the walk only ever goes up: it can land on a
    directory somebody chose to initialise, and it creates nothing.
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


def read_json_lenient(path: Path, default: Any = None) -> Any:
    """`read_json`, with a malformed file treated the same as an absent one.

    For the readers that legitimately accept a list *or* an object, where
    `read_json_safe`'s dict-only contract would quietly discard the list form.
    Same reasoning as `read_json_safe` otherwise: half-written generated files are
    a state this tree reaches, not one a scan may refuse to continue past.
    """
    try:
        return read_json(path, default)
    except (OSError, ValueError):
        return default


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


# Credentials as they appear *in file contents*, for the case where a file is
# about to leave the machine. Deliberately not quality_tools.SECRET_PATTERNS: that
# list matches *mentions* of secret-bearing files in a shell command, which is what
# a command guard wants and would mangle prose - "check your .env" is not a secret.
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----[\s\S]*?-----END[^\n]*-----"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    # JWTs carry claims as well as authority, so they are worth removing whole.
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
)
# A password inside a connection string, which none of the token patterns match.
_DSN_CREDENTIAL = re.compile(r"\b([a-z][a-z0-9+.-]*://)([^\s:@/]+):([^\s@/]+)@")
# KEY=value lines, matched on the name. Over-redacting a URL costs an advisor a
# little context; under-redacting one sends a credential to a third party.
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)^(\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*"
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|DSN|_URI|_URL)S?)(\s*[=:]\s*)(\S.*)$"
)


def redact_secrets(text: str) -> str:
    """Credential values replaced with a marker, for text about to leave the box.

    Used on anything bound for a third-party API. Names and structure survive so
    the text still reads; only the values go.
    """
    if not text:
        return text
    redacted = _DSN_CREDENTIAL.sub(r"\1\2:<redacted>@", text)
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return _SECRET_ASSIGNMENT.sub(r"\1\2<redacted>", redacted)


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

    ``repo_root`` falls back to the cwd when it finds no marker above it, so
    outside a repo this can be handed a home directory, a filesystem root, or an
    agent config tree. ``~/.claude`` in particular vendors plugin caches and one
    git clone per installed marketplace - walking it costs hundreds of thousands
    of files and yields nothing a stack detector or context pack can use.

    Same predicate as ``is_addressable_root``, deliberately: a directory this
    plugin refuses to scan is one it must also refuse to anchor to, or the two
    would disagree about the same tree.
    """
    return is_addressable_root(root)


NESTED_SCAN_MAX_DEPTH = 4
NESTED_SCAN_MAX_DIRS = 4_000


def nested_workspaces(
    root: Path,
    max_depth: int = NESTED_SCAN_MAX_DEPTH,
    max_dirs: int = NESTED_SCAN_MAX_DIRS,
) -> list[Path]:
    """Workspaces strictly below `root`. Reporting only.

    Bounded exactly like ``scan_files``, and pruned by the same set - which
    includes `.project`, so this never descends into a workspace looking for more.
    Resolution deliberately does not use this: an upward walk stays correct when
    this listing is truncated or stale, and is cheap enough for every hook.
    """
    root = root.resolve()
    if not is_addressable_root(root):
        return []
    found: list[Path] = []
    for seen, (dirpath, dirnames, _) in enumerate(os.walk(root), 1):
        if seen > max_dirs:
            break
        here = Path(dirpath)
        if len(here.relative_to(root).parts) >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = sorted(name for name in dirnames if name not in SCAN_PRUNE_DIRS)
        if here != root and (here / WORKSPACE).is_dir():
            found.append(here)
            dirnames[:] = []  # a workspace is a leaf; do not nest inside one
    return sorted(found)


def unreachable_workspaces(root: Path) -> list[Path]:
    """Workspaces buried inside `root`'s own `.project` tree.

    Deliberately separate from ``nested_workspaces``: these are unaddressable by
    design, since ``is_addressable_root`` refuses anything under `.project`.
    Reported so they can be moved or removed rather than silently ignored forever.
    """
    base = root / ".project"
    if not base.is_dir():
        return []
    return sorted({path.parents[1] for path in base.glob(f"*/*/{WORKSPACE.as_posix()}")})


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


@dataclass(frozen=True)
class HookPayload:
    """What arrived on stdin, and whether it could be understood at all.

    The distinction a bare dict could not carry. "The harness sent nothing" and
    "the harness sent something this could not parse" both used to come back as
    `{}`, and the two PreToolUse guards read an empty payload as "no command to
    object to" - so an input they could not read was indistinguishable from an
    input they had cleared. `unreadable` is what lets them fail closed instead.
    """

    data: dict[str, Any]
    unreadable: bool = False
    detail: str = ""


# Far above any payload the harness will ever send, and present only so a runaway
# producer cannot make a hook the process that runs out of memory. Exceeding it is
# reported as unreadable - never quietly truncated, which is the defect below.
HOOK_PAYLOAD_MAX_BYTES = 64 * 1024 * 1024


def _stdin_bytes(limit: int) -> bytes:
    """Stdin read to EOF, or far enough past `limit` for the caller to notice."""
    chunks: list[bytes] = []
    size = 0
    while size <= limit:
        chunk = os.read(0, 1 << 16)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
    return b"".join(chunks)


def read_hook_payload() -> HookPayload:
    """The hook payload on stdin, with a usable answer for every kind of stdin.

    Read to EOF. The previous single `os.read(0, 1024 * 1024)` returned at most one
    buffer, so a payload over 1 MiB - one Write of a large file, one long Bash
    command - arrived truncated mid-document, failed to parse, and a bare
    `except Exception: return {}` turned that into "the harness sent nothing". For
    the PreToolUse guards that meant they FAIL OPEN: `rm -rf /` was denied at 112
    bytes and allowed at 2 MiB. A guard that stops seeing its input above a size
    threshold is not a guard.

    Three outcomes, kept distinguishable:

    * a JSON object -> that object, `unreadable` False
    * nothing on stdin -> `{}`, `unreadable` False (a tty, a CLI run, a closed pipe)
    * anything else -> `{}`, `unreadable` True

    The third case covers both a document that will not parse and one that parses
    to something that is not an object - a top-level array or scalar, which is a
    payload every consumer would then call `.get` on. Consumers still see an empty
    dict, which is what "treated as no payload" has to mean for them; only the
    guards, which must not treat "unseen" as "clean", look at the flag.
    """
    try:
        if os.isatty(0):
            return HookPayload({})
        raw = _stdin_bytes(HOOK_PAYLOAD_MAX_BYTES)
    except (OSError, ValueError) as exc:
        # No readable stdin at all, which is the CLI shape rather than a hostile
        # one: nothing was sent, so nothing was missed.
        return HookPayload({}, False, f"stdin could not be read: {exc}")
    if len(raw) > HOOK_PAYLOAD_MAX_BYTES:
        return HookPayload({}, True, f"payload exceeded {HOOK_PAYLOAD_MAX_BYTES} bytes")
    # BOM first: Windows producers emit one, it is not whitespace, and `strip()`
    # leaves it in front of the `{` where it fails the parse for no good reason.
    text = raw.decode("utf-8", errors="replace").lstrip("﻿").strip()
    if not text:
        return HookPayload({})
    try:
        data = json.loads(text)
    except ValueError as exc:
        return HookPayload({}, True, f"stdin is not JSON: {exc}")
    if not isinstance(data, dict):
        return HookPayload({}, True, f"hook payload is a {type(data).__name__}, not an object")
    return HookPayload(data)


def load_hook_payload() -> dict[str, Any]:
    """The payload alone, for callers with nothing to decide about unreadability."""
    return read_hook_payload().data


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
    if (
        name.startswith(".env")
        or suffix in {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
        or name in {".netrc", "_netrc", ".pgpass", ".htpasswd", ".npmrc", ".pypirc"}
        or name.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"))
        or "credential" in name
        or "secret" in name
    ):
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
        #
        # CLAUDE_PROJECT_DIR stays here even though `_start_dir` now reads it. This
        # set governs one thing: which names must never be demanded in a *consuming
        # project's* .env.example. A variable the harness supplies belongs in
        # nobody's .env.example, and this plugin reading it does not change that.
        # Removing it would report CLAUDE_PROJECT_DIR as undocumented in every repo
        # that installs the plugin.
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
