#!/usr/bin/env python3
"""Issue-tracker adapters for the surfacing and sync tooling.

`linear-sync.py` had the right architecture and one wrong assumption. The
architecture - a deterministic script that emits a plan the model executes through
MCP, because hooks cannot call MCP tools - is correct and is kept verbatim. The
assumption was that the tracker is Linear: the config schema, the state file, the
ledger field names and the priority map all said so.

An adapter carries what actually differs between trackers: the verbs, what each
argument is called, where the created issue's id appears in the response, and how a
project URL decodes into an id. Everything else stays shared, the same way
`dialects.py` shares one pipeline across five database engines.

## Tool names, and why they are stored as bare verbs

A tracker reached through MCP is addressed as `mcp__<server>__<verb>`. The server
segment is not a property of the tracker - it is a property of how *this machine*
connected to it. A workspace connector gets a UUID; a `.mcp.json` declaration gets
the name it was declared under. The same Linear, two different tool names.

So providers declare `save_issue`, and the server segment comes from config. When it
is unknown, `tool_candidates` lists every plausible spelling and the model uses
whichever resolves - hooks cannot see which MCP servers are connected, so the first
attempt is necessarily a guess. `reconcile` then records the one that worked, and
the guess happens once per repository rather than once per run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eng_common import engineering_root

# Local status vocabulary. Every provider maps these onto its own workflow states.
STATUSES = ("open", "in-progress", "blocked", "done", "deferred", "cancelled")


@dataclass(frozen=True)
class Tracker:
    """One issue tracker's answer to the questions the shared tooling asks."""

    name: str
    label: str
    # False for the local-file provider: no MCP, no network, no tool names.
    remote: bool = True

    # Bare verbs. Never write `mcp__...` here - see the module docstring.
    create_tool: str = ""
    update_tool: str = ""
    search_tool: str = ""
    get_tool: str = ""
    comment_tool: str = ""
    # Server segments worth trying when config does not name one.
    server_candidates: tuple[str, ...] = ()

    # Canonical field -> this provider's argument name.
    field_map: Mapping[str, str] = field(default_factory=dict)
    # Config scope key -> this provider's argument name.
    scope_map: Mapping[str, str] = field(default_factory=dict)
    # The argument carrying an existing issue's id on update. Its presence is also
    # what distinguishes an update from a create for providers that use one verb.
    update_key: str = "id"

    # Where the created issue's identifiers appear in the tool result.
    id_key: str = "id"
    url_key: str = "url"
    identifier_key: str = "identifier"

    priority_map: Mapping[str, int] = field(default_factory=dict)
    default_status_map: Mapping[str, str] = field(default_factory=dict)
    supports_labels: bool = True
    supports_assignee: bool = True
    supports_project: bool = True

    # --- the pull direction ------------------------------------------------
    #
    # `search_tool` and `get_tool` above were declared from the start and read by
    # nothing: the round trip only ever pushed. These are what a search call needs
    # that a write call does not.

    # Canonical search argument -> this provider's argument name. Separate from
    # `field_map` because the search verb and the write verb disagree: Linear
    # writes `labels` and searches `label`.
    search_arg_map: Mapping[str, str] = field(default_factory=dict)
    # This provider's own words for "still open". One search call per entry.
    open_states: tuple[str, ...] = ()
    # Response fields worth asking for, where the provider lets you choose. Must
    # be exact members of its own enum: an unknown name is an error, not an
    # ignored hint.
    search_fields: tuple[str, ...] = ()
    # Canonical issue field -> where it appears in one returned issue.
    ingest_map: Mapping[str, str] = field(default_factory=dict)
    # Where the array and the next-page cursor live in the response.
    items_key: str = "issues"
    next_cursor_key: str = "nextCursor"
    # The human-facing key (WEB-123) when the search verb will not return it.
    identifier_url_pattern: str = ""

    # Patterns that pull an id out of a pasted URL, so `LINEAR_PROJECT_ID` and
    # `LINEAR_PROJECT_URL` are one code path rather than two.
    url_patterns: tuple[tuple[str, str], ...] = ()
    notes: str = ""

    @property
    def supports_search(self) -> bool:
        """Whether a fetch plan can be built for this provider.

        Declaring a verb is not enough - the plan needs to know what "open" is
        called and what the response looks like. A provider without that answers
        "not configured" and names the overlay file, which is the same discipline
        `resolve_tracker` uses of returning the reason rather than guessing.
        """
        return bool(self.remote and self.search_tool and self.open_states)

    def search_argument(self, key: str) -> str:
        return self.search_arg_map.get(key, key)

    def scope_argument(self, key: str) -> str:
        return self.scope_map.get(key, key)

    def field_argument(self, key: str) -> str:
        return self.field_map.get(key, key)


LINEAR = Tracker(
    name="linear",
    label="Linear",
    create_tool="save_issue",
    update_tool="save_issue",
    search_tool="list_issues",
    get_tool="get_issue",
    comment_tool="save_comment",
    server_candidates=("linear",),
    # Verified against the tool's own schema: `description` not `body`, and
    # `assignee` rather than `assigneeId`, which the schema calls out explicitly.
    field_map={
        "title": "title",
        "body": "description",
        "status": "state",
        "labels": "labels",
        "priority": "priority",
        "assignee": "assignee",
    },
    scope_map={"team": "team", "project": "project", "cycle": "cycle"},
    update_key="id",
    id_key="id",
    url_key="url",
    identifier_key="identifier",
    # Linear's own scale: 0=None, 1=Urgent, 2=High, 3=Medium, 4=Low.
    priority_map={
        "critical": 1,
        "urgent": 1,
        "high": 2,
        "warning": 3,
        "normal": 3,
        "medium": 3,
        "low": 4,
        "suggestion": 4,
    },
    default_status_map={
        "open": "Todo",
        "in-progress": "In Progress",
        "blocked": "Blocked",
        "done": "Done",
        "deferred": "Backlog",
        "cancelled": "Canceled",
    },
    search_arg_map={
        "state": "state",
        "limit": "limit",
        "cursor": "cursor",
        "label": "label",
        "assignee": "assignee",
        "query": "query",
        "updated_since": "updatedAt",
        "order_by": "orderBy",
        "include_archived": "includeArchived",
        "fields": "fields",
        "team": "team",
        "project": "project",
        "cycle": "cycle",
    },
    # Linear's *state types*, which `state` accepts alongside state names.
    open_states=("triage", "backlog", "unstarted", "started"),
    search_fields=(
        "id",
        "title",
        "description",
        "url",
        "priority",
        "estimate",
        "status",
        "statusType",
        "labels",
        "assignee",
        "project",
        "projectId",
        "team",
        "teamId",
        "parentId",
        "cycleId",
        "createdAt",
        "updatedAt",
        "dueDate",
    ),
    ingest_map={
        "id": "id",
        "url": "url",
        "title": "title",
        "body": "description",
        "status": "status",
        "status_type": "statusType",
        "labels": "labels",
        "assignee": "assignee",
        "project": "project",
        "team": "team",
        "parent": "parentId",
        "priority": "priority",
        "estimate": "estimate",
        "updated_at": "updatedAt",
    },
    items_key="issues",
    next_cursor_key="nextCursor",
    # `fields` is a closed enum on this tool and has no `identifier` member, so
    # WEB-123 has to come out of the URL.
    identifier_url_pattern=r"/issue/([A-Z][A-Z0-9]*-\d+)",
    url_patterns=(
        ("project", r"linear\.app/[^/]+/project/[^/]*?-?([0-9a-f]{8,})"),
        ("team", r"linear\.app/[^/]+/team/([A-Z0-9]+)"),
    ),
    notes="One verb creates and updates; passing an existing id is what makes it an update.",
)

GITHUB = Tracker(
    name="github",
    label="GitHub Issues",
    create_tool="create_issue",
    update_tool="update_issue",
    search_tool="search_issues",
    get_tool="get_issue",
    comment_tool="add_issue_comment",
    server_candidates=("github",),
    field_map={"title": "title", "body": "body", "status": "state", "labels": "labels", "assignee": "assignees"},
    scope_map={"owner": "owner", "repo": "repo"},
    update_key="issue_number",
    id_key="number",
    url_key="html_url",
    identifier_key="number",
    # GitHub has no priority field; severity is carried as a label instead.
    priority_map={},
    default_status_map={
        "open": "open",
        "in-progress": "open",
        "blocked": "open",
        "done": "closed",
        "deferred": "open",
        "cancelled": "closed",
    },
    supports_project=False,
    url_patterns=(("repo", r"github\.com/[^/]+/([^/#?]+)"), ("owner", r"github\.com/([^/]+)/")),
    notes=(
        "Only open and closed exist. Everything finer has to live in labels. "
        "No pull shape declared: the search argument names were not verified against a live tool "
        "schema, and a fetch plan built on a guessed one fails at the MCP call with no useful "
        "message. Supply one via tracker/providers/github.json to enable /triage fetch."
    ),
)

JIRA = Tracker(
    name="jira",
    label="Jira",
    create_tool="create_issue",
    update_tool="update_issue",
    search_tool="search_issues",
    get_tool="get_issue",
    comment_tool="add_comment",
    server_candidates=("jira", "atlassian"),
    field_map={
        "title": "summary",
        "body": "description",
        "status": "status",
        "labels": "labels",
        "priority": "priority",
        "assignee": "assignee",
    },
    scope_map={"project": "projectKey"},
    update_key="issueKey",
    id_key="key",
    url_key="self",
    identifier_key="key",
    priority_map={"critical": 1, "high": 2, "normal": 3, "medium": 3, "low": 4, "suggestion": 4, "warning": 3},
    default_status_map={
        "open": "To Do",
        "in-progress": "In Progress",
        "blocked": "Blocked",
        "done": "Done",
        "deferred": "Backlog",
        "cancelled": "Cancelled",
    },
    notes=(
        "Transitions are workflow-specific; status_map almost always needs overriding per project. "
        "No pull shape declared, for the same reason as GitHub: supply one via "
        "tracker/providers/jira.json to enable /triage fetch."
    ),
)

FILE = Tracker(
    name="file",
    label="Local file",
    remote=False,
    priority_map={"critical": 1, "high": 2, "normal": 3, "warning": 3, "low": 4, "suggestion": 4},
    default_status_map={status: status for status in STATUSES},
    notes=(
        "No tracker. Issues stay in the local queue and its generated digest. "
        "The default, so that surfacing works with nothing configured."
    ),
)

TRACKERS: dict[str, Tracker] = {tracker.name: tracker for tracker in (LINEAR, GITHUB, JIRA, FILE)}

DEFAULT_TRACKER = FILE

_ALIASES = {
    "linearapp": "linear",
    "gh": "github",
    "githubcom": "github",
    "githubissues": "github",
    "atlassian": "jira",
    "none": "file",
    "local": "file",
    "off": "file",
    "": "file",
}


def _normalise(name: str | None) -> str:
    return "".join(char for char in str(name or "").strip().lower() if char.isalnum())


def get_tracker(name: str | None) -> Tracker:
    """Look up a tracker by canonical name or common alias."""
    key = _normalise(name)
    return TRACKERS.get(_ALIASES.get(key, key), DEFAULT_TRACKER)


def load_overlays(root: Path) -> dict[str, Tracker]:
    """Providers declared as JSON, so adding one needs no code change.

    Every field on `Tracker` is data. A tracker whose *call shape* differs - one
    needing two calls to create an issue - still needs Python, and should get a
    built-in entry above rather than an overlay that cannot express it.
    """
    directory = engineering_root(root) / "tracker" / "providers"
    if not directory.is_dir():
        return {}
    found: dict[str, Tracker] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not data.get("name"):
            continue
        base = TRACKERS.get(_normalise(data.get("extends")))
        merged = {**({} if base is None else base.__dict__), **data}
        merged.pop("extends", None)
        known = {key: value for key, value in merged.items() if key in Tracker.__dataclass_fields__}
        for tuple_field in ("server_candidates", "url_patterns"):
            if isinstance(known.get(tuple_field), list):
                known[tuple_field] = tuple(
                    tuple(item) if isinstance(item, list) else item for item in known[tuple_field]
                )
        try:
            found[str(known["name"])] = Tracker(**known)
        except TypeError:
            continue
    return found


def all_trackers(root: Path | None = None) -> dict[str, Tracker]:
    return {**TRACKERS, **(load_overlays(root) if root else {})}


def resolve_tracker(root: Path, settings: Mapping[str, Any], override: str | None = None) -> tuple[Tracker, str]:
    """The tracker to use, and the evidence for choosing it.

    Returning the reason alongside is the same discipline `resolve_dialect` uses: a
    wrong guess should be visible in the output rather than silently deciding where
    every issue gets filed.
    """
    registry = all_trackers(root)
    if override:
        return registry.get(_ALIASES.get(_normalise(override), _normalise(override)), DEFAULT_TRACKER), (
            f"--provider {override}"
        )
    declared = settings.get("provider")
    if declared:
        key = _ALIASES.get(_normalise(declared), _normalise(declared))
        if key in registry:
            return registry[key], f"settings.json issue_filing.provider: {declared}"
        return DEFAULT_TRACKER, f"unknown provider {declared!r}; fell back to the local file provider"
    if (engineering_root(root) / "ledger" / "linear-config.json").is_file():
        return LINEAR, "ledger/linear-config.json is present"
    return DEFAULT_TRACKER, "no provider configured; issues stay in the local queue"


def parse_scope_url(tracker: Tracker, url: str) -> dict[str, str]:
    """Scope fields pulled out of a pasted URL.

    This is what makes JOS-31's "LINEAR_PROJECT_ID **or** LINEAR_PROJECT_URL" one
    code path. A human copying a URL out of the browser is the common case.
    """
    found: dict[str, str] = {}
    for key, pattern in tracker.url_patterns:
        match = re.search(pattern, url or "")
        if match:
            found[key] = match.group(1)
    return found


def qualified_tool(tracker: Tracker, verb: str, server: str | None) -> str:
    """`mcp__<server>__<verb>`, or an empty string when the server is unknown."""
    if not tracker.remote or not verb or not server:
        return ""
    return f"mcp__{server}__{verb}"


def tool_candidates(tracker: Tracker, verb: str, server: str | None) -> list[str]:
    """Every spelling of a verb worth trying, configured server first.

    Hooks cannot detect which MCP servers are connected, so the model has to try.
    Listing the candidates is honest about that rather than pretending one name is
    correct.
    """
    if not tracker.remote or not verb:
        return []
    servers = [server, *tracker.server_candidates] if server else list(tracker.server_candidates)
    seen: list[str] = []
    for name in servers:
        candidate = f"mcp__{name}__{verb}"
        if name and candidate not in seen:
            seen.append(candidate)
    return seen
