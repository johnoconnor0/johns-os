#!/usr/bin/env python3
"""The durable store for questions the assistant needs a human to answer.

Split out of quality_tools.py. Before this store existed, questions lived only as
free-text `## Open Questions` headings inside individual artifacts: never
aggregated, never statused, and never surfaced again after the turn that wrote
them.

Storage is `.project/.engineering/questions/`, with a JSON store beside a
human-readable digest so the folder is useful without a tool.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from eng_common import (
    artifact_roots,
    engineering_root,
    now_iso,
    parse_front_matter,
    read_json_safe,
    relpath,
    workspace_exists,
    write_json,
    write_text,
)

# --- open questions --------------------------------------------------------
#
# One durable store for every question the assistant needs a human to answer,
# whatever raised it. Before this existed, questions lived only as free-text
# `## Open Questions` headings inside individual artifacts: never aggregated,
# never statused, never surfaced again after the turn that wrote them. Council
# questions had no destination at all, and the AskUserQuestion hook discarded
# both the question and the answer.

QUESTION_KINDS = ("clarification", "council", "artifact", "general")
QUESTION_STATUSES = ("open", "answered", "deferred", "obsolete")
_QUESTIONS_FILE = ("questions", "open-questions.json")
_QUESTIONS_DIGEST = ("questions", "open-questions.md")
_OPEN_QUESTIONS_HEADING = re.compile(r"^#{1,6}\s+open\s+questions\s*$", re.IGNORECASE)
_QUESTION_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(?:\[[ xX]\]\s*)?(.+?)\s*$")


def questions_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_QUESTIONS_FILE)


def render_questions_digest(payload: dict[str, Any]) -> str:
    """A human-readable view beside the machine one.

    The store exists so questions stop getting lost, which only works if a
    person can open the folder and read them without a tool.
    """
    entries = payload.get("open_questions", [])
    lines = ["# Open Questions", "", f"Generated at {payload.get('generated_at', '')}.", ""]
    for status in QUESTION_STATUSES:
        group = [entry for entry in entries if entry.get("status") == status]
        if not group:
            continue
        lines.append(f"## {status.title()} ({len(group)})")
        lines.append("")
        for entry in group:
            source = entry.get("source_artifact") or entry.get("skill") or entry.get("kind", "general")
            lines.append(f"- **{entry['question']}**")
            lines.append(f"  - id: `{entry['id']}` | kind: {entry.get('kind', 'general')} | source: {source}")
            if entry.get("options"):
                lines.append(f"  - options: {', '.join(entry['options'])}")
            if entry.get("answer"):
                lines.append(f"  - answer: {entry['answer']}")
        lines.append("")
    if not entries:
        lines.append("None recorded.")
        lines.append("")
    return "\n".join(lines)


def question_id(question: str, source: str = "") -> str:
    """Stable id so re-scanning an artifact updates rather than duplicates."""
    normalized = " ".join(question.lower().split())
    return "q-" + hashlib.sha1(f"{source}|{normalized}".encode()).hexdigest()[:12]


def load_open_questions(root: Path) -> dict[str, Any]:
    # `read_json_safe`, not `read_json`: seven PostToolUse hooks write into this
    # tree concurrently and a session can end mid-write, so a truncated store is a
    # state this reaches rather than a state it can refuse. Raising here took down
    # the UserPromptSubmit hook on every subsequent turn - which is to say the
    # whole plugin - and nothing left in the plugin could report or repair it.
    data = read_json_safe(questions_path(root))
    entries = data.get("open_questions")
    return {"generated_at": data.get("generated_at", now_iso()), "open_questions": entries if entries else []}


def record_questions(root: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert questions by id, preserving any answer already recorded.

    Idempotent on purpose: the artifact scanner re-reads the same
    `## Open Questions` sections on every sync, and re-asking a question the
    human already answered would make the store worse than useless.
    """
    store = load_open_questions(root)
    existing = {entry["id"]: entry for entry in store["open_questions"] if entry.get("id")}
    for entry in entries:
        record = {
            "id": entry.get("id") or question_id(entry.get("question", ""), entry.get("source_artifact") or ""),
            "question": entry.get("question", "").strip(),
            "kind": entry.get("kind") if entry.get("kind") in QUESTION_KINDS else "general",
            "status": entry.get("status") if entry.get("status") in QUESTION_STATUSES else "open",
            "asked_at": entry.get("asked_at") or now_iso(),
        }
        for optional in ("options", "answer", "answered_at", "initiative_id", "skill", "source_artifact"):
            if entry.get(optional) is not None:
                record[optional] = entry[optional]
        if not record["question"]:
            continue
        previous = existing.get(record["id"])
        if previous:
            # An answered question stays answered no matter how often its source
            # artifact is rescanned.
            record["asked_at"] = previous.get("asked_at", record["asked_at"])
            if previous.get("status") != "open":
                record["status"] = previous["status"]
                for carried in ("answer", "answered_at"):
                    if previous.get(carried) is not None:
                        record[carried] = previous[carried]
        existing[record["id"]] = record

    payload = {
        "generated_at": now_iso(),
        "open_questions": _sorted_questions(existing.values()),
    }
    if workspace_exists(root):
        write_json(questions_path(root), payload)
        write_text(engineering_root(root).joinpath(*_QUESTIONS_DIGEST), render_questions_digest(payload))
    return payload


def _sorted_questions(entries: Any) -> list[dict[str, Any]]:
    """Open questions first, then by when they were asked.

    Extracted so `answer_question` re-sorts on write the same way `record_questions`
    does. It did not, so answering a question left the store in an order that no
    longer matched its own invariant - and the next substring match walked that
    stale order.
    """
    return sorted(entries, key=lambda item: (item.get("status") != "open", item.get("asked_at", "")))


def answer_question(
    root: Path,
    target: str,
    answer: str,
    status: str = "answered",
    allow_answered: bool = False,
) -> dict[str, Any]:
    """Resolve a question by exact id, or by a substring that matches exactly one open question.

    Three defects lived on the single condition this replaces
    (`entry.id == target or needle and needle in entry.question`):

    1. The docstring promised a *unique* substring, but the loop stopped at the
       first hit. Three of this repo's questions contain the word "registry"; a
       caller answering by substring silently resolved whichever sorted first and
       was told it had succeeded.
    2. The id test and the substring test were OR'd inside one iteration, so an
       earlier entry whose *text* happened to contain an id-shaped token beat the
       later entry whose `id` genuinely equalled the target.
    3. There was no status filter, so an already-answered question could be
       silently re-answered and its recorded answer overwritten - while the failure
       path still reported "no *open* question matched". That contradicted the
       invariant `record_questions` maintains at every rescan, and it was live
       rather than theoretical: with every entry in the store already answered, the
       next call was guaranteed to clobber one.

    Exact ids are now resolved in a full first pass. Substring matching is a
    fallback, restricted to open questions, and ambiguity is an error that returns
    the candidates rather than a guess that returns success.
    """
    store = load_open_questions(root)
    entries = store["open_questions"]
    needle = target.lower().strip()

    matched = next((entry for entry in entries if entry.get("id") == target), None)
    if matched is None and needle:
        pool = entries if allow_answered else [entry for entry in entries if entry.get("status") == "open"]
        candidates = [entry for entry in pool if needle in entry.get("question", "").lower()]
        if len(candidates) > 1:
            return {
                "updated": False,
                "reason": f"{target!r} matches {len(candidates)} questions; pass an exact id",
                "candidates": [{"id": entry["id"], "question": entry["question"]} for entry in candidates],
            }
        matched = candidates[0] if candidates else None
        if matched is None and not allow_answered:
            # Distinguish "there is no such question" from "there is, and it is
            # already answered". Reporting the first for the second is what the
            # original made impossible to notice.
            resolved = [entry for entry in entries if needle in entry.get("question", "").lower()]
            if resolved:
                names = ", ".join(f"{entry['id']} ({entry.get('status')})" for entry in resolved)
                return {
                    "updated": False,
                    "reason": f"{target!r} matches only questions that are already answered: {names}. "
                    "Pass --allow-answered to overwrite one.",
                    "candidates": [{"id": entry["id"], "question": entry["question"]} for entry in resolved],
                }
    if matched is None:
        scope = "question" if allow_answered else "open question"
        return {"updated": False, "reason": f"no {scope} matched {target!r}"}
    if matched.get("status") != "open" and not allow_answered:
        return {
            "updated": False,
            "reason": f"{matched['id']} is already {matched.get('status')}; pass --allow-answered to overwrite",
            "question": matched,
        }

    matched["status"] = status if status in QUESTION_STATUSES else "answered"
    matched["answer"] = answer
    matched["answered_at"] = now_iso()
    store["open_questions"] = _sorted_questions(entries)
    store["generated_at"] = now_iso()
    if workspace_exists(root):
        write_json(questions_path(root), store)
        write_text(engineering_root(root).joinpath(*_QUESTIONS_DIGEST), render_questions_digest(store))
    return {"updated": True, "id": matched["id"], "question": matched}


def extract_open_questions(text: str) -> list[str]:
    """List items under an `## Open Questions` heading.

    Fourteen artifact templates carry that heading and `validate-artifact.py`
    requires it, so the questions are already being written. They were simply
    never read back out.
    """
    questions: list[str] = []
    collecting = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.lstrip().startswith("#"):
            collecting = bool(_OPEN_QUESTIONS_HEADING.match(line.strip()))
            continue
        if not collecting:
            continue
        match = _QUESTION_ITEM.match(line)
        if match:
            candidate = match.group(1).strip()
            # Template placeholders are not questions anyone can answer.
            if candidate and not candidate.lower().startswith(("todo", "tbd", "none", "n/a", "<")):
                questions.append(candidate)
    return questions


def scan_artifact_questions(root: Path) -> list[dict[str, Any]]:
    """Every `## Open Questions` item across both artifact trees."""
    sources = [base for base in artifact_roots(root) if base.exists()]
    if not sources:
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(item for base in sources for item in base.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        front, _ = parse_front_matter(text)
        source = relpath(path, root)
        for question in extract_open_questions(text):
            found.append(
                {
                    "question": question,
                    "kind": "artifact",
                    "source_artifact": source,
                    "initiative_id": front.get("initiative_id"),
                    "skill": front.get("skill"),
                }
            )
    return found


def sync_open_questions(root: Path) -> dict[str, Any]:
    """Refresh artifact-sourced questions, then report the open count."""
    payload = record_questions(root, scan_artifact_questions(root))
    entries = payload["open_questions"]
    return {
        "open_questions": entries,
        "open_count": sum(1 for entry in entries if entry["status"] == "open"),
        "total_count": len(entries),
        "path": relpath(questions_path(root), root),
    }


def capture_asked_questions(root: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Record what the assistant asked the human, before the answer arrives.

    The PreToolUse hook on AskUserQuestion used to return `allow` and nothing
    else, so every question and every answer was discarded the moment the turn
    ended. This is the one place in the system that sees a question at the exact
    moment it is raised.
    """
    if not payload or not workspace_exists(root):
        return {"recorded": 0}
    # `or {}` only replaces a *falsey* value, so a string `tool_input` sailed
    # through to `.get` and took the hook down. The type is what has to be
    # checked, which is what `command_from_payload` and its siblings already do.
    tool_input = payload.get("tool_input")
    asked = tool_input.get("questions") if isinstance(tool_input, dict) else None
    if not isinstance(asked, list):
        return {"recorded": 0}

    entries: list[dict[str, Any]] = []
    for item in asked:
        if not isinstance(item, dict):
            continue
        text = str(item.get("question", "")).strip()
        if not text:
            continue
        options = [
            str(option.get("label", "")).strip()
            for option in item.get("options", [])
            if isinstance(option, dict) and option.get("label")
        ]
        entries.append({"question": text, "kind": "clarification", "options": options, "status": "open"})
    if not entries:
        return {"recorded": 0}
    record_questions(root, entries)
    return {"recorded": len(entries)}


def capture_given_answers(root: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Record what the human answered, once the tool has returned.

    The other half of the loop. `capture_asked_questions` runs at `PreToolUse` and
    its own docstring says "before the answer arrives" - and nothing ever ran after
    it, so every question a human answered stayed `open` forever and was re-surfaced
    on every subsequent turn. Four questions answered in one session were still
    being reported as open at the end of it.

    Matching is by exact question text, which is what the capture side stored, so
    this never has to guess the way answering by substring does.
    """
    if not payload or not workspace_exists(root):
        return {"answered": 0}
    tool_input = payload.get("tool_input")
    asked = tool_input.get("questions") if isinstance(tool_input, dict) else None
    response = payload.get("tool_response")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            response = None
    if not isinstance(asked, list) or not isinstance(response, dict):
        return {"answered": 0}

    # The harness returns answers keyed by the question text it was given.
    answers = response.get("answers") if isinstance(response.get("answers"), dict) else response
    if not isinstance(answers, dict):
        return {"answered": 0}

    answered = 0
    for item in asked:
        if not isinstance(item, dict):
            continue
        text = str(item.get("question", "")).strip()
        chosen = answers.get(text)
        if not text or not chosen:
            continue
        result = answer_question(root, question_id(text, ""), str(chosen))
        if not result.get("updated"):
            # The id is derived from the text with an empty source, matching how
            # `capture_asked_questions` records it. If that misses, fall back to the
            # exact text rather than a substring, which could hit the wrong entry.
            result = answer_question(root, text, str(chosen))
        answered += 1 if result.get("updated") else 0
    return {"answered": answered}
