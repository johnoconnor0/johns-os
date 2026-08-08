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

_FENCE = re.compile(r"^\s*(?:```|~~~)")
_TABLE_ROW = re.compile(r"^\s*\|(?P<body>.*)\|\s*$")
# `| --- | :--: |`, the row that makes the line above it a header.
_TABLE_RULE = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
# The first cell of a plan row: a number, a dotted number, or an issue key. This is
# the discriminator that keeps `| Option | Pros | Cons |` from becoming an inventory -
# an ordered work table numbers its rows and a comparison table does not.
_ROW_ID = re.compile(r"^(?:(?P<num>\d+(?:\.\d+)*)[.)]?|(?P<key>[A-Z][A-Z0-9]{1,9}-\d+))$")
# Header cells that name the column holding the work itself.
_TITLE_HEADERS = (
    "task",
    "title",
    "item",
    "work",
    "description",
    "deliverable",
    "change",
    "step",
    "name",
    "summary",
    "what",
)

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


def _fenced(lines: list[str]) -> set[int]:
    """Indices of lines inside a fenced code block.

    A worked example in a code fence is not the plan, and every extractor here
    matches line shapes rather than parsing markdown, so without this a numbered
    list demonstrating something becomes the inventory.
    """
    inside: set[int] = set()
    open_fence = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            open_fence = not open_fence
            inside.add(index)
            continue
        if open_fence:
            inside.add(index)
    return inside


def _cells(line: str) -> list[str]:
    match = _TABLE_ROW.match(line)
    if match is None:
        return []
    return [cell.strip() for cell in match.group("body").split("|")]


def _title_column(header: list[str]) -> int:
    """Which column holds the work, given the header cells."""
    for index, cell in enumerate(header):
        if any(word in cell.lower() for word in _TITLE_HEADERS):
            return index
    # No named column: the first cell is the id, so the one after it is the work.
    return 1 if len(header) > 1 else 0


def _table_blocks(lines: list[str]) -> list[tuple[int, list[str], list[int]]]:
    """Every markdown table: its header cells and the line indices of its body rows.

    Returns `(header_index, header_cells, body_row_indices)` per table.
    """
    fenced = _fenced(lines)
    blocks: list[tuple[int, list[str], list[int]]] = []
    index = 0
    while index < len(lines) - 1:
        if index in fenced or not _TABLE_ROW.match(lines[index]) or not _TABLE_RULE.match(lines[index + 1]):
            index += 1
            continue
        header = _cells(lines[index])
        body: list[int] = []
        cursor = index + 2
        while cursor < len(lines) and cursor not in fenced and _TABLE_ROW.match(lines[cursor]):
            body.append(cursor)
            cursor += 1
        blocks.append((index, header, body))
        index = cursor
    return blocks


def _extract_table(lines: list[str], source: str) -> tuple[list[PlanItem], list[int]]:
    """Plan items stated as rows of a markdown table.

    A normal way to write a build order, and the one this extractor was added for:
    a plan whose fifteen work items lived in two tables parsed as six, because the
    only structure any extractor could see was an unrelated ordered list elsewhere
    in the document.

    A table qualifies only when its rows are *numbered* - a bare number, a dotted
    number or an issue key in the first cell. That is what separates an ordered
    inventory from a comparison table, which is the shape most likely to be here
    for some other reason.
    """
    items: list[PlanItem] = []
    starts: list[int] = []
    for _header_index, header, body in _table_blocks(lines):
        rows = [(row, _cells(lines[row])) for row in body]
        numbered = [(row, cells) for row, cells in rows if cells and _ROW_ID.match(cells[0])]
        # Most of the rows must be numbered, or this is a table that merely starts
        # with something numeric-looking.
        if not numbered or len(numbered) * 2 < len(rows):
            continue
        column = _title_column(header)
        for row, cells in numbered:
            match = _ROW_ID.match(cells[0])
            title = cells[column].strip() if column < len(cells) else ""
            if not title:
                title = next((cell for cell in cells[1:] if cell), "")
            if not title:
                continue
            items.append(
                PlanItem(
                    id=match.group("num") or match.group("key"),
                    # The rest of the row is where the issue key and the estimate
                    # live, and `_mentions` reads backticks out of it.
                    title=title,
                    source=f"{source}:{row + 1}",
                    extractor="table",
                    body=" | ".join(cells),
                )
            )
            starts.append(row)
    return items, starts


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
    fenced = _fenced(lines)
    for index, line in enumerate(lines):
        if _ANY_HEADING.match(line) or index in fenced:
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

# These read the document's declared structure, and on a real plan more than one
# usually matches: a document with `## Wave 1 - Blockers` above `### 1.1 ...` matches
# phase-sections on the three waves and numbered-headings on the sixteen tasks. Taking
# them in a fixed order picked the three, which is the plan's table of contents rather
# than its inventory. They compete on count instead, because between two readings of
# the same document the finer one is the inventory.
#
# `table` belongs in this tier and not in the fallback below: a numbered table is a
# deliberate statement of a build order, not an incidental numbered list. Putting it
# here is what fixes the case this was added for - fifteen table rows outranking a
# six-step staging checklist that happened to be the only thing an extractor could see.
_STRUCTURED_EXTRACTORS = (
    ("numbered-headings", _extract_numbered_headings),
    ("phase-sections", _extract_phase_sections),
    ("table", _extract_table),
)

# Last resort. A numbered list in prose might be steps, might be options, might be a
# worked example, so it only runs when no declared structure was found at all.
_FALLBACK = (("ordered-list", _extract_ordered_list),)

# Below this, a match is more likely to be incidental prose than a real inventory.
_MIN_ITEMS = 2


def _sections(lines: list[str]) -> list[tuple[int, int, str]]:
    """`(start, end, heading)` for each heading's span, plus the preamble above the first."""
    heads = [index for index, line in enumerate(lines) if _ANY_HEADING.match(line)]
    if not heads:
        return [(0, len(lines), "(document)")]
    spans: list[tuple[int, int, str]] = []
    if heads[0] > 0:
        spans.append((0, heads[0], "(preamble)"))
    for position, start in enumerate(heads):
        end = heads[position + 1] if position + 1 < len(heads) else len(lines)
        spans.append((start, end, lines[start].lstrip("# ").strip()))
    return spans


def _work_rows(lines: list[str], start: int, end: int, fenced: set[int]) -> int:
    """How many lines in a span are shaped like a statement of work."""
    found = 0
    for index in range(start, end):
        if index in fenced:
            continue
        line = lines[index]
        if ACTION_RE.match(line) or _ORDERED_LIST.match(line):
            found += 1
            continue
        cells = _cells(line)
        if cells and _ROW_ID.match(cells[0]):
            found += 1
    return found


def _coverage(lines: list[str], counts: dict[str, int], starts: list[int]) -> dict[str, Any]:
    """What each extractor saw, and which sections the winner did not account for.

    The missing signal in the failure this was built for. A plan stated in tables
    parsed as six items from an unrelated ordered list, and nothing in the output
    said so - the report simply asserted "4 of 6 plan items complete (67%)" over a
    denominator that should have been 21. A partial parse was indistinguishable from
    a complete one.
    """
    fenced = _fenced(lines)
    claimed = set(starts)
    candidates: list[str] = []
    unparsed: list[str] = []
    unaccounted = 0
    for start, end, heading in _sections(lines):
        rows = _work_rows(lines, start, end, fenced)
        if not rows:
            continue
        candidates.append(heading)
        if any(start <= item < end for item in claimed):
            continue
        unparsed.append(heading)
        unaccounted += rows
    return {
        "extractor_counts": counts,
        "candidate_sections": len(candidates),
        "sections_parsed": len(candidates) - len(unparsed),
        "unparsed_sections": unparsed,
        "unaccounted_rows": unaccounted,
        # Reported whenever it happens, but only enough unaccounted work to move a
        # denominator withdraws the percentage. One stray numbered line in a section
        # of prose is worth a note and is not worth suppressing a measurement over -
        # a warning that fires on every document is one nobody reads.
        "confident": unaccounted < _MIN_ITEMS,
    }


def parse_plan(path: Path, root: Path) -> dict[str, Any]:
    """The plan's items, which extractor produced them, and how much it accounted for.

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
        return _result(source, "front-matter", front_items, {"front-matter": len(front_items)}, [], lines)

    # Every extractor runs, every count is kept - including the ones that lose. They
    # were computed and discarded before, which is why nothing could report how much
    # of the document the winning reading actually accounted for. Running the whole
    # set costs one regex pass each and is what makes `extractor_counts` mean
    # something: "the winner found 6 and another extractor found 15" is the sentence
    # that would have caught the misparse this was built for.
    attempts: dict[str, tuple[str, list[PlanItem], list[int]]] = {}
    counts: dict[str, int] = {}
    for name, extractor in _UNAMBIGUOUS + _STRUCTURED_EXTRACTORS + _FALLBACK:
        items, starts = extractor(lines, source)
        if name == "numbered-headings":
            keep = {item.id for item in _drop_group_headings(items)}
            pairs = [(item, start) for item, start in zip(items, starts, strict=True) if item.id in keep]
            items = [item for item, _ in pairs]
            starts = [start for _, start in pairs]
        counts[name] = len(items)
        # Below the floor, a match is more likely incidental prose than an inventory.
        if len(items) >= _MIN_ITEMS:
            attempts[name] = (name, items, starts)

    won: tuple[str, list[PlanItem], list[int]] | None = None
    # A checklist means exactly one thing, so it wins outright when present.
    for name, _extractor in _UNAMBIGUOUS:
        won = won or attempts.get(name)
    if won is None:
        # Between competing readings of the declared structure, the finer one is the
        # inventory and the coarser one is its table of contents.
        structured = [attempts[name] for name, _ in _STRUCTURED_EXTRACTORS if name in attempts]
        if structured:
            won = max(structured, key=lambda found: len(found[1]))
    if won is None:
        for name, _extractor in _FALLBACK:
            won = won or attempts.get(name)

    if won is None:
        return _result(source, None, [], counts, [], lines)
    return _finish(source, won, lines, counts)


def _finish(
    source: str,
    won: tuple[str, list[PlanItem], list[int]],
    lines: list[str],
    counts: dict[str, int],
) -> dict[str, Any]:
    name, items, starts = won
    for item, body in zip(items, _bodies(lines, starts), strict=True):
        # A table row is its own body; the span to the next row would swallow the
        # rest of the table.
        item.body = item.body or body
        item.mentions = _mentions(item.body)
    return _result(source, name, items, counts, starts, lines)


def _result(
    source: str,
    parsed_by: str | None,
    items: list[PlanItem],
    counts: dict[str, int] | None = None,
    starts: list[int] | None = None,
    lines: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "path": source,
        "parsed_by": parsed_by,
        "item_count": len(items),
        "items": items,
        "coverage": _coverage(lines or [], counts or {}, starts or []),
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
