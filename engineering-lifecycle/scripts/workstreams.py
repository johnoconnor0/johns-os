#!/usr/bin/env python3
"""Group the surfaced-issue queue into workstreams that can be worked in parallel.

A backlog is a list; work is not. The question this answers is "which of these
belong in one sitting, and which of those sittings can happen at the same time?".

## Why this is deterministic

Clustering by model call would be unreproducible, would cost a call before any
work starts, and could not run in CI. So the base pass is union-find over a
signal graph, and the one place a model genuinely helps - naming a cluster whose
title heuristic came out weak - is offered separately and only when the title
confidence is low.

## The property that matters

    score = 0.30*same_initiative + 0.30*path_affinity + 0.20*jaccard(labels)
          + 0.15*jaccard(tokens)  + 0.05*same_project
    MERGE_THRESHOLD = 0.34

**No single signal reaches the threshold.** Two must agree before anything
merges. That is what stops "everything labelled backend" collapsing into one
forty-issue blob, and it is the first thing a future tuner will destroy by
raising one weight past 0.34. The weights sum to 1.0 so the threshold reads as a
fraction of total agreement.

Hard edges are different: a shared parent, or an explicit blocking relation, merge
unconditionally. The tracker's own declared structure outranks every heuristic
here - splitting a parent from its sub-issues would be an obviously wrong answer
however the tokens score.

## What this cannot see

Tracker issues carry no file paths. Locally-detected findings do, but a pulled
Linear issue almost never will - so path affinity, one of the two strongest
signals, is blind on exactly the items this feature exists to handle. Rather than
pretend otherwise, `derived_paths` extracts path-shaped tokens from the body and
keeps only those that exist on disk, every workstream reports which kind of path
evidence it had, and `path_evidence: none` forces `parallel_safe: false`. A
parallel-safety verdict computed from invented paths is worse than one computed
from no paths at all.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path
from typing import Any

from eng_common import engineering_root, now_iso, read_json_safe, write_json, write_text
from initiatives import initiative_token_index, topic_tokens
from tracker import SEVERITIES, load_queue

WEIGHTS = {"initiative": 0.30, "path": 0.30, "label": 0.20, "token": 0.15, "project": 0.05}
MERGE_THRESHOLD = 0.34
MAX_WORKSTREAM_SIZE = 8
MAX_ISSUES = 1500

_WORKSTREAMS = ("tracker", "workstreams.json")
_DIGEST = ("tracker", "workstreams.md")

# Statuses that mean the work is over and should not be planned.
_CLOSED = {"resolved", "dismissed", "duplicate"}

# A path-shaped token: at least one directory separator, or a bare filename with a
# source extension. Deliberately narrow - anything looser matches prose.
_PATHISH = re.compile(
    r"(?:[\w.-]+/)+[\w.-]+\.\w{1,5}|\b[\w.-]+\.(?:ts|tsx|js|jsx|py|go|rs|rb|php|sql|ya?ml|json|md|sh|ps1)\b"
)

# Most specific first; first hit wins. Matched against paths and labels.
AGENT_ROUTES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("database-engineer", ("migrations/", "schema", "prisma/", "db/"), ("database", "migration", "schema", "sql")),
    ("frontend-engineer", ("components/", "pages/", "ui/", ".tsx", ".vue", ".svelte"), ("frontend", "ui", "ux")),
    ("api-contract-reviewer", ("openapi", "routes/", "api/", ".proto", "graphql"), ("api", "contract", "integration")),
    ("security-reviewer", ("auth/", "security/"), ("security", "auth", "vulnerability", "cve")),
    (
        "devops-release-engineer",
        (".github/workflows/", "dockerfile", "terraform/", "k8s/", "infra/"),
        ("infra", "deploy", "release", "ci", "github"),
    ),
    ("qa-test-strategist", ("tests/", "__tests__/", ".spec.", ".test."), ("test", "qa", "flaky")),
    ("backend-engineer", ("server/", "services/", "lib/", "src/", "scripts/"), ("backend", "worker", "job", "system")),
)
DEFAULT_AGENT = "solution-architect"


def workstreams_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_WORKSTREAMS)


def digest_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_DIGEST)


# --- features --------------------------------------------------------------


def derived_paths(issue: dict[str, Any], root: Path) -> list[str]:
    """Path-shaped tokens in the body, kept only if they exist on disk.

    The verification is the whole point. Without it this is a regex that invents
    file paths out of prose, and a `parallel_safe` computed from invented paths is
    worse than one computed from none.
    """
    found = {match.group(0).lstrip("./") for match in _PATHISH.finditer(issue.get("body", ""))}
    return sorted(path for path in found if path and (root / path).exists())


def _path_keys(paths: list[str]) -> set[str]:
    """Exact paths plus their depth-2 directory prefixes.

    Depth 1 is deliberately excluded: `src` merges the whole repository.
    """
    keys: set[str] = set()
    for path in paths:
        posix = path.replace("\\", "/")
        keys.add(posix)
        parts = posix.split("/")
        if len(parts) > 2:
            keys.add("/".join(parts[:2]))
    return keys


def features(issue: dict[str, Any], root: Path, index: dict[str, set[str]]) -> dict[str, Any]:
    external = issue.get("external") or {}
    declared = [str(item) for item in (issue.get("paths") or [])]
    inferred = derived_paths(issue, root) if not declared else []
    paths = declared or inferred
    return {
        "id": issue["id"],
        "title": issue.get("title", ""),
        "severity": issue.get("severity", "medium"),
        "initiative": issue.get("initiative_id") or "",
        "labels": {str(label).lower() for label in (external.get("labels") or [])},
        "tokens": topic_tokens(f"{issue.get('title', '')} {issue.get('body', '')[:400]}"),
        "paths": paths,
        "path_keys": _path_keys(paths),
        "path_evidence": "declared" if declared else ("derived" if inferred else "none"),
        "project": str(external.get("project") or ""),
        "external_id": str(external.get("id") or ""),
        "identifier": str(external.get("identifier") or ""),
        "parent": str(external.get("parent") or ""),
        "url": str(external.get("url") or ""),
        "_index": index,
    }


# --- scoring ---------------------------------------------------------------


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def path_affinity(left: dict[str, Any], right: dict[str, Any]) -> float:
    """Not a Jaccard: sharing one file out of ten is a strong signal, not a weak one."""
    if not left["path_keys"] or not right["path_keys"]:
        return 0.0
    if set(left["paths"]) & set(right["paths"]):
        return 1.0
    return 0.6 if left["path_keys"] & right["path_keys"] else 0.0


def signal_breakdown(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    return {
        "initiative": 1.0 if left["initiative"] and left["initiative"] == right["initiative"] else 0.0,
        "path": path_affinity(left, right),
        "label": _jaccard(left["labels"], right["labels"]),
        "token": _jaccard(left["tokens"], right["tokens"]),
        "project": 1.0 if left["project"] and left["project"] == right["project"] else 0.0,
    }


def score(left: dict[str, Any], right: dict[str, Any]) -> float:
    signals = signal_breakdown(left, right)
    return sum(WEIGHTS[name] * value for name, value in signals.items())


def hard_edge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """The tracker's own structure, which outranks every heuristic."""
    if left["parent"] and left["parent"] == right["parent"]:
        return True
    return bool(
        (left["parent"] and left["parent"] == right["identifier"])
        or (right["parent"] and right["parent"] == left["identifier"])
        or (left["parent"] and left["parent"] == right["external_id"])
        or (right["parent"] and right["parent"] == left["external_id"])
    )


# --- union-find ------------------------------------------------------------


class _Union:
    def __init__(self, keys: list[str]) -> None:
        self.parent = {key: key for key in keys}
        self.size = dict.fromkeys(keys, 1)

    def find(self, key: str) -> str:
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        # Merge into the lexicographically smaller root, so the result does not
        # depend on which side happened to be larger.
        a, b = sorted((a, b))
        self.parent[b] = a
        self.size[a] += self.size[b]


# --- titling and routing ---------------------------------------------------

_TITLE_STOP = frozenset({"the", "and", "for", "with", "into", "from", "that", "not", "are", "its"})


def _title_for(members: list[dict[str, Any]]) -> tuple[str, str]:
    """A title and how much to trust it.

    The parent issue's own title first, when one member is the parent of the
    others. Somebody already wrote a sentence describing exactly this group of
    work; synthesising a worse one from token frequencies would be perverse.
    """
    if len(members) == 1:
        return members[0]["title"], "high"

    keys = {member["identifier"] for member in members if member["identifier"]}
    keys |= {member["external_id"] for member in members if member["external_id"]}
    parents = {member["parent"] for member in members if member["parent"]}
    for member in members:
        own = {member["identifier"], member["external_id"]} - {""}
        if own & parents and not member["parent"]:
            return member["title"], "high"

    shared_labels = set.intersection(*(member["labels"] for member in members)) if members else set()
    words: dict[str, int] = {}
    for member in members:
        for word in topic_tokens(member["title"]):
            if word not in _TITLE_STOP:
                words[word] = words.get(word, 0) + 1
    # Only words most of the group shares, and only if there are enough of them
    # to read as a phrase. Two frequent-but-unrelated tokens produce word salad,
    # which is worse than admitting the heuristic did not find a name.
    quorum = max(2, (len(members) + 1) // 2)
    common = sorted(((count, word) for word, count in words.items() if count >= quorum), reverse=True)
    if len(common) >= 3:
        picked = sorted(word for _count, word in common[:3])
        return " ".join(word.title() for word in picked), "low"
    if shared_labels:
        return f"{sorted(shared_labels)[0].title()} work", "low"
    return "", "low"


def _route(members: list[dict[str, Any]]) -> tuple[str, float]:
    paths = " ".join(path.lower() for member in members for path in member["paths"])
    labels = {label for member in members for label in member["labels"]}
    text = " ".join(member["title"].lower() for member in members)
    for agent, path_hints, label_hints in AGENT_ROUTES:
        matched = sum(
            1
            for member in members
            if any(hint in " ".join(member["paths"]).lower() for hint in path_hints)
            or any(hint in label for hint in label_hints for label in member["labels"])
            or any(hint in member["title"].lower() for hint in label_hints)
        )
        if matched and (any(hint in paths for hint in path_hints) or any(hint in text for hint in label_hints) or
                        any(hint in label for hint in label_hints for label in labels)):
            return agent, round(matched / len(members), 2)
    return DEFAULT_AGENT, 0.0


# --- the build -------------------------------------------------------------


def build_workstreams(
    root: Path,
    threshold: float = MERGE_THRESHOLD,
    max_size: int = MAX_WORKSTREAM_SIZE,
    max_issues: int = MAX_ISSUES,
) -> dict[str, Any]:
    queue = load_queue(root)
    open_issues = [issue for issue in queue["issues"] if issue.get("status") not in _CLOSED]
    truncated = len(open_issues) > max_issues
    open_issues = open_issues[:max_issues]

    if not open_issues:
        return {
            "generated_at": now_iso(),
            "queue_generated_at": queue.get("generated_at", ""),
            "source": {"queue_issues": len(queue["issues"]), "clustered": 0, "excluded": len(queue["issues"])},
            "parameters": {"merge_threshold": threshold, "max_size": max_size, "weights": WEIGHTS},
            "truncated": False,
            "cycles": [],
            "workstreams": [],
        }

    index = initiative_token_index(root)
    feats = {issue["id"]: features(issue, root, index) for issue in open_issues}
    union = _Union(sorted(feats))

    for left, right in combinations(sorted(feats), 2):
        if hard_edge(feats[left], feats[right]):
            union.union(left, right)

    evidence: dict[str, list[dict[str, Any]]] = {}
    # Strongest first, so when the size cap bites, the strongest pairing survives.
    # That ordering is what makes a size-capped union-find reproducible: the result
    # is merge-order dependent, and this fixes the merge order.
    scored = sorted(
        ((score(feats[a], feats[b]), a, b) for a, b in combinations(sorted(feats), 2)),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    for value, left, right in scored:
        if value < threshold:
            break
        a, b = union.find(left), union.find(right)
        if a == b or union.size[a] + union.size[b] > max_size:
            continue
        union.union(left, right)
        root_key = union.find(left)
        evidence.setdefault(root_key, []).append(
            {
                "pair": [left, right],
                "score": round(value, 3),
                "signals": {k: round(v, 3) for k, v in signal_breakdown(feats[left], feats[right]).items()},
            }
        )

    groups: dict[str, list[str]] = {}
    for key in sorted(feats):
        groups.setdefault(union.find(key), []).append(key)

    severity_rank = {name: position for position, name in enumerate(SEVERITIES)}
    ordered = sorted(
        groups.items(),
        key=lambda item: (min(severity_rank.get(feats[m]["severity"], 99) for m in item[1]), item[0]),
    )

    streams: list[dict[str, Any]] = []
    for position, (root_key, member_ids) in enumerate(ordered, 1):
        members = [feats[member] for member in member_ids]
        title, confidence = _title_for(members)
        agent, agent_confidence = _route(members)
        paths = sorted({path for member in members for path in member["paths"]})
        evidence_kinds = {member["path_evidence"] for member in members}
        path_evidence = "declared" if "declared" in evidence_kinds else ("derived" if "derived" in evidence_kinds else "none")
        worst = min(members, key=lambda m: severity_rank.get(m["severity"], 99))["severity"]
        slug = _slug(title or f"workstream-{position}")
        streams.append(
            {
                "id": f"ws-{position:02d}-{slug}",
                "title": title or f"Workstream {position}",
                "title_confidence": confidence,
                "issue_ids": sorted(member_ids),
                "identifiers": sorted(m["identifier"] for m in members if m["identifier"]),
                "initiative_id": next((m["initiative"] for m in members if m["initiative"]), None),
                "severity": worst,
                "size": len(members),
                "labels": sorted({label for member in members for label in member["labels"]}),
                "paths": paths,
                "path_evidence": path_evidence,
                "suggested_agent": agent,
                "agent_confidence": agent_confidence,
                "depends_on": [],
                "conflicts_with": [],
                "wave": 0,
                "parallel_safe": False,
                "parallel_safe_reason": "",
                "merge_evidence": sorted(evidence.get(root_key, []), key=lambda e: -e["score"])[:3],
            }
        )

    _add_conflict_edges(streams)
    _mark_parallel_safe(streams)

    return {
        "generated_at": now_iso(),
        "queue_generated_at": queue.get("generated_at", ""),
        "source": {
            "queue_issues": len(queue["issues"]),
            "clustered": len(open_issues),
            "excluded": len(queue["issues"]) - len(open_issues),
            "excluded_reason": "resolved|dismissed|duplicate",
        },
        "parameters": {"merge_threshold": threshold, "max_size": max_size, "weights": WEIGHTS},
        "truncated": truncated,
        "cycles": [],
        "workstreams": streams,
    }


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return "-".join(cleaned.split("-")[:4]) or "workstream"


def _add_conflict_edges(streams: list[dict[str, Any]]) -> None:
    """Workstreams touching the same file cannot be implemented at the same time."""
    for left, right in combinations(streams, 2):
        shared = sorted(set(left["paths"]) & set(right["paths"]))
        if not shared:
            continue
        left["conflicts_with"].append({"workstream_id": right["id"], "kind": "shared-path", "paths": shared[:5]})
        right["conflicts_with"].append({"workstream_id": left["id"], "kind": "shared-path", "paths": shared[:5]})


def _mark_parallel_safe(streams: list[dict[str, Any]]) -> None:
    """Never a bare boolean.

    A gate with no stated reason is a gate people override without reading it.
    """
    for stream in streams:
        if stream["conflicts_with"]:
            names = ", ".join(item["workstream_id"] for item in stream["conflicts_with"][:2])
            stream["parallel_safe"] = False
            stream["parallel_safe_reason"] = f"shares files with {names}"
        elif stream["path_evidence"] == "none":
            stream["parallel_safe"] = False
            # Unknown is not safe. These issues named no file that exists on disk,
            # so nothing here can tell whether two of them would collide.
            stream["parallel_safe_reason"] = "no file-path evidence, so overlap cannot be ruled out"
        else:
            stream["parallel_safe"] = True
            stream["parallel_safe_reason"] = "no workstream shares a path with this one"


# --- output ----------------------------------------------------------------


def render_digest(payload: dict[str, Any]) -> str:
    streams = payload.get("workstreams", [])
    lines = [
        "# Workstreams",
        "",
        f"Generated at {payload.get('generated_at', '')} from a queue of "
        f"{payload.get('source', {}).get('clustered', 0)} open issue(s).",
        "",
    ]
    if payload.get("truncated"):
        lines += ["> Truncated: more issues than the clustering cap. Narrow the queue and re-run.", ""]
    if not streams:
        return "\n".join([*lines, "No open issues to group.", ""])
    for stream in streams:
        lines.append(f"## {stream['id']} — {stream['title']}")
        lines.append("")
        detail = f"- severity: {stream['severity']} | size: {stream['size']} | agent: {stream['suggested_agent']}"
        if stream["title_confidence"] == "low":
            detail += " | **title confidence low — worth renaming**"
        lines.append(detail)
        if stream["identifiers"]:
            lines.append(f"- issues: {', '.join(stream['identifiers'])}")
        if stream["labels"]:
            lines.append(f"- labels: {', '.join(stream['labels'])}")
        if stream["paths"]:
            lines.append(f"- paths ({stream['path_evidence']}): {', '.join(f'`{p}`' for p in stream['paths'][:5])}")
        safe = "yes" if stream["parallel_safe"] else "no"
        lines.append(f"- parallel safe: {safe} — {stream['parallel_safe_reason']}")
        lines.append("")
    return "\n".join(lines)


def write_workstreams(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    write_json(workstreams_path(root), payload)
    write_text(digest_path(root), render_digest(payload))
    return payload


def load_workstreams(root: Path) -> dict[str, Any]:
    return read_json_safe(workstreams_path(root))


def workstream_status(root: Path) -> dict[str, Any]:
    """The cheap answer the intake hook needs: no clustering, one file read."""
    payload = load_workstreams(root)
    streams = payload.get("workstreams", []) if isinstance(payload, dict) else []
    queue = load_queue(root)
    open_ids = {issue["id"] for issue in queue["issues"] if issue.get("status") not in _CLOSED}
    grouped = {issue_id for stream in streams for issue_id in stream.get("issue_ids", [])}
    return {
        "workstreams": len(streams),
        "unclustered": len(open_ids - grouped),
        # Stale means the queue moved after the grouping was computed, so the
        # grouping no longer describes the work.
        "workstreams_stale": bool(streams) and payload.get("queue_generated_at") != queue.get("generated_at"),
    }
