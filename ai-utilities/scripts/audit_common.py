#!/usr/bin/env python3
"""Shared helpers for the ai-utilities audit scripts.

Deliberately standalone. `ai-utilities` is an independently installable plugin: it
has its own manifest, its own marketplace entry, and when installed it runs from
`~/.claude/plugins/cache/<marketplace>/ai-utilities/<version>/`, where no sibling
plugin directory is guaranteed to exist. `from eng_common import ...` inside these
scripts would work in this repository and fail for anybody who installed this plugin
without also installing `engineering-lifecycle`.

So the small amount of overlap with `engineering-lifecycle/scripts/eng_common.py` is
intentional and is limited to primitives that cannot drift meaningfully - JSON IO,
repo-root resolution, timestamps. Anything with real behaviour behind it is reached
through the resolution ladder in `stack_probe.py` instead of copied.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Kept in step with eng_common.SCAN_PRUNE_DIRS. Divergence here costs a slower scan,
# not a wrong answer, which is why duplicating it is acceptable and duplicating a
# detector would not be.
PRUNE_DIRS = frozenset(
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

AUDIT_DIR = Path(".project") / "audits" / "plan-completion-audit"

# Kept from check-secrets.sh, which had the one genuinely reusable part of the six.
# Lives here rather than in checks.py because it has two jobs now: finding
# credentials committed to a repository, and keeping credentials that appear in a
# build's own output from being written into an audit artifact.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"), "private key block"),
    ("stripe-secret", re.compile(r"\bsk_live_[0-9a-zA-Z]{16,}"), "live Stripe secret key"),
    ("slack-token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}"), "Slack token"),
    ("github-token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}"), "GitHub token"),
    ("anthropic-key", re.compile(r"\bsk-ant-[0-9A-Za-z-]{20,}"), "Anthropic API key"),
    ("openai-key", re.compile(r"\bsk-[0-9A-Za-z]{32,}\b"), "OpenAI-style API key"),
    (
        "generic-assignment",
        re.compile(r"(?i)\b(?:api_?key|secret|password|token)\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"),
        "hardcoded credential",
    ),
)

# Connection strings carry the password in the middle of a URL, which none of the
# patterns above match. An audit that runs a project's own commands sees these in
# stderr constantly - a failing migration prints its DSN.
_DSN = re.compile(r"\b([a-z][a-z0-9+.-]*://)([^\s:@/]+):([^\s@/]+)@")


def scrub_secrets(text: str) -> str:
    """Credentials in captured command output replaced with a marker.

    Audit findings persist command output verbatim into `findings.json` and
    `report.md`, which then get committed or pasted into an issue. A failing
    `npm audit`, migration or test run routinely echoes a token or a DSN, so the
    scrub happens on the way in rather than being left to whoever reads it.
    """
    if not text:
        return text
    scrubbed = _DSN.sub(r"\1\2:<redacted>@", text)
    for _rule, pattern, label in SECRET_PATTERNS:
        scrubbed = pattern.sub(f"<{label} redacted>", scrubbed)
    return scrubbed


# shlex keeps these as ordinary tokens, so they have to be rejected by name.
_SHELL_OPERATORS = frozenset({"&&", "||", "|", "&", ";", ">", ">>", "<", "<<"})


def command_argv(command: str) -> list[str] | None:
    """A command string as an argv list with its executable resolved, or None.

    None means the string needs a shell to mean what it says. Refusing those is
    the point rather than a limitation: this plugin runs commands chosen by the
    repository under audit, and pipes, redirection and `&&` are how such a string
    stops being a test run. A project that genuinely needs a shell can put the
    pipeline in a script and declare the script.

    `shutil.which` is what makes `shell=False` work on Windows, where npm, npx and
    yarn are `.CMD` shims that CreateProcess will not find by bare name.
    """
    if any(char in command for char in "|<>&;`$\n\r"):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv or any(token in _SHELL_OPERATORS for token in argv):
        return None
    resolved = shutil.which(argv[0])
    if resolved is None:
        return None
    return [resolved, *argv[1:]]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def run_id(stamp: str | None = None) -> str:
    """The timestamp that names one audit run's directory."""
    return stamp or datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")


def repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            return candidate
        if (candidate / ".claude-plugin" / "plugin.json").exists():
            return candidate
    return cur


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def scan_files(root: Path, suffixes: frozenset[str] | None = None, max_files: int = 20_000) -> list[Path]:
    """Bounded walk of `root`, pruning the usual generated trees."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in PRUNE_DIRS)
        for name in filenames:
            path = Path(dirpath) / name
            if suffixes and path.suffix.lower() not in suffixes:
                continue
            found.append(path)
            if len(found) >= max_files:
                return sorted(found)
    return sorted(found)


def audit_dir(root: Path, stamp: str) -> Path:
    """One directory per run, holding the report and its machine-readable twin.

    A directory rather than a bare `<TIMESTAMP>.md`, because the run now emits two
    artefacts. `audit-resolver`'s newest-by-name discovery is unaffected: the names
    still sort chronologically.
    """
    return root / AUDIT_DIR / stamp


_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Minimal YAML front matter: scalars and `- ` lists, which is all artifacts use."""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    data: dict[str, Any] = {}
    current: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith(("  - ", "- ")) and current:
            data.setdefault(current, []).append(line.split("- ", 1)[1].strip().strip('"'))
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            current = key.strip()
            value = value.strip()
            if value in {"", "[]"}:
                data[current] = []
            elif value.lower() in {"true", "false"}:
                data[current] = value.lower() == "true"
            else:
                data[current] = value.strip('"')
    return data, text[match.end() :]
