#!/usr/bin/env python3
"""Check that what the documentation says exists, exists.

Written after an audit found that `ai-utilities/skills/audit-resolver` routes its
findings to four plugins and two agents that are not in this marketplace, and tells
the reader to install them from a marketplace that is not this one. None of it was
detectable, because nothing had ever compared a name written in prose against the
set of names that exist.

Two classes of reference, deliberately held to different standards, because a
measurement over this repo's 198 markdown files said they deserve different ones:

  Closed-namespace tokens - a plugin, skill, agent, command, marketplace or
  `${CLAUDE_PLUGIN_ROOT}` path. The set of valid answers is finite and built from
  the filesystem on every run, so a miss is nearly always real. Measured 90%
  precision. These are errors, and they are meant to block a commit.

  Filesystem paths - anything that looks like a path in prose. The set of valid
  answers includes every file in whatever repository the document is *about*,
  which is not this one. Measured 3% precision naively, 15% with bare basenames
  dropped. These are warnings, and they never block.

Shipping both at error strength would have buried eight real findings under 278
false ones, and `anti-slop-check.py` already recorded what happens then: a checker
that guesses produces noise, and noise gets ignored.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eng_common import SCAN_PRUNE_DIRS, git_files, read_json_safe, relpath

# `_unreleased/` holds candidate plugins that point at a different upstream repo and
# are excluded from ruff, pre-commit, yamllint and every marketplace manifest. Their
# documentation describes plugins this marketplace does not ship, so checking it
# against this marketplace's namespaces would report the entire tree as broken.
PRUNE_DIRS = SCAN_PRUNE_DIRS | {"_unreleased", ".claude", ".agents", ".github"}

# The first path segment of a generated workspace artifact. A document naming
# `ledger/action-items.json` is naming an output, not a file in this repository, so
# resolving it against the repo is guaranteed to miss. Derived from the directory
# list in `references/workspace-contract.md`.
WORKSPACE_SEGMENTS = frozenset(
    {
        ".project",
        "profile",
        "lifecycle",
        "context",
        "initiatives",
        "decisions",
        "handoffs",
        "hygiene",
        "ledger",
        "council",
        "questions",
        "dashboards",
        "reports",
        "audits",
        "tracker",
    }
)

# Left-hand sides that look like `plugin:name` but are a tool-permission token, a
# metavariable, or a URL port. Each entry earns its place by having been measured as
# a false positive on this repository.
TOOL_PERMISSION_PREFIXES = frozenset(
    {
        "bash",
        "git",
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "node",
        "python",
        "python3",
        "sh",
        "pwsh",
        "cat",
        "wc",
        "ls",
        "find",
        "grep",
        "mkdir",
        "cp",
        "rm",
        "zip",
        "unzip",
        "test",
        "timeout",
        "mypy",
        "pyright",
        "ruff",
        "supabase",
        "docker",
        "make",
    }
)

# Spellings that are metavariables by construction: no plugin is named "plugin", no
# file is named "path". Listing them is not a carve-out for any one document - a
# token in this set cannot name a real thing anywhere.
PLACEHOLDER_TOKENS = frozenset(
    {
        "plugin:skill",
        "plugin:name",
        "plugin:command",
        "plugin:agent",
        "namespace/plugin:name",
        "path:line",
        "file:line",
        "id:slug",
        "key:value",
        "name:value",
        "table:column",
        "type:scope",
        "owner:repo",
    }
)

# Metavariable markers. A reference containing one of these is a template, not a
# claim about something that exists.
_METAVARIABLE = re.compile(r"[<>*|]|\{\{|\$\{(?!CLAUDE_PLUGIN_ROOT\})|YYYY|HHMMSS|MM-DD|\.\.\.")

_CODE_FENCE = re.compile(r"^\s*(?:```|~~~)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"

# `plugin:name`, whole-token inside backticks.
_QUALIFIED = re.compile(rf"^({_SLUG}):({_SLUG})$")
# `namespace/plugin:name` - the shape every fictional route in this repo was written
# in. Claude Code has no such addressing form, so the pattern itself is the finding.
_NAMESPACED = re.compile(rf"^({_SLUG}(?:/{_SLUG})+):([a-z0-9*][a-z0-9*-]*)$")
# `/plugin:command` in prose, not preceded by another slash or a colon.
_SLASH_COMMAND = re.compile(rf"(?<![/:\w])/({_SLUG}):({_SLUG})\b")
_WIKI_LINK = re.compile(r"\[\[([a-z0-9][a-z0-9:_-]*)\]\]")
# `@marketplace`, but only on a line that is actually installing a plugin.
_INSTALL_LINE = re.compile(r"/plugin\s+install")
_MARKETPLACE = re.compile(rf"@({_SLUG})")
_PLUGIN_ROOT_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`\"')]+)")
# A path-shaped inline-code token: at least one separator, and a file extension or a
# trailing slash. Bare basenames are excluded by construction - see the docstring.
_PATH_TOKEN = re.compile(r"^[A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@-]+)+/?$")

# Inline pragmas. A bare ignore is itself a finding: an exclusion with no stated
# reason is indistinguishable from an oversight six months later.
_PRAGMA_NEXT = re.compile(r"<!--\s*ref-check:\s*ignore-next(?:\s+reason=\"([^\"]*)\")?\s*-->")
_PRAGMA_INLINE = re.compile(r"<!--\s*ref-check:\s*(?:ignore|external)(?:\s+reason=\"([^\"]*)\")?\s*-->")


@dataclass(frozen=True)
class Namespaces:
    """Every name this marketplace can legitimately be referred to by.

    Rebuilt from the filesystem on each run rather than declared, so the checker
    cannot itself become the stale document it exists to catch.
    """

    plugins: frozenset[str]
    marketplaces: frozenset[str]
    skills: frozenset[str]
    agents: frozenset[str]
    commands: frozenset[str]
    qualified: frozenset[str]
    plugin_dirs: Mapping[str, Path]

    def member(self, plugin: str, name: str) -> bool:
        return f"{plugin}:{name}" in self.qualified


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    severity: str
    token: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "rule": self.rule,
            "severity": self.severity,
            "token": self.token,
            "message": self.message,
        }


def _plugin_dirs(root: Path) -> dict[str, Path]:
    """Directories holding a Claude plugin manifest, keyed by declared name."""
    found: dict[str, Path] = {}
    for manifest in sorted(root.glob("*/.claude-plugin/plugin.json")):
        data = read_json_safe(manifest)
        name = data.get("name")
        if isinstance(name, str) and name:
            found[name] = manifest.parent.parent
    return found


def build_namespaces(root: Path) -> Namespaces:
    dirs = _plugin_dirs(root)
    skills: set[str] = set()
    agents: set[str] = set()
    commands: set[str] = set()
    qualified: set[str] = set()

    for plugin, directory in dirs.items():
        for skill in sorted((directory / "skills").glob("*/SKILL.md")):
            name = skill.parent.name
            skills.add(name)
            qualified.add(f"{plugin}:{name}")
        for agent in sorted((directory / "agents").glob("*.md")):
            agents.add(agent.stem)
            qualified.add(f"{plugin}:{agent.stem}")
        for command in sorted((directory / "commands").glob("*.md")):
            commands.add(command.stem)
            qualified.add(f"{plugin}:{command.stem}")

    marketplaces: set[str] = set()
    catalog = read_json_safe(root / "marketplace" / "catalog.json")
    if isinstance(catalog.get("id"), str):
        marketplaces.add(catalog["id"])
    claude_marketplace = read_json_safe(root / ".claude-plugin" / "marketplace.json")
    if isinstance(claude_marketplace.get("name"), str):
        marketplaces.add(claude_marketplace["name"])

    return Namespaces(
        plugins=frozenset(dirs),
        marketplaces=frozenset(marketplaces),
        skills=frozenset(skills),
        agents=frozenset(agents),
        commands=frozenset(commands),
        qualified=frozenset(qualified),
        plugin_dirs=dict(dirs),
    )


def load_allowlist(root: Path) -> dict[str, Any]:
    """Class-level exclusions, from the repo root.

    Deliberately not under `.project/`: that whole tree is gitignored, so an
    allow-list living there would silence the checker on one machine and nowhere
    else - the exact asymmetry that lets a dead reference survive review.
    """
    data = read_json_safe(root / ".reference-allowlist.json")
    return {
        "tokens": frozenset(str(item) for item in data.get("tokens", []) if isinstance(item, str)),
        "prefixes": tuple(str(item) for item in data.get("prefixes", []) if isinstance(item, str)),
        "reasons": data.get("reasons", {}) if isinstance(data.get("reasons"), dict) else {},
    }


def markdown_files(root: Path, explicit: Iterable[Path] = ()) -> list[Path]:
    paths = [path if path.is_absolute() else root / path for path in explicit]
    if paths:
        return [path for path in paths if path.is_file() and path.suffix.lower() == ".md"]
    found: list[Path] = []
    for path in root.rglob("*.md"):
        if set(path.parts) & PRUNE_DIRS:
            continue
        found.append(path)
    return sorted(found)


def _owning_plugin_dir(path: Path, namespaces: Namespaces) -> Path | None:
    for directory in namespaces.plugin_dirs.values():
        try:
            path.relative_to(directory)
        except ValueError:
            continue
        return directory
    return None


def _path_index(root: Path) -> dict[str, list[str]]:
    """basename -> every tracked path ending in it, for suffix resolution."""
    index: dict[str, list[str]] = {}
    for tracked in git_files(root):
        index.setdefault(tracked.name, []).append(tracked.as_posix())
    return index


def _skip_path_class(path: Path, root: Path) -> str:
    """Why the path class is not checked in this file, or an empty string.

    Three whole-file exemptions, each measured. Examples and templates exist to show
    illustrative paths into a repository that is not this one. A changelog describes
    the state of the world when it was written, so `generate-erd.py` was real at the
    time and reporting it now is just wrong.
    """
    parts = set(path.parts)
    if "examples" in parts or "templates" in parts:
        return "illustrative paths under examples/ or templates/"
    if path.name == "CHANGELOG.md":
        return "a changelog describes historical state"
    if relpath(path, root).startswith(".project/"):
        return "generated workspace state"
    return ""


def _iter_lines(text: str) -> Iterable[tuple[int, str, bool]]:
    """(line number, text, inside a fenced code block)."""
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _CODE_FENCE.match(line):
            fenced = not fenced
            yield number, line, True
            continue
        yield number, line, fenced


def check_text(
    path: Path,
    text: str,
    root: Path,
    namespaces: Namespaces,
    allowlist: Mapping[str, Any],
    index: Mapping[str, list[str]],
    anchors: frozenset[str] = frozenset(),
) -> list[Finding]:
    rel = relpath(path, root)
    owner = _owning_plugin_dir(path, namespaces)
    path_skip = _skip_path_class(path, root)
    allowed_tokens = allowlist["tokens"]
    allowed_prefixes = allowlist["prefixes"]
    findings: list[Finding] = []
    suppress_next = False

    def allowed(token: str) -> bool:
        return token in allowed_tokens or any(token.startswith(prefix) for prefix in allowed_prefixes)

    for number, line, fenced in _iter_lines(text):
        if suppress_next:
            suppress_next = False
            continue
        pragma = _PRAGMA_NEXT.search(line) or _PRAGMA_INLINE.search(line)
        # An exclusion with no stated reason is indistinguishable from an oversight
        # six months later, so the checker reports its own unexplained suppressions.
        if pragma and not (pragma.group(1) or "").strip():
            findings.append(
                Finding(
                    rel,
                    number,
                    "unexplained-suppression",
                    "error",
                    "ref-check pragma",
                    'A ref-check pragma must state why: reason="...".',
                )
            )
        if _PRAGMA_NEXT.search(line):
            suppress_next = True
            continue
        inline_suppressed = bool(_PRAGMA_INLINE.search(line))

        # --- closed-namespace classes (errors) ---------------------------------
        for token in _INLINE_CODE.findall(line):
            token = token.strip()
            if not token or inline_suppressed or allowed(token) or token in PLACEHOLDER_TOKENS:
                continue
            if _METAVARIABLE.search(token):
                continue

            namespaced = _NAMESPACED.match(token)
            if namespaced:
                findings.append(
                    Finding(
                        rel,
                        number,
                        "namespaced-plugin-ref",
                        "error",
                        token,
                        "Claude Code has no `namespace/plugin:name` addressing form. "
                        "Use `plugin:name`, and only for a plugin this marketplace ships.",
                    )
                )
                continue

            qualified = _QUALIFIED.match(token)
            if qualified:
                plugin, name = qualified.groups()
                if plugin in TOOL_PERMISSION_PREFIXES:
                    continue
                if plugin not in namespaces.plugins:
                    findings.append(
                        Finding(
                            rel,
                            number,
                            "unknown-plugin",
                            "error",
                            token,
                            f"No plugin named `{plugin}` in this marketplace. "
                            f"Known: {', '.join(sorted(namespaces.plugins))}.",
                        )
                    )
                elif not namespaces.member(plugin, name):
                    findings.append(
                        Finding(
                            rel,
                            number,
                            "unknown-plugin-member",
                            "error",
                            token,
                            f"`{plugin}` ships no skill, agent or command named `{name}`.",
                        )
                    )
                continue

            if token.startswith("${CLAUDE_PLUGIN_ROOT}/"):
                findings.extend(_check_plugin_root(rel, number, token, owner))
                continue

            # --- filesystem path class (warnings) ------------------------------
            if path_skip or fenced:
                continue
            # A backticked span is either a bare path or a command containing one.
            # `python tests/scripts/test_smoke.py` names a script exactly as much as
            # a bare path does, and it is the form the dead verifier references were
            # written in. Flags and metavariables fall out via the checks below.
            for word in [token] if _PATH_TOKEN.match(token) else token.split():
                if not _PATH_TOKEN.match(word) or _METAVARIABLE.search(word):
                    continue
                findings.extend(_check_repo_path(rel, number, word, path, root, owner, anchors, index))

        # Patterns that are not whole inline-code tokens.
        if inline_suppressed:
            continue
        for plugin, command in _SLASH_COMMAND.findall(line):
            token = f"/{plugin}:{command}"
            if allowed(token) or plugin in TOOL_PERMISSION_PREFIXES:
                continue
            if f"{plugin}:{command}" in PLACEHOLDER_TOKENS:
                continue
            if plugin not in namespaces.plugins:
                findings.append(Finding(rel, number, "unknown-plugin", "error", token, f"No plugin named `{plugin}`."))
            elif not namespaces.member(plugin, command):
                findings.append(
                    Finding(
                        rel,
                        number,
                        "unknown-command",
                        "error",
                        token,
                        f"`{plugin}` ships no command named `{command}`.",
                    )
                )
        for name in _WIKI_LINK.findall(line):
            if allowed(name):
                continue
            bare = name.split(":")[-1]
            if bare in namespaces.skills or bare in namespaces.agents or bare in namespaces.commands:
                continue
            findings.append(
                Finding(rel, number, "unknown-wiki-link", "error", f"[[{name}]]", f"No skill or agent named `{bare}`.")
            )
        if _INSTALL_LINE.search(line):
            for market in _MARKETPLACE.findall(line):
                if market in namespaces.marketplaces or allowed(f"@{market}"):
                    continue
                findings.append(
                    Finding(
                        rel,
                        number,
                        "unknown-marketplace",
                        "error",
                        f"@{market}",
                        f"`@{market}` is not this marketplace. Known: {', '.join(sorted(namespaces.marketplaces))}.",
                    )
                )
        for tail in _PLUGIN_ROOT_PATH.findall(line):
            findings.extend(_check_plugin_root(rel, number, "${CLAUDE_PLUGIN_ROOT}/" + tail, owner))

    return findings


def _check_plugin_root(rel: str, number: int, token: str, owner: Path | None) -> list[Finding]:
    tail = token.split("}/", 1)[1].strip("`\"' ")
    if not tail or _METAVARIABLE.search(tail):
        return []
    if owner is None:
        return []
    if (owner / tail).exists():
        return []
    return [
        Finding(
            rel,
            number,
            "missing-plugin-file",
            "error",
            token,
            f"`{tail}` does not exist under `{owner.name}`.",
        )
    ]


def _check_repo_path(
    rel: str,
    number: int,
    token: str,
    path: Path,
    root: Path,
    owner: Path | None,
    anchors: frozenset[str],
    index: Mapping[str, list[str]],
) -> list[Finding]:
    """A path reference, checked only when it can plausibly be about this repo.

    The discriminator is the first segment. `scripts/check-versions.mjs` starts in a
    directory this repository has, so a miss is a real claim about a file that
    should be here. `src/design-system/tokens.ts` starts in one it does not, because
    it names a file a skill will create in somebody else's repository - and
    resolving that here can only ever fail. Measured, this single rule removes about
    fifty of sixty-six false positives without losing a real one.
    """
    candidate = token.rstrip("/")
    first = candidate.split("/", 1)[0]
    if first in WORKSPACE_SEGMENTS or first not in anchors:
        return []
    bases = [path.parent, root] + ([owner] if owner else [])
    if any((base / candidate).exists() for base in bases):
        return []
    matches = index.get(Path(candidate).name, [])
    if any(match.endswith(candidate) for match in matches):
        return []
    return [
        Finding(
            rel,
            number,
            "unresolved-path",
            "warning",
            token,
            f"`{candidate}` does not resolve relative to this file, its plugin, or the repository root.",
        )
    ]


def _path_anchors(root: Path, namespaces: Namespaces) -> frozenset[str]:
    """Top-level directory names a path reference may legitimately start in.

    The repository's own top level, plus every plugin's, because a plugin document
    writes `references/design-styles/` meaning a path under its own root.
    """
    names = {entry.name for entry in root.iterdir() if entry.is_dir() and not entry.name.startswith(".")}
    for directory in namespaces.plugin_dirs.values():
        names |= {entry.name for entry in directory.iterdir() if entry.is_dir() and not entry.name.startswith(".")}
    return frozenset(names)


def reference_check(root: Path, paths: Iterable[Path] = ()) -> dict[str, Any]:
    namespaces = build_namespaces(root)
    if not namespaces.plugins:
        # No plugin manifests under this root, so the closed namespaces are empty and
        # every `plugin:name` in the tree would read as unknown. Checking against a
        # namespace built from nothing is not a check; it is 42 false positives.
        return {
            "checked": False,
            "reason": f"no plugin manifests found under {relpath(root, root) or root.name}; "
            "run this against the marketplace root",
            "files_checked": 0,
            "error_count": 0,
            "warning_count": 0,
            "errors": [],
            "warnings": [],
            "blocking": False,
        }
    allowlist = load_allowlist(root)
    index = _path_index(root)
    anchors = _path_anchors(root, namespaces)
    findings: list[Finding] = []
    files = markdown_files(root, paths)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(check_text(path, text, root, namespaces, allowlist, index, anchors))

    # The same token can appear in two backtick spans on one line. That is one
    # problem to fix, not two, and counting it twice inflates every total downstream.
    findings = list(dict.fromkeys(findings))
    errors = [item for item in findings if item.severity == "error"]
    warnings = [item for item in findings if item.severity == "warning"]
    return {
        "checked": True,
        "files_checked": len(files),
        "namespaces": {
            "plugins": sorted(namespaces.plugins),
            "marketplaces": sorted(namespaces.marketplaces),
            "skills": len(namespaces.skills),
            "agents": len(namespaces.agents),
            "commands": len(namespaces.commands),
        },
        "error_count": len(errors),
        "warning_count": len(warnings),
        # Only the closed-namespace classes block. The path class was measured at
        # 15% precision even after exclusions, which is not a standard anything
        # should be committed against.
        "blocking": bool(errors),
        "errors": [item.as_dict() for item in errors],
        "warnings": [item.as_dict() for item in warnings],
        "reference": "references/reference-check-rules.md",
    }


def reference_check_scoped(root: Path, path: str = "", files: Iterable[str] = ()) -> dict[str, Any]:
    """Whole-repo when nothing is named, otherwise only the named markdown files.

    The PostToolUse hook fires on every edit, including to Python and JSON. Without
    this guard an empty markdown scope would fall through to `markdown_files`'s
    no-arguments branch and rescan all 198 documents after every source edit.
    """
    named = [Path(item) for item in (list(files) or ([path] if path else []))]
    if named and not any(item.suffix.lower() == ".md" for item in named):
        return {
            "checked": False,
            "reason": "no markdown file in scope",
            "error_count": 0,
            "warning_count": 0,
            "errors": [],
            "warnings": [],
            "blocking": False,
        }
    return reference_check(root, named)


def description_drift(root: Path) -> list[Finding]:
    """A plugin's description, compared across every surface that carries one.

    `bump-version` keeps versions in lockstep across five files and does not touch
    descriptions, and `validate_platform_surfaces` never compares them. So a plugin
    can be described five different ways with nothing complaining - which is how
    this marketplace came to advertise a Supabase-shaped audit on a skill that no
    longer had one.
    """
    findings: list[Finding] = []
    claude_marketplace = read_json_safe(root / ".claude-plugin" / "marketplace.json")
    marketplace_by_name = {
        entry.get("name"): entry.get("description")
        for entry in claude_marketplace.get("plugins", [])
        if isinstance(entry, dict)
    }
    for plugin, directory in sorted(_plugin_dirs(root).items()):
        surfaces: dict[str, str] = {}
        claude = read_json_safe(directory / ".claude-plugin" / "plugin.json")
        if claude.get("description"):
            surfaces[".claude-plugin/plugin.json"] = str(claude["description"])
        codex = read_json_safe(directory / ".codex-plugin" / "plugin.json")
        if codex.get("description"):
            surfaces[".codex-plugin/plugin.json"] = str(codex["description"])
        if marketplace_by_name.get(plugin):
            surfaces[".claude-plugin/marketplace.json"] = str(marketplace_by_name[plugin])
        # `marketplace/plugins/<id>.json` carries a `summary`, not a `description`.
        # A deliberately shorter form is not drift, and comparing the two fields
        # would report every plugin here forever.

        distinct = {value.strip() for value in surfaces.values()}
        if len(distinct) > 1:
            where = ", ".join(sorted(surfaces))
            findings.append(
                Finding(
                    f"{plugin}/.claude-plugin/plugin.json",
                    1,
                    "description-drift",
                    "warning",
                    plugin,
                    f"`{plugin}` is described {len(distinct)} different ways across {where}. "
                    "Nothing keeps these in step, so they have to be edited together.",
                )
            )
    return findings


_VERSION_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|\s*(\d+\.\d+\.\d+)\s*\|")


def version_drift(root: Path) -> list[Finding]:
    """Version numbers quoted in prose, against the manifests.

    `bump-version` writes five files and does not know about the table in
    `README.md`, so a bump silently leaves the front page advertising the old
    version. Found exactly that: the README still said `ai-utilities 0.1.0` after
    the bump to 0.2.0.
    """
    manifests = {
        name: read_json_safe(directory / ".claude-plugin" / "plugin.json").get("version")
        for name, directory in _plugin_dirs(root).items()
    }
    findings: list[Finding] = []
    for path in sorted(root.glob("*.md")) + sorted(root.glob("*/README.md")):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            match = _VERSION_ROW.match(line)
            if not match:
                continue
            plugin, quoted = match.groups()
            actual = manifests.get(plugin)
            if actual and quoted != actual:
                findings.append(
                    Finding(
                        relpath(path, root),
                        number,
                        "version-drift",
                        "warning",
                        f"{plugin} {quoted}",
                        f"`{plugin}` is {actual} in its manifest. `bump-version` does not edit prose.",
                    )
                )
    return findings


def _scoped_counts(root: Path, namespaces: Namespaces) -> dict[str, dict[str, int]]:
    """Inventory totals for the repository and for each plugin separately.

    A plugin README counting its own four skills is correct; comparing it against
    the marketplace total of twenty-three is the false positive that makes a
    cardinality check useless. The scope is the document's location.
    """
    scoped: dict[str, dict[str, int]] = {
        "": {
            "plugins": len(namespaces.plugins),
            "skills": len(namespaces.skills),
            "agents": len(namespaces.agents),
            "commands": len(namespaces.commands),
        }
    }
    for plugin, directory in namespaces.plugin_dirs.items():
        scoped[plugin] = {
            "plugins": len(namespaces.plugins),
            "skills": len(list(directory.glob("skills/*/SKILL.md"))),
            "agents": len(list(directory.glob("agents/*.md"))),
            "commands": len(list(directory.glob("commands/*.md"))),
        }
    return scoped


def claim_check(root: Path, paths: Iterable[Path] = ()) -> dict[str, Any]:
    """Counting claims in inventory documents, checked against the sets they count.

    Restricted to README files on purpose. A number next to the word "skill" is an
    inventory claim in a README and an illustration anywhere else - "a plugin with
    one skill" in a design guide is not a statement about this repository, and
    flagging it is exactly the guessing that gets a checker ignored.

    Only cardinality lives here. Existence claims are the reference checker above.
    Behavioural claims - "this is fast", "the hook fires before Y" - have no
    enumerable other side; verifying them means running the thing, which is the
    audit's job, not this module's.
    """
    namespaces = build_namespaces(root)
    scoped = _scoped_counts(root, namespaces)
    findings: list[Finding] = []
    for path in markdown_files(root, paths):
        if path.name != "README.md" or _skip_path_class(path, root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        owner = _owning_plugin_dir(path, namespaces)
        scope = owner.name if owner else ""
        findings.extend(_check_counts(relpath(path, root), text, scoped.get(scope, scoped[""]), scope or "repository"))
    findings.extend(description_drift(root))
    findings.extend(version_drift(root))
    return {
        "checked": True,
        "counts": scoped,
        "warning_count": len(findings),
        "blocking": False,
        "warnings": [item.as_dict() for item in findings],
    }


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
_COUNT_CLAIM = re.compile(
    r"\b(\d{1,3}|" + "|".join(_NUMBER_WORDS) + r")\s+(plugins?|skills?|agents?|commands?)\b",
    re.IGNORECASE,
)


def _check_counts(rel: str, text: str, counts: Mapping[str, int], scope: str) -> list[Finding]:
    findings: list[Finding] = []
    for number, line, fenced in _iter_lines(text):
        if fenced or _PRAGMA_INLINE.search(line):
            continue
        for raw, noun in _COUNT_CLAIM.findall(line):
            key = noun.lower().rstrip("s") + "s"
            expected = counts.get(key)
            if expected is None:
                continue
            claimed = _NUMBER_WORDS.get(raw.lower()) if not raw.isdigit() else int(raw)
            if claimed is None or claimed == expected:
                continue
            findings.append(
                Finding(
                    rel,
                    number,
                    "count-mismatch",
                    "warning",
                    f"{raw} {noun}",
                    f"{scope} has {expected} {key}, not {claimed}.",
                )
            )
    return findings
