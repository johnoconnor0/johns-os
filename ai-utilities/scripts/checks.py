#!/usr/bin/env python3
"""What each check family actually does.

These replace six bash scripts, deleted with the rest of the fixed-phase design.
Each is worth naming, because the reasons are not all the same:

  check-todos.sh        hardcoded ten file extensions, so a Go or Rust repo scanned
                        clean by construction. Extensions are derived from what is
                        on disk now.
  check-types.sh        reimplemented, worse, what the stack detector already does.
                        The detector's whole point is that it only emits commands
                        the project really declares.
  check-secrets.sh      the regex set was worth keeping; the npm-audit half belonged
                        in the dependency family and the service-role-key half in
                        the data layer.
  check-deprecated.sh   half Supabase, half npm.
  check-unused-deps.sh  its orphan-file test was `grep -rl "$BASENAME"`, which
                        false-positives on every repository containing a file called
                        something ordinary.
  audit-supabase.sh     the last hardcoded engine.

A runner returns a FamilyResult. It never decides `not-applicable` or `not-checked`
for itself - the registry's two predicates do that, so the distinction cannot be
quietly collapsed inside a runner.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from audit_common import SECRET_PATTERNS, command_argv, relpath, scan_files, scrub_secrets
from families import Ctx
from findings import Evidence, FamilyResult, Finding

# Extensions worth scanning for source-level markers, chosen from what is present
# rather than from a fixed list.
_SOURCE_SUFFIXES = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".java",
        ".kt",
        ".cs",
        ".swift",
        ".sql",
        ".sh",
        ".bash",
        ".ps1",
        ".vue",
        ".svelte",
        ".css",
        ".scss",
        ".yml",
        ".yaml",
        ".toml",
    }
)

_MARKERS = re.compile(r"\b(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB|INCOMPLETE|WIP)\b")

# A line that names three or more markers at once is a detector for them, not an
# instance of one. Without this the marker scan reports its own pattern table, the
# shell script it replaced, and every other placeholder-detector in the repo - which
# is exactly what the previous audit had to explain away by hand as "these are the
# detectors, not placeholders".
_MARKER_DETECTOR = re.compile(
    r"(?:TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB|INCOMPLETE|WIP)\b.*\b(?:FIXME|HACK|XXX|PLACEHOLDER|STUB|INCOMPLETE|WIP)\b.*\b(?:HACK|XXX|PLACEHOLDER|STUB|INCOMPLETE|WIP)\b"
)

# Shared with verify.py through audit_common: one list, two jobs - detecting
# credentials in a repository, and keeping them out of the artifacts this writes.
_SECRET_PATTERNS = SECRET_PATTERNS

# A placeholder in an example file is the example. Only real source counts.
_SECRET_SKIP_PARTS = frozenset({"examples", "templates", "fixtures", "tests", "test", "__tests__", "references"})

_BUILD_ARTIFACTS = ("dist", "build", ".next", "__pycache__", "coverage", "target")


def _lines(command: str, root: Path, timeout: int = 60) -> list[str]:
    """Full stdout of a listing command, split into lines.

    Deliberately not `_run`: that truncates output to the last 8000 characters,
    which is right for a failing build's diagnostics and catastrophic for a file
    listing - it silently cut this repository's tracked files from several hundred
    to 117, and every scan downstream inherited the wrong file set.
    """
    argv = command_argv(command)
    if argv is None:
        return []
    try:
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode != 0:
        return []
    return [line for line in (proc.stdout or "").splitlines() if line.strip()]


def _run(command: str, root: Path, timeout: int = 300) -> dict:
    """Run one check command as an argv list, never through a shell.

    `shell=True` here used to hand a string that can come from the audited
    repository's own `stack.json` straight to the shell. Running a project's
    declared checks is the point of this tool; letting a data file choose the
    shell syntax around them is not.
    """
    argv = command_argv(command)
    if argv is None:
        return {
            "cmd": command,
            "exit": None,
            "error": "needs a shell, or its executable is not on PATH",
            "output": "",
        }
    try:
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"cmd": command, "exit": None, "timed_out": True, "output": ""}
    except OSError as exc:
        return {"cmd": command, "exit": None, "error": str(exc), "output": ""}
    # Scrubbed here rather than at each use: this output is persisted verbatim
    # into findings.json and report.md, and a failing build routinely prints a
    # token or a DSN.
    output = scrub_secrets((proc.stdout or "") + (proc.stderr or ""))
    return {"cmd": command, "exit": proc.returncode, "output": output[-8000:]}


def _result(family, findings: list[Finding], commands: list[dict], applies_because: str = "") -> FamilyResult:
    return FamilyResult(
        id=family.id,
        title=family.title,
        outcome="failed" if findings else "passed",
        applies_because=applies_because,
        commands=commands,
        findings=findings,
    )


def _route(family) -> dict:
    return {"kind": "agent", "target": family.route, "available": None}


# --- runners ---------------------------------------------------------------


def run_unfinished_markers(ctx: Ctx, family) -> FamilyResult:
    suffixes = frozenset(path.suffix.lower() for path in ctx.files) & _SOURCE_SUFFIXES
    findings: list[Finding] = []
    for path in ctx.files:
        if path.suffix.lower() not in suffixes:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            match = _MARKERS.search(line)
            if not match or _MARKER_DETECTOR.search(line):
                continue
            findings.append(
                Finding(
                    family=family.id,
                    rule=f"marker/{match.group(1).lower()}",
                    severity="suggestion",
                    title=f"{match.group(1)} marker in {relpath(path, ctx.root)}",
                    detail=line.strip()[:200],
                    evidence=[Evidence(relpath(path, ctx.root), number, line.strip()[:200])],
                    route=_route(family),
                    suggested_strategy="auto",
                )
            )
    return _result(family, findings, [], f"scanned {len(suffixes)} source extension(s) present on disk")


def run_command_family(ctx: Ctx, family, keys: tuple[str, ...], severity: str) -> FamilyResult:
    """Run whichever of `keys` the detected stack declares, and report each."""
    declared = [ctx.commands[key] for key in keys if ctx.commands.get(key)]
    if declared and ctx.commands_are_repo_supplied and not ctx.allow_untrusted_commands:
        # Named rather than summarised: the point of stopping here is that somebody
        # gets to look at the strings before they run.
        return FamilyResult(
            id=family.id,
            title=family.title,
            outcome="not-checked",
            reason=(
                "these commands came from the audited repository's own "
                ".project/.engineering/context/stack.json, not from detection: "
                + "; ".join(f"`{command}`" for command in declared)
                + ". Re-run with --allow-untrusted-commands to execute them."
            ),
        )

    commands: list[dict] = []
    findings: list[Finding] = []
    for key in keys:
        command = ctx.commands.get(key)
        if not command:
            continue
        outcome = _run(command, ctx.root)
        commands.append({k: v for k, v in outcome.items() if k != "output"})
        if outcome.get("timed_out"):
            return FamilyResult(
                id=family.id,
                title=family.title,
                outcome="errored",
                reason=f"`{command}` did not finish within the timeout",
                commands=commands,
            )
        if outcome.get("exit"):
            findings.append(
                Finding(
                    family=family.id,
                    rule=f"command/{key}",
                    severity=severity,
                    title=f"`{command}` failed with exit {outcome['exit']}",
                    detail=outcome.get("output", "")[-2000:],
                    evidence=[Evidence(relpath(ctx.root, ctx.root) or ".", None, command)],
                    route=_route(family),
                    suggested_strategy="plan-first",
                )
            )
    return _result(family, findings, commands, ", ".join(f"stack.test_commands.{key}" for key in keys))


def run_secrets(ctx: Ctx, family) -> FamilyResult:
    findings: list[Finding] = []
    for path in ctx.files:
        if set(part.lower() for part in path.parts) & _SECRET_SKIP_PARTS:
            continue
        if path.suffix.lower() not in _SOURCE_SUFFIXES and path.name not in {".env", ".envrc"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            for rule, pattern, label in _SECRET_PATTERNS:
                if not pattern.search(line):
                    continue
                findings.append(
                    Finding(
                        family=family.id,
                        rule=f"secret/{rule}",
                        severity="critical",
                        title=f"Possible {label} in {relpath(path, ctx.root)}",
                        detail="The matched value is deliberately not reproduced here.",
                        evidence=[Evidence(relpath(path, ctx.root), number, f"<{label} redacted>")],
                        route=_route(family),
                        suggested_strategy="human-input",
                    )
                )
                break
    # A tracked .env is a finding on its own, whatever is inside it.
    for path in ctx.files:
        if path.name == ".env":
            findings.append(
                Finding(
                    family=family.id,
                    rule="secret/tracked-env",
                    severity="critical",
                    title=".env is tracked in version control",
                    detail="Add it to .gitignore and rotate anything it contained.",
                    evidence=[Evidence(relpath(path, ctx.root), None, "")],
                    route=_route(family),
                    suggested_strategy="human-input",
                )
            )
    return _result(family, findings, [], "always relevant")


def run_dependency_audit(ctx: Ctx, family) -> FamilyResult:
    manager = str(ctx.stack.get("package_manager") or "")
    command = {
        "npm": "npm audit --audit-level=high",
        "pnpm": "pnpm audit --audit-level=high",
        "yarn": "yarn npm audit --severity high",
        "python": "pip-audit",
        "cargo": "cargo audit",
        "go": "go list -json -m all",
    }.get(manager)
    if not command:
        return FamilyResult(
            id=family.id,
            title=family.title,
            outcome="not-checked",
            reason=f"no dependency auditor known for {manager!r}",
        )
    outcome = _run(command, ctx.root)
    findings: list[Finding] = []
    if outcome.get("exit"):
        findings.append(
            Finding(
                family=family.id,
                rule="dependency/vulnerability",
                severity="critical",
                title=f"`{command}` reported vulnerabilities",
                detail=outcome.get("output", "")[-2000:],
                evidence=[Evidence(".", None, command)],
                route=_route(family),
                suggested_strategy="plan-first",
            )
        )
    return _result(
        family, findings, [{k: v for k, v in outcome.items() if k != "output"}], f"package manager {manager}"
    )


def run_repo_hygiene(ctx: Ctx, family) -> FamilyResult:
    findings: list[Finding] = []
    paths = _lines("git ls-files", ctx.root)
    for line in paths:
        first = line.split("/", 1)[0]
        if first in _BUILD_ARTIFACTS or "/__pycache__/" in line or line.endswith(".pyc"):
            findings.append(
                Finding(
                    family=family.id,
                    rule="hygiene/committed-artifact",
                    severity="warning",
                    title=f"Build artifact is tracked: {line}",
                    detail="Generated output should be ignored, not committed.",
                    evidence=[Evidence(line, None, "")],
                    route=_route(family),
                    suggested_strategy="auto",
                )
            )
    return _result(family, findings, [{"cmd": "git ls-files", "exit": 0, "files": len(paths)}], "git repository")


def run_dead_code(ctx: Ctx, family) -> FamilyResult:
    """Python modules under the repo that nothing imports.

    Name-level only, and deliberately so: a real reachability analysis needs an
    import graph per language, and the shell version's `grep -rl "$BASENAME"` stood
    in for one badly enough to false-positive on any common filename.
    """
    if not ctx.has("backend", "Python"):
        return FamilyResult(
            id=family.id,
            title=family.title,
            outcome="not-checked",
            reason="only the Python arm of this family is implemented",
        )
    modules = {path.stem: path for path in ctx.files if path.suffix == ".py" and path.stem != "__init__"}
    referenced: set[str] = set()
    for path in ctx.files:
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name in modules:
            if name != path.stem and re.search(rf"\b{re.escape(name)}\b", text):
                referenced.add(name)
    findings = [
        Finding(
            family=family.id,
            rule="dead-code/unreferenced-module",
            severity="suggestion",
            title=f"`{relpath(path, ctx.root)}` is not referenced by name anywhere else",
            detail="Name-level only. Confirm it is not an entrypoint before removing it.",
            evidence=[Evidence(relpath(path, ctx.root), None, "")],
            route=_route(family),
            suggested_strategy="human-input",
        )
        for name, path in sorted(modules.items())
        if name not in referenced and "__main__" not in path.read_text(encoding="utf-8", errors="ignore")
    ]
    return _result(family, findings, [], "Python sources detected")


def collect_files(root: Path) -> list[Path]:
    """Files git tracks, or a bounded walk when this is not a repository.

    Tracked-only is the right set and not just the faster one: it honours the
    project's own `.gitignore` without this script needing to know anything about
    it. On this repository that is what keeps `_unreleased/` - deliberately excluded
    from ruff, pre-commit, yamllint and every marketplace manifest - out of the audit
    as well, with no special case for it anywhere in here.
    """
    tracked = [root / line for line in _lines("git ls-files", root)]
    if tracked:
        return [path for path in tracked if path.is_file()]
    return scan_files(root)
