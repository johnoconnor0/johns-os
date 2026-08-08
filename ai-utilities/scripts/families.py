#!/usr/bin/env python3
"""Which checks this repository warrants, decided by the repository.

The skill this replaces ran eleven fixed phases and instructed the model to "execute
every phase in order... never skip a phase". Nine of the eleven assumed
Next.js/React/TypeScript/npm/Supabase. On a Python repository with no frontend and no
database that produced two honest N/A rows and nine phases of ceremony, and the one
real run on record simply routed around the instruction - which is the clearest
evidence available that prose does not hold this kind of line.

The same problem was solved once already in this repo: `create-data-model` assumed
Postgres on every project until dialect adapters replaced the assumption with a
lookup. This is that shape, applied to checks instead of engines - a frozen dataclass
per family, a registry, and two predicates that answer two different questions:

    applies_when   Is this check relevant to THIS repository?
                   No  -> not-applicable, with the reason.
    requires       Can it actually run here, right now?
                   No  -> not-checked, with the reason.

Keeping those separate is the whole point. "This repo has no database" and "the
database client is not installed" produce identical silence otherwise, and silence
reads as a pass.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# (relevant or runnable, reason)
Verdict = tuple[bool, str]


@dataclass
class Ctx:
    """Everything a family needs to decide about itself and then run."""

    root: Path
    stack: dict[str, Any]
    plan: dict[str, Any]
    files: list[Path]
    # Explicit opt-in to running command strings the audited repository chose.
    # See `commands_are_repo_supplied`.
    allow_untrusted_commands: bool = False

    @property
    def commands(self) -> dict[str, str]:
        return self.stack.get("test_commands", {}) or {}

    @property
    def commands_are_repo_supplied(self) -> bool:
        """True when `test_commands` came verbatim out of the audited repository.

        The `workspace` rung of the stack ladder reads
        `.project/.engineering/context/stack.json` from the repo under audit and
        treats it as authoritative. Every other rung derives its commands here,
        from file presence. Running a project's declared checks is what this tool
        is for; the distinction worth drawing is that a JSON file which looks
        inert gets to name the executable and its arguments.
        """
        return self.stack.get("detector") == "workspace"

    def has(self, key: str, *names: str) -> bool:
        values = {str(item).lower() for item in self.stack.get(key, []) or []}
        return any(name.lower() in values for name in names)

    def exists(self, *relative: str) -> bool:
        return any((self.root / item).exists() for item in relative)

    @property
    def frontend(self) -> bool:
        return bool(self.stack.get("frameworks")) or self.exists("package.json")

    @property
    def has_markdown(self) -> bool:
        return any(path.suffix.lower() == ".md" for path in self.files)


@dataclass(frozen=True)
class Family:
    """One cluster of checks, and the conditions under which it means anything."""

    id: str
    title: str
    applies_when: Callable[[Ctx], Verdict]
    requires: Callable[[Ctx], Verdict]
    # Set by checks.py at import time; kept out of the dataclass so the registry can
    # be read (by the docs generator, by tests) without importing the runners.
    route: str = ""
    max_severity: str = "warning"


def _always(_: Ctx) -> Verdict:
    return True, ""


def _runnable(_: Ctx) -> Verdict:
    return True, ""


def _on_path(tool: str) -> Callable[[Ctx], Verdict]:
    def check(_: Ctx) -> Verdict:
        if shutil.which(tool):
            return True, ""
        return False, f"`{tool}` is not on PATH"

    return check


def _command(key: str) -> Callable[[Ctx], Verdict]:
    def check(ctx: Ctx) -> Verdict:
        if ctx.commands.get(key):
            return True, f"stack.test_commands.{key}"
        return False, f"the detected stack declares no {key} command"

    return check


def _has_database(ctx: Ctx) -> Verdict:
    if ctx.stack.get("database"):
        return True, f"stack.database: {', '.join(ctx.stack['database'])}"
    if ctx.exists("supabase/migrations", "migrations", "db/migrate", "prisma/schema.prisma"):
        return True, "migration sources on disk"
    return False, "no database detected and no migration sources on disk"


def _has_interfaces(ctx: Ctx) -> Verdict:
    if ctx.frontend and (ctx.stack.get("backend") or ctx.stack.get("database")):
        return True, "a frontend and a backend or database were both detected"
    return False, "needs both a frontend and a backend or database; this repo has one side only"


def _has_package_manager(ctx: Ctx) -> Verdict:
    manager = ctx.stack.get("package_manager")
    if manager:
        return True, f"stack.package_manager: {manager}"
    return False, "no package manager detected"


_AUDITORS = {"npm": "npm", "pnpm": "pnpm", "yarn": "yarn", "python": "pip-audit", "cargo": "cargo", "go": "go"}


def _auditor_available(ctx: Ctx) -> Verdict:
    tool = _AUDITORS.get(str(ctx.stack.get("package_manager") or ""))
    if not tool:
        return False, f"no dependency auditor known for package manager {ctx.stack.get('package_manager')!r}"
    if not shutil.which(tool):
        return False, f"`{tool}` is not on PATH"
    return True, ""


def _is_git_repo(ctx: Ctx) -> Verdict:
    if (ctx.root / ".git").exists():
        return True, ""
    return False, "not a git repository, so tracked-vs-untracked cannot be established"


def _plan_parsed(ctx: Ctx) -> Verdict:
    if ctx.plan.get("parsed_by"):
        return True, f"plan parsed by {ctx.plan['parsed_by']}"
    return False, "no plan could be parsed"


def _dead_code_language(ctx: Ctx) -> Verdict:
    """Only Python, because only the Python arm exists.

    This used to admit any Node tree as well, and the runner then refused everything
    but Python - so on a TypeScript repository the family passed the relevance gate
    and reported `not-checked`, which says "this applies here but could not run" when
    the truth is "this does not apply here". The registry keeps two predicates
    precisely so those two do not collapse into each other, and a promise the runner
    cannot keep is the one way the gate can still tell the wrong story.
    """
    if ctx.has("backend", "Python"):
        return True, "Python sources were detected"
    return False, "dead-code analysis is only implemented for Python, and no Python was detected"


def _markdown_present(ctx: Ctx) -> Verdict:
    if ctx.has_markdown:
        return True, "markdown documents are present"
    return False, "no markdown documents"


REGISTRY: tuple[Family, ...] = (
    Family(
        id="plan-inventory",
        title="Plan completion",
        applies_when=_plan_parsed,
        requires=_runnable,
        route="engineering-lifecycle:create-engineering-plan",
        max_severity="critical",
    ),
    Family(
        id="unfinished-markers",
        title="Unfinished work markers",
        applies_when=_always,
        requires=_runnable,
        route="engineering-lifecycle:repo-hygiene-maintainer",
    ),
    Family(
        id="static-analysis",
        title="Static analysis",
        applies_when=lambda ctx: (
            (True, "stack.test_commands has lint or typecheck")
            if (ctx.commands.get("lint") or ctx.commands.get("typecheck"))
            else (False, "the detected stack declares no lint or typecheck command")
        ),
        requires=_runnable,
        route="engineering-lifecycle:backend-engineer",
    ),
    Family(
        id="tests",
        title="Test suite",
        applies_when=lambda ctx: _command("unit")(ctx),
        requires=_runnable,
        route="engineering-lifecycle:qa-test-strategist",
        max_severity="critical",
    ),
    Family(
        id="build",
        title="Build",
        applies_when=lambda ctx: _command("build")(ctx),
        requires=_runnable,
        route="engineering-lifecycle:devops-release-engineer",
        max_severity="critical",
    ),
    Family(
        id="secrets",
        title="Secret exposure",
        applies_when=_always,
        requires=_runnable,
        route="engineering-lifecycle:security-reviewer",
        max_severity="critical",
    ),
    Family(
        id="dependency-audit",
        title="Dependency vulnerabilities",
        applies_when=_has_package_manager,
        requires=_auditor_available,
        route="engineering-lifecycle:security-reviewer",
        max_severity="critical",
    ),
    Family(
        id="repo-hygiene",
        title="Repository hygiene",
        applies_when=_always,
        requires=_is_git_repo,
        route="engineering-lifecycle:update-repo-hygiene",
    ),
    Family(
        id="dead-code",
        title="Dead code",
        applies_when=_dead_code_language,
        requires=_runnable,
        route="engineering-lifecycle:repo-hygiene-maintainer",
    ),
    Family(
        id="data-layer",
        title="Data layer",
        applies_when=_has_database,
        requires=_runnable,
        route="engineering-lifecycle:database-engineer",
        max_severity="critical",
    ),
    Family(
        id="interface-alignment",
        title="Interface alignment",
        applies_when=_has_interfaces,
        requires=_runnable,
        route="engineering-lifecycle:api-contract-reviewer",
    ),
    Family(
        id="docs-references",
        title="Documentation references",
        applies_when=_markdown_present,
        requires=_runnable,
        route="engineering-lifecycle:repo-hygiene-maintainer",
    ),
    Family(
        id="plan-drift",
        title="Plan drift",
        applies_when=_plan_parsed,
        requires=_runnable,
        route="engineering-lifecycle:create-engineering-plan",
    ),
)

BY_ID: dict[str, Family] = {family.id: family for family in REGISTRY}


def registered_ids() -> list[str]:
    return [family.id for family in REGISTRY]
