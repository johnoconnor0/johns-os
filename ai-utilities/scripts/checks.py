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

import math
import re
from collections import Counter
from pathlib import Path

from audit_common import SECRET_PATTERNS, Captured, relpath, run_command, scan_files, scrub_secrets
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

# A placeholder in an example file is the example. Directories where a credential-
# shaped literal is overwhelmingly likely to be a fixture rather than a credential.
#
# `e2e` and `spec` are here because they were missing, and their absence is most of
# why a real run produced six false-positive criticals.
_SECRET_SKIP_PARTS = frozenset(
    {
        "examples",
        "example",
        "templates",
        "fixtures",
        "__fixtures__",
        "tests",
        "test",
        "__tests__",
        "testdata",
        "references",
        "e2e",
        "spec",
        "specs",
        "mocks",
        "__mocks__",
        "stories",
    }
)

# Directory components are not enough: `api.leads.test.ts` sits in `api/src/` and is
# a test file, which is how four of those six criticals got through. A convention
# every ecosystem shares is worth matching by name.
_TEST_FILENAME = re.compile(
    r"(?:\.|_|-)(?:test|spec|stories|fixture|mock)s?\.[^.]+$|^(?:test|conftest)_|_test\.[^.]+$",
    re.IGNORECASE,
)

# Literals that state in themselves that they are not real. Five of the six criticals
# said so in the value: `not-a-real-token`, `SUPER-SECRET-TOKEN`,
# `a-test-signing-secret-that-is-long-enough`, `test-secret-not-a-real-key`,
# `not-a-real-value`. A scanner that cannot read its own match is not weighing
# evidence, and six wrong criticals train the reader to skim the section that a real
# one will be in.
_OBVIOUS_DUMMY = re.compile(
    r"(?i)"
    r"not[-_ ]?a[-_ ]?real|not[-_ ]?real|"
    r"\bfake\b|\bdummy\b|\bplaceholder\b|\bredacted\b|\bsample\b|\bexample\b|"
    r"change[-_ ]?me|replace[-_ ]?me|your[-_ ]?|"
    r"\bxxx+\b|\bfoo\b|\bbar\b|\bbaz\b|\btodo\b|"
    r"^test[-_]|[-_]test$|[-_]test[-_]|"
    r"super[-_ ]?secret|"
    r"\bsecret\b.*\b(?:token|key|value)\b$|"
    r"process\.env|os\.environ|<[^>]+>|\.\.\."
)

_BASE64ISH = re.compile(r"^[A-Za-z0-9+/=_-]+$")

# The quoted value on the right of a `secret: "..."` assignment.
_QUOTED = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'")

_BUILD_ARTIFACTS = ("dist", "build", ".next", "__pycache__", "coverage", "target")


def _listing(command: str, root: Path, timeout: int = 60) -> Captured:
    """Full stdout of a listing command, undecided about what its failure means.

    Deliberately not `_run`: that truncates output to the last 8000 characters,
    which is right for a failing build's diagnostics and catastrophic for a file
    listing - it silently cut this repository's tracked files from several hundred
    to 117, and every scan downstream inherited the wrong file set.

    Returns the `Captured` rather than lines, because "this is not a git repo" and
    "git ls-files ran and we could not read it" need different answers from the
    caller and an empty list cannot tell them apart.
    """
    return run_command(command, root, timeout=timeout)


def _lines(command: str, root: Path, timeout: int = 60) -> list[str]:
    """Lines of a listing command's stdout, empty when it did not succeed."""
    captured = _listing(command, root, timeout=timeout)
    if not captured.ok:
        return []
    return [line for line in captured.stdout.splitlines() if line.strip()]


def _run(command: str, root: Path, timeout: int = 300) -> dict:
    """Run one check command as an argv list, never through a shell.

    `shell=True` here used to hand a string that can come from the audited
    repository's own `stack.json` straight to the shell. Running a project's
    declared checks is the point of this tool; letting a data file choose the
    shell syntax around them is not.
    """
    captured = run_command(command, root, timeout=timeout)
    if captured.error and captured.exit is None:
        return {"cmd": command, "exit": None, "error": captured.error, "output": ""}
    if captured.timed_out:
        return {"cmd": command, "exit": None, "timed_out": True, "output": ""}
    if not captured.captured:
        return {"cmd": command, "exit": captured.exit, "captured": False, "error": captured.error, "output": ""}
    # Scrubbed here rather than at each use: this output is persisted verbatim
    # into findings.json and report.md, and a failing build routinely prints a
    # token or a DSN.
    output = scrub_secrets(captured.combined)
    return {"cmd": command, "exit": captured.exit, "output": output[-8000:]}


def _capture_failure_reason(captured: Captured) -> str:
    """Why a command produced no usable output, in words a reader can act on."""
    if captured.timed_out:
        return f"`{captured.cmd}` timed out"
    if not captured.captured:
        return f"`{captured.cmd}` ran but its output could not be read: {captured.error}"
    if captured.error:
        return f"`{captured.cmd}` could not run: {captured.error}"
    return f"`{captured.cmd}` exited {captured.exit}"


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


def _is_test_path(path: Path, root: Path) -> bool:
    """Whether a path is test or example material rather than production source.

    Compared against the path *relative to the root*, not `path.parts`. `ctx.files`
    holds absolute paths, so matching components of the absolute path meant a
    checkout at `C:\\dev\\tests\\myrepo` skipped the entire secrets scan, and any
    file literally named `test` was skipped wherever it lived.
    """
    relative = relpath(path, root)
    parts = relative.lower().split("/")
    if set(parts[:-1]) & _SECRET_SKIP_PARTS:
        return True
    return bool(_TEST_FILENAME.search(path.name))


def _shannon(text: str) -> float:
    """Bits of entropy per character. English is low, a generated key is not."""
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _quoted_values(line: str) -> list[str]:
    return [match.group(1) or match.group(2) or "" for match in _QUOTED.finditer(line)]


def _looks_like_a_real_credential(line: str) -> bool:
    """Whether a `generic-assignment` match is plausibly a live credential.

    Only consulted for that one rule. The eight shape-specific patterns - `AKIA`,
    `sk_live_`, `xox[abprs]-` and the rest - are precise enough that second-guessing
    them would only weaken them, so they are never routed through here.
    """
    values = [value for value in _quoted_values(line) if len(value) >= 12]
    if not values:
        return True
    for value in values:
        if _OBVIOUS_DUMMY.search(value):
            continue
        # A dotted or slashed identifier is a resource name, not a value. This is the
        # `SECRET = "poolslip-report-link-secret"` case: a Secret Manager resource
        # name passed to `gcloud --secret=`, matching a whole repo of sibling names.
        if _shannon(value) < 3.5 and _BASE64ISH.match(value) is None:
            continue
        # Words separated by hyphens with no digits is how humans name things.
        if _shannon(value) < 3.5 and value.count("-") >= 2 and not any(c.isdigit() for c in value):
            continue
        if _shannon(value) < 3.0:
            continue
        return True
    return False


def run_secrets(ctx: Ctx, family) -> FamilyResult:
    findings: list[Finding] = []
    ceiling = getattr(family, "max_severity", "critical")
    for path in ctx.files:
        if path.suffix.lower() not in _SOURCE_SUFFIXES and path.name not in {".env", ".envrc"}:
            continue
        in_test = _is_test_path(path, ctx.root)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            for rule, pattern, label in _SECRET_PATTERNS:
                if not pattern.search(line):
                    continue
                if rule == "generic-assignment" and not _looks_like_a_real_credential(line):
                    break
                # Kept rather than dropped, at a severity that says so. Test material
                # is not where production credentials live, and a scanner that
                # reports six wrong criticals consumes the attention the seventh -
                # the real one - needs. Dropping it silently would trade one blind
                # spot for another.
                severity = "suggestion" if in_test else ceiling
                where = " (test or example material)" if in_test else ""
                findings.append(
                    Finding(
                        family=family.id,
                        rule=f"secret/{rule}",
                        severity=severity,
                        title=f"Possible {label} in {relpath(path, ctx.root)}{where}",
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
    listing = _listing("git ls-files", ctx.root)
    if not listing.ok:
        # This family is gated on `.git` existing, so a failure here is the listing
        # itself failing rather than "not a git repository". Reporting `passed` on a
        # file list nobody read is the exact shape of wrongness this audit exists to
        # avoid, and it did so with `files: 0` right there in the evidence.
        return FamilyResult(
            id=family.id,
            title=family.title,
            outcome="errored",
            reason=_capture_failure_reason(listing),
            applies_because="git repository",
            commands=[listing.as_command_record()],
        )
    paths = [line for line in listing.stdout.splitlines() if line.strip()]
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
    # `_dead_code_language` now gates on the same condition, so reaching this means
    # the registry and the runner disagree. Kept as a backstop, and deliberately
    # `errored` rather than `not-checked`: a mismatch between a family's own two
    # predicates is a bug in this file, not a fact about the repository.
    if not ctx.has("backend", "Python"):
        return FamilyResult(
            id=family.id,
            title=family.title,
            outcome="errored",
            reason="reached the Python dead-code runner with no Python detected; the family gate and its runner disagree",
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


def collect_files(root: Path) -> tuple[list[Path], str]:
    """Files git tracks, or a bounded walk when this is not a repository.

    Tracked-only is the right set and not just the faster one: it honours the
    project's own `.gitignore` without this script needing to know anything about
    it. On this repository that is what keeps `_unreleased/` - deliberately excluded
    from ruff, pre-commit, yamllint and every marketplace manifest - out of the audit
    as well, with no special case for it anywhere in here.

    Returns the files and a warning, empty when the set is the intended one. The
    walk is a correct answer for a directory that is not a repository and a wrong
    one when `git ls-files` was there and failed: the fallback does not read
    `.gitignore`, so every downstream scan silently widens to files the project
    excluded. Which of the two happened is not visible in the file list, so it is
    returned alongside it.
    """
    is_repo = (root / ".git").exists()
    listing = _listing("git ls-files", root)
    if listing.ok:
        tracked = [root / line for line in listing.stdout.splitlines() if line.strip()]
        if tracked:
            return [path for path in tracked if path.is_file()], ""
    if not is_repo:
        return scan_files(root), ""
    return scan_files(root), (
        f"file scope fell back to a directory walk because {_capture_failure_reason(listing)}. "
        "That walk does not honour .gitignore, so this audit may have read files the "
        "project excludes."
    )
