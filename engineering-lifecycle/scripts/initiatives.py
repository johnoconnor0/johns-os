#!/usr/bin/env python3
"""Which initiative a piece of work belongs to, and whether the session has drifted.

Split out of quality_tools.py. An initiative used to exist only as a directory
name the model invented while writing the first artifact into it: no registry, no
active pointer, no create/switch/close verb, and the one function that could
answer "which initiative are we in?" was never called by anything.

`initiative_drift_detector` takes the classified intent as an argument rather than
computing it. That keeps this module free of any dependency on prompt
classification, which lives in quality_tools and would otherwise import back.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eng_common import (
    DOCS_SUBDIRS,
    INITIATIVE_STAGES,
    docs_root,
    engineering_root,
    git,
    now_iso,
    read_json,
    slugify,
    workspace_exists,
    write_json,
)

# --- initiative identity ---------------------------------------------------
#
# An initiative used to exist only as a directory name the model invented while
# writing the first artifact into it. There was no registry, no active pointer,
# no create/switch/close verb, and the one function that could answer "which
# initiative are we in?" was never called by anything. So when a session pivoted
# to unrelated work, nothing noticed: the model kept writing into whichever
# folder happened to still be in its context.

_STOPWORD_TEXT = (
    "a an and are as at be but by can do does for from has have how i if in into is it its me my "
    "of on or our should so than that the their then there these this to us was we what when where "
    "which who why will with would you your please add create build make update change fix need want "
    "let lets new work working now also just like get set use using run"
)
_STOPWORDS = frozenset(_STOPWORD_TEXT.split(" "))
# Below this overlap the prompt is not plausibly about the active initiative.
_DRIFT_THRESHOLD = 0.12
_DRIFT_INTENTS = frozenset(
    {
        "discovery",
        "requirements",
        "ux-design",
        "system-map",
        "architecture",
        "data-model",
        "api-contract",
        "design-system",
        "ui-prototype",
        "implementation-plan",
        "implementation",
        "testing",
        "release",
    }
)


def registry_path(root: Path) -> Path:
    return engineering_root(root) / "initiatives" / "registry.json"


def initiative_dirs(root: Path) -> list[str]:
    base = engineering_root(root) / "initiatives"
    if not base.is_dir():
        return []
    return sorted(path.name for path in base.iterdir() if path.is_dir())


def load_initiative_registry(root: Path) -> dict[str, Any]:
    """The registry, reconciled with what is actually on disk.

    Directories created before the registry existed (or by hand) are adopted
    rather than ignored, so the registry can never disagree with the filesystem.
    """
    data = read_json(registry_path(root)) or {}
    known = {entry["id"]: entry for entry in data.get("initiatives", []) if isinstance(entry, dict) and entry.get("id")}
    for name in initiative_dirs(root):
        known.setdefault(name, {"id": name, "title": name.replace("-", " "), "status": "active", "created_at": None})
    active = data.get("active")
    if active not in known:
        active = next((entry["id"] for entry in known.values() if entry.get("status") == "active"), None)
    return {"active": active, "initiatives": sorted(known.values(), key=lambda item: item["id"])}


def save_initiative_registry(root: Path, registry: dict[str, Any]) -> dict[str, Any]:
    registry["updated_at"] = now_iso()
    if workspace_exists(root):
        write_json(registry_path(root), registry)
    return registry


def topic_tokens(text: str) -> set[str]:
    """Content words of a piece of text, for overlap scoring.

    Public because workstream clustering scores issue titles the same way. Two
    different tokenizers over the same corpus would drift.
    """
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {word for word in words if len(word) > 2 and word not in _STOPWORDS}


# Kept as a private alias: this module had it under the old name throughout.
_topic_tokens = topic_tokens


def _initiative_tokens(root: Path, entry: dict[str, Any]) -> set[str]:
    """Tokens describing an initiative: its slug, title, and artifact headings."""
    tokens = topic_tokens(entry.get("id", "").replace("-", " "))
    tokens |= topic_tokens(entry.get("title", ""))
    identifier = entry.get("id", "")
    folders = [engineering_root(root) / "initiatives" / identifier, docs_root(root) / identifier]
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.md"))[:20]:
            try:
                head = path.read_text(encoding="utf-8")[:400]
            except OSError:
                continue
            tokens |= topic_tokens(head)
    return tokens


def initiative_token_index(root: Path) -> dict[str, set[str]]:
    """Token sets for every open initiative, built once.

    ``active_initiative_resolver`` reads up to 20 markdown files per initiative
    per call. That is affordable once per prompt and ruinous per issue: triaging
    200 tracker items across 5 initiatives would be 20,000 file reads. Callers
    with more than one thing to classify build this and pass it in.
    """
    registry = load_initiative_registry(root)
    return {
        entry["id"]: _initiative_tokens(root, entry)
        for entry in registry["initiatives"]
        if entry.get("status") != "closed"
    }


def _overlap(prompt_tokens: set[str], initiative_tokens: set[str]) -> float:
    if not prompt_tokens or not initiative_tokens:
        return 0.0
    return len(prompt_tokens & initiative_tokens) / len(prompt_tokens)


def active_initiative_resolver(root: Path, prompt: str, index: dict[str, set[str]] | None = None) -> dict[str, Any]:
    """Which initiative this prompt is about.

    Matching used to be a literal lowercase substring test against the slug, so
    "the public repo readiness work" did not match `public-repo-readiness`, and
    with two or more initiatives and no slug typed verbatim it gave up entirely.

    `index` is an optional prebuilt ``initiative_token_index``. Pass it when
    classifying more than one thing: building it per call re-reads up to 20
    markdown files per initiative each time.
    """
    registry = load_initiative_registry(root)
    entries = [entry for entry in registry["initiatives"] if entry.get("status") != "closed"]
    candidates = [entry["id"] for entry in entries]
    text = prompt.lower()
    prompt_tokens = topic_tokens(prompt)

    scored: list[tuple[float, str]] = []
    for entry in entries:
        identifier = entry["id"]
        tokens = index[identifier] if index is not None and identifier in index else _initiative_tokens(root, entry)
        # An explicitly typed slug is decisive, whatever the token overlap says.
        score = 1.0 if identifier.lower() in text else _overlap(prompt_tokens, tokens)
        scored.append((score, identifier))
    scored.sort(reverse=True)

    best_score, best = scored[0] if scored else (0.0, None)
    chosen, confidence = best, "high"
    if not scored:
        chosen, confidence = None, "low"
    elif best_score >= 1.0:
        confidence = "high"
    elif best_score >= _DRIFT_THRESHOLD:
        confidence = "medium"
    else:
        # Nothing matched: stay on the active initiative rather than guessing,
        # and say so with low confidence. The drift detector reads this.
        chosen = registry["active"] or (candidates[0] if len(candidates) == 1 else None)
        confidence = "low"

    return {
        "initiative_id": chosen,
        "confidence": confidence,
        "candidates": candidates,
        "active": registry["active"],
        "best_match": best,
        "best_score": round(best_score, 3),
        "scores": {identifier: round(score, 3) for score, identifier in scored},
    }


def initiative_drift_detector(root: Path, prompt: str, intent: dict[str, Any]) -> dict[str, Any]:
    """Decide whether this prompt is new work rather than the active initiative.

    This is the check that was missing entirely. Without it a session that
    pivots keeps appending to whatever initiative folder it started in, and the
    only signal anyone gets is a PRD for one feature sitting inside another
    feature's directory.

    `intent` is passed in rather than computed. Classification lives in
    quality_tools, and calling it from here would make these two modules import
    each other.
    """
    resolution = active_initiative_resolver(root, prompt)
    result = {
        "drift": False,
        "action": "continue",
        "intent": intent["intent"],
        "active": resolution["active"],
        "best_match": resolution["best_match"],
        "best_score": resolution["best_score"],
        "message": "",
    }
    if intent["intent"] not in _DRIFT_INTENTS or not workspace_exists(root):
        return result

    active = resolution["active"]
    if not resolution["candidates"]:
        result.update(
            drift=True,
            action="create",
            message=(
                "No initiative exists yet. Before writing lifecycle artifacts, create one with "
                "`/initiative new <slug>` so this work has somewhere to live."
            ),
        )
        return result

    better_match = resolution["best_match"] and resolution["best_match"] != active
    if active and better_match and resolution["best_score"] >= _DRIFT_THRESHOLD:
        result.update(
            drift=True,
            action="switch",
            message=(
                f"This prompt matches initiative '{resolution['best_match']}' more closely than the active one "
                f"('{active}'). Use AskUserQuestion to confirm before writing artifacts: switch to "
                f"'{resolution['best_match']}', or continue in '{active}'? Then run "
                f"`/initiative switch <id>` if switching."
            ),
        )
        return result

    if active and resolution["best_score"] < _DRIFT_THRESHOLD:
        result.update(
            drift=True,
            action="ask",
            message=(
                f"This looks like new work rather than the active initiative '{active}'. Do NOT write lifecycle "
                f"artifacts into 'initiatives/{active}/' by default. Use AskUserQuestion to ask whether to start a "
                f"new initiative (`/initiative new <slug>`) or continue in '{active}', and record the answer."
            ),
        )
    return result


def initiative_command(root: Path, action: str, identifier: str = "", title: str = "") -> dict[str, Any]:
    """Create, switch, close, or list initiatives."""
    registry = load_initiative_registry(root)
    known = {entry["id"]: entry for entry in registry["initiatives"]}

    if action == "list":
        return {"action": "list", **registry}

    if action == "new":
        slug = slugify(identifier or title)
        if not slug:
            return {"action": "new", "error": "an initiative id or title is required"}
        if slug in known:
            return {"action": "new", "error": f"initiative already exists: {slug}", "initiative_id": slug}
        base = engineering_root(root) / "initiatives" / slug
        for stage in INITIATIVE_STAGES:
            (base / stage).mkdir(parents=True, exist_ok=True)
        # The narrative half of the initiative lives in the docs tree.
        for subdir in DOCS_SUBDIRS:
            (docs_root(root) / slug / subdir).mkdir(parents=True, exist_ok=True)
        known[slug] = {
            "id": slug,
            "title": title or identifier or slug.replace("-", " "),
            "status": "active",
            "created_at": now_iso(),
            "last_active_at": now_iso(),
            "branch": (lambda result: result[1].strip() if result[0] == 0 else None)(
                git(["rev-parse", "--abbrev-ref", "HEAD"], root)
            ),
        }
        registry = {"active": slug, "initiatives": sorted(known.values(), key=lambda item: item["id"])}
        save_initiative_registry(root, registry)
        return {"action": "new", "initiative_id": slug, "active": slug, "stages": list(INITIATIVE_STAGES)}

    if action == "switch":
        slug = slugify(identifier)
        if slug not in known:
            return {"action": "switch", "error": f"unknown initiative: {slug}", "candidates": sorted(known)}
        known[slug]["last_active_at"] = now_iso()
        known[slug]["status"] = "active"
        registry = {"active": slug, "initiatives": sorted(known.values(), key=lambda item: item["id"])}
        save_initiative_registry(root, registry)
        return {"action": "switch", "active": slug}

    if action == "close":
        slug = slugify(identifier) or registry["active"]
        if slug not in known:
            return {"action": "close", "error": f"unknown initiative: {slug}", "candidates": sorted(known)}
        known[slug]["status"] = "closed"
        known[slug]["closed_at"] = now_iso()
        remaining = [entry["id"] for entry in known.values() if entry.get("status") == "active"]
        registry = {
            "active": remaining[0] if len(remaining) == 1 else None,
            "initiatives": sorted(known.values(), key=lambda item: item["id"]),
        }
        save_initiative_registry(root, registry)
        return {"action": "close", "closed": slug, "active": registry["active"]}

    return {"action": action, "error": f"unknown action: {action}"}
