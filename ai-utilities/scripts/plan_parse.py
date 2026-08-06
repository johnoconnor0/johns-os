#!/usr/bin/env python3
"""Turn a plan document into a checkable inventory of discrete work items.

The audit used to run a fixed list of eleven phases against every repository,
whether or not the plan mentioned any of them. Replacing that with something
plan-derived needs one thing first: a reliable answer to "what did the plan
actually ask for".

No single pattern gives that. `ACTION_RE` - the checklist form the rest of the
lifecycle tooling uses - is worth trying first because it is unambiguous, but the
one real plan on record in this repository stated its sixteen items as *numbered
headings* (`### 1.1 ...`), and a checkbox-only parser would have found zero items
in it and reported a complete audit of nothing.

So: a cascade, tried in order of how unambiguous each form is, recording which one
answered. And when none of them match, the correct behaviour is to stop and ask,
never to invent an inventory - an audit against an imagined plan is worse than no
audit, because it produces a verdict.

`ACTION_RE` is imported from the Engineering Lifecycle plugin when it is installed
and vendored otherwise, for the same reason `stack_probe.py` has a ladder: the two
plugins install separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audit_common import parse_front_matter, relpath

# Vendored from engineering-lifecycle/scripts/eng_common.py, which is the source of
# truth. Kept byte-identical on purpose; the two must agree about what a plan item is.
ACTION_RE = re.compile(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+(?P<title>.+)$")

_NUMBERED_HEADING = re.compile(r"^(#{2,4})\s+(\d+(?:\.\d+)*)[.)]?\s+(.+?)\s*$")
_ORDERED_LIST = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]\s+(.+?)\s*$")
_PHASE_SECTION = re.compile(r"^#{2,4}\s+(?:Phase|Step|Slice|Milestone|Wave)\s+(\S+?)[:.)]?\s+(.+?)\s*$", re.IGNORECASE)
_ANY_HEADING = re.compile(r"^#{1,6}\s")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")

# Plan documents this skill will look for when the user names a directory.
PLAN_CANDIDATES = (
    "PLAN.md",
    "TASKS.md",
    "TODO.md",
    "IMPLEMENTATION-PLAN.md",
    "implementation-plan.md",
    "engineering-plan.md",
    "task-breakdown.md",
    "requirements.md",
)

# The five statuses a plan item can end in. `unverifiable` is new and is the join
# between this skill and the reference checker: an item naming a file that does not
# exist cannot be called complete OR incomplete on the evidence available, and
# collapsing that into either one is a claim the audit has not earned.
ITEM_STATUSES = ("complete", "partial", "not-started", "deviates", "unverifiable")


@dataclass
class PlanItem:
    id: str
    title: str
    source: str
    extractor: str
    body: str = ""
    mentions: list[str] = field(default_factory=list)
    status: str = "not-started"
    reason: str = ""
    verified_by: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "extractor": self.extractor,
            "mentions": self.mentions,
            "status": self.status,
            "reason": self.reason,
            "verified_by": self.verified_by,
        }


def find_plan(root: Path) -> Path | None:
    """The most likely plan document under `root`, or None.

    Searched in a fixed order of specificity, and the lifecycle workspace before the
    repository root, because a generated engineering plan is a better inventory than
    a README that happens to contain a numbered list.
    """
    docs = root / ".project" / "docs" / "engineering"
    if docs.is_dir():
        for name in ("engineering-plan.md", "task-breakdown.md", "implementation-plan.md"):
            found = sorted(docs.rglob(name))
            if found:
                return found[-1]
    for name in PLAN_CANDIDATES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _mentions(text: str) -> list[str]:
    """Backticked tokens in an item's body: the things it claims will exist."""
    seen: list[str] = []
    for token in _INLINE_CODE.findall(text):
        token = token.strip()
        if token and token not in seen and len(token) < 200:
            seen.append(token)
    return seen


def _bodies(lines: list[str], starts: list[int]) -> list[str]:
    """Text belonging to each item: from its own line to the next item's."""
    bounds = starts + [len(lines)]
    return ["\n".join(lines[bounds[index] : bounds[index + 1]]) for index in range(len(starts))]


def _drop_group_headings(items: list[PlanItem]) -> list[PlanItem]:
    """Remove numbered headings that only contain other numbered headings.

    `## 1. Data layer` above `### 1.1 ...` and `### 1.2 ...` is a grouping, not a
    task. Counting it as one inflates the denominator and produces an item nothing
    can ever be verified against.
    """
    ids = {item.id for item in items}
    return [item for item in items if not any(other != item.id and other.startswith(item.id + ".") for other in ids)]


def _extract_front_matter(text: str, source: str) -> list[PlanItem]:
    front, _ = parse_front_matter(text)
    raw = front.get("tasks") or front.get("items")
    if not isinstance(raw, list) or not raw:
        return []
    return [
        PlanItem(id=f"{index:02d}", title=str(entry).strip(), source=f"{source}:1", extractor="front-matter")
        for index, entry in enumerate(raw, start=1)
        if str(entry).strip()
    ]


def _extract_checkboxes(lines: list[str], source: str) -> tuple[list[PlanItem], list[int]]:
    items: list[PlanItem] = []
    starts: list[int] = []
    for index, line in enumerate(lines):
        match = ACTION_RE.match(line)
        if not match:
            continue
        items.append(
            PlanItem(
                id=f"{len(items) + 1:02d}",
                title=match.group("title").strip(),
                source=f"{source}:{index + 1}",
                extractor="action-items",
                status="complete" if match.group("state").lower() == "x" else "not-started",
            )
        )
        starts.append(index)
    return items, starts


def _extract_numbered_headings(lines: list[str], source: str) -> tuple[list[PlanItem], list[int]]:
    items: list[PlanItem] = []
    starts: list[int] = []
    for index, line in enumerate(lines):
        match = _NUMBERED_HEADING.match(line)
        if not match:
            continue
        items.append(
            PlanItem(
                id=match.group(2),
                title=match.group(3).strip(),
                source=f"{source}:{index + 1}",
                extractor="numbered-headings",
            )
        )
        starts.append(index)
    return items, starts


def _extract_phase_sections(lines: list[str], source: str) -> tuple[list[PlanItem], list[int]]:
    items: list[PlanItem] = []
    starts: list[int] = []
    for index, line in enumerate(lines):
        match = _PHASE_SECTION.match(line)
        if not match:
            continue
        items.append(
            PlanItem(
                id=match.group(1),
                title=match.group(2).strip(),
                source=f"{source}:{index + 1}",
                extractor="phase-sections",
            )
        )
        starts.append(index)
    return items, starts


def _extract_ordered_list(lines: list[str], source: str) -> tuple[list[PlanItem], list[int]]:
    items: list[PlanItem] = []
    starts: list[int] = []
    for index, line in enumerate(lines):
        if _ANY_HEADING.match(line):
            continue
        match = _ORDERED_LIST.match(line)
        if not match:
            continue
        items.append(
            PlanItem(
                id=match.group(1),
                title=match.group(2).strip(),
                source=f"{source}:{index + 1}",
                extractor="ordered-list",
            )
        )
        starts.append(index)
    return items, starts


# A checklist means exactly one thing, so it wins outright when present.
_UNAMBIGUOUS = (("action-items", _extract_checkboxes),)

# Both of these read section headings, and on a real plan both usually match: a
# document with `## Wave 1 - Blockers` above `### 1.1 ...` matches phase-sections on
# the three waves and numbered-headings on the sixteen tasks. Taking them in a fixed
# order picked the three, which is the plan's table of contents rather than its
# inventory. They compete on count instead, because between two readings of the same
# headings the finer one is the inventory.
_HEADING_EXTRACTORS = (
    ("numbered-headings", _extract_numbered_headings),
    ("phase-sections", _extract_phase_sections),
)

# Last resort. A numbered list in prose might be steps, might be options, might be a
# worked example, so it only runs when no heading structure was found at all.
_FALLBACK = (("ordered-list", _extract_ordered_list),)

# Below this, a match is more likely to be incidental prose than a real inventory.
_MIN_ITEMS = 2


def parse_plan(path: Path, root: Path) -> dict[str, Any]:
    """The plan's items, and which extractor produced them.

    Returns `parsed_by: None` with an empty list when nothing matched. The caller
    must stop and ask rather than proceeding: there is no honest audit of a plan
    that could not be read.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    source = relpath(path, root)
    lines = text.splitlines()

    front_items = _extract_front_matter(text, source)
    if front_items:
        for item in front_items:
            item.mentions = _mentions(item.title)
        return _result(source, "front-matter", front_items)

    def attempt(name: str, extractor: Any) -> tuple[str, list[PlanItem], list[int]] | None:
        items, starts = extractor(lines, source)
        if name == "numbered-headings":
            keep = {item.id for item in _drop_group_headings(items)}
            pairs = [(item, start) for item, start in zip(items, starts, strict=True) if item.id in keep]
            items = [item for item, _ in pairs]
            starts = [start for _, start in pairs]
        return (name, items, starts) if len(items) >= _MIN_ITEMS else None

    for name, extractor in _UNAMBIGUOUS:
        won = attempt(name, extractor)
        if won:
            return _finish(source, won, lines)

    heading_attempts = [won for name, extractor in _HEADING_EXTRACTORS if (won := attempt(name, extractor))]
    if heading_attempts:
        return _finish(source, max(heading_attempts, key=lambda won: len(won[1])), lines)

    for name, extractor in _FALLBACK:
        won = attempt(name, extractor)
        if won:
            return _finish(source, won, lines)

    return _result(source, None, [])


def _finish(source: str, won: tuple[str, list[PlanItem], list[int]], lines: list[str]) -> dict[str, Any]:
    name, items, starts = won
    for item, body in zip(items, _bodies(lines, starts), strict=True):
        item.body = body
        item.mentions = _mentions(body)
    return _result(source, name, items)


def _result(source: str, parsed_by: str | None, items: list[PlanItem]) -> dict[str, Any]:
    return {
        "path": source,
        "parsed_by": parsed_by,
        "item_count": len(items),
        "items": items,
    }


def mark_unverifiable(items: list[PlanItem], unresolved: set[str]) -> None:
    """Flag items whose stated artefacts do not exist.

    An item promising `scripts/foo.py` when nothing resolves that name has not been
    shown complete and has not been shown incomplete. Saying so is the point: the
    old skill had no way to express it and had to pick one.
    """
    for item in items:
        missing = [token for token in item.mentions if token in unresolved]
        if not missing:
            continue
        item.status = "unverifiable"
        item.reason = "names " + ", ".join(f"`{token}`" for token in missing[:3]) + ", which does not resolve"
