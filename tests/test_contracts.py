"""Contracts between the marketplace surfaces, and between each surface and disk.

`test_marketplace.py` proves the four surfaces list the *same plugin names*.
Nothing proved they agree on anything else, and the repository has already
shipped the consequence: one plugin was `Developer Tools` in three files and
`engineering` in its own catalog record, because version and homepage were
cross-checked and category simply was not.

The surfaces are maintained separately on purpose (ADR-0001), so the only thing
that can hold them together is a comparison. Four of them plus six plugin
manifests is ten hand-edited files per plugin change; every field below is one
that a human has to remember to copy and that no generator writes.

Where an existing checker already covers a field, this suite does not repeat it.
Where an existing checker covers it *advisorily* - `description_drift` is a
non-blocking warning inside `claim-check`, and `claim-check` is a hook that
`scripts/validate-repo.py` never runs - it is repeated here at assertion
strength, because a warning nobody runs is not a check.

**On the two Codex marketplaces carrying no version and no description:** that is
deliberate, documented at `CONTRIBUTING.md:63` and in ADR-0001, and
`bump-version` is written to leave them alone. The invariant asserted here is
therefore the *absence* of those fields. A test demanding versions on those two
surfaces would fail correctly-designed code.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# The two Codex marketplace manifests. Byte-for-byte copies of each other by
# design; Codex reads whichever one it finds first.
CODEX_MARKETPLACES = (ROOT / "marketplace.json", ROOT / ".agents" / "plugins" / "marketplace.json")
CLAUDE_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
CATALOG = ROOT / "marketplace" / "catalog.json"

# Component directories a plugin manifest may point at, and the glob a client
# actually loads out of each. Claude Code discovers these by convention and
# needs no declaration; Codex is told explicitly.
#
# The glob matters: a directory that is merely non-empty - one stray README -
# declares components and ships none, which reads as coverage in exactly the way
# an empty directory does.
COMPONENT_CONTENTS = {
    "skills": "*/SKILL.md",
    "commands": "*.md",
    "agents": "*.md",
    "hooks": "hooks.json",
}
COMPONENT_KEYS = tuple(COMPONENT_CONTENTS)

# `${CLAUDE_PLUGIN_ROOT}/<path>`, in either the exec form (`args`) or the shell
# form (`command`). The path ends at a quote or whitespace.
PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)")

# Directories that hold copies of components rather than components. `e2e`
# installs `playwright-core`, which vendors three SKILL.md files of its own -
# find them with a bare `**/SKILL.md` and this suite starts making assertions
# about somebody else's package.
NOT_OURS = frozenset({"node_modules", ".fixture", "tests", "examples", "templates", ".project"})

FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?$", re.DOTALL | re.MULTILINE)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    """Repo-relative POSIX spelling, for failure labels.

    `path.name` does not identify a surface here: `marketplace.json`,
    `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json` are
    three different files with one basename, so a subTest labelled
    `surface='marketplace.json'` names none of them and a failure does not say
    which file to open.
    """
    return path.relative_to(ROOT).as_posix()


def front_matter(path: Path) -> dict[str, str]:
    """The scalar keys of a Markdown front-matter block, values unquoted.

    Deliberately not `eng_common.parse_front_matter`: this suite spans all three
    plugins and must not depend on any one of them being importable.
    """
    match = FRONT_MATTER.search(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key_value = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if key_value:
            fields[key_value.group(1)] = key_value.group(2).strip().strip("\"'")
    return fields


def catalog_entries() -> list[dict[str, Any]]:
    return load(CATALOG)["plugins"]


def plugin_ids() -> list[str]:
    """Derived from the catalog, never hardcoded.

    A hardcoded list is a fourth place to forget to add a plugin, and the whole
    subject of this file is places people forget.
    """
    return [entry["id"] for entry in catalog_entries()]


def records() -> dict[str, dict[str, Any]]:
    return {entry["id"]: load(ROOT / entry["record"]) for entry in catalog_entries()}


def claude_entries() -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in load(CLAUDE_MARKETPLACE)["plugins"]}


def literal_from_source(path: Path, name: str) -> Any:
    """A module-level literal, read without importing the module.

    `workstreams.py` and `council.py` sit inside a plugin and import its shared
    helpers, so importing them here would make this suite depend on one plugin's
    `sys.path` being set up. The values wanted are plain literals; `ast` reads
    them with no import side effects at all.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name and node.value is not None:
                return ast.literal_eval(node.value)
    raise AssertionError(f"{path}: no module-level {name}")


def marketplace_module():
    """`scripts/johns-os-marketplace.py`, loaded by path because of the hyphens."""
    spec = importlib.util.spec_from_file_location("jos_marketplace", ROOT / "scripts" / "johns-os-marketplace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscoveryTests(unittest.TestCase):
    """Everything below iterates over what it finds, so what it finds must exist.

    Every other test in this file is a loop. A loop over an empty sequence is a
    passing test, so a typo'd glob or a renamed directory would turn this whole
    suite green while checking nothing - which is the failure mode the repository
    already recorded once, in the schema files that sat on disk unread while a
    weaker check stood in for them.
    """

    def test_the_discovery_this_suite_rests_on_finds_something(self) -> None:
        # A floor, not a count. `plugin_ids()` exists so the plugin list is never
        # hardcoded, and an equality here would contradict it: adding a fourth
        # plugin would fail the one test whose entire job is guarding against
        # empty loops. Losing one is what this catches.
        self.assertGreaterEqual(len(plugin_ids()), 3)
        self.assertEqual(set(records()), set(plugin_ids()))
        self.assertEqual(set(claude_entries()), set(plugin_ids()))
        self.assertGreaterEqual(len(list(ROOT.glob("*/skills/*/SKILL.md"))), len(plugin_ids()))
        self.assertTrue(list(ROOT.glob("*/commands/*.md")))
        self.assertTrue(list(ROOT.glob("*/agents/*.md")))

    def test_front_matter_parsing_reads_a_real_skill(self) -> None:
        # The parser is local to this file; if it silently returned `{}` the
        # identity tests below would compare None to None and pass.
        fields = front_matter(ROOT / "engineering-lifecycle" / "skills" / "review-change" / "SKILL.md")
        self.assertEqual(fields.get("name"), "review-change")
        self.assertTrue(fields.get("description"))


class CrossSurfaceAgreementTests(unittest.TestCase):
    """One plugin, one set of facts, across ten hand-edited files.

    `bump-version` keeps `version` in lockstep and `validate_platform_surfaces`
    compares `version` and `homepage`. Everything else below is copied by hand
    between files that nothing compares, which is exactly the shape of the
    category bug that already shipped.
    """

    def test_the_catalog_entry_and_its_record_name_the_same_plugin(self) -> None:
        # `catalog.json` names a plugin twice: as `id` and as a path to a record
        # that carries its own `id`. Renaming a plugin touches both, and the
        # validator only checks that the record file exists - not that it is the
        # record for the plugin the entry claims.
        for entry in catalog_entries():
            with self.subTest(plugin=entry["id"]):
                record = load(ROOT / entry["record"])
                self.assertEqual(record["id"], entry["id"])
                self.assertEqual(Path(entry["record"]).stem, entry["id"])

    def test_the_two_plugin_manifests_agree_on_every_shared_field(self) -> None:
        # `validate_codex_manifest` compares `name` and `version` only, and it
        # runs through `eng-life validate`, which is invoked without `--all` -
        # so even that pair is only ever checked for engineering-lifecycle.
        # homepage, license, author and description are checked by nobody.
        #
        # Presence is asserted before equality, and that is not belt-and-braces:
        # `claude.get(key) == codex.get(key)` is satisfied by `None == None`, so
        # deleting `license` from *both* manifests - the likeliest way it goes
        # missing, since the two are edited as a pair - kept this green while the
        # published plugin shipped with no licence field at all.
        for plugin_id in plugin_ids():
            claude = load(ROOT / plugin_id / ".claude-plugin" / "plugin.json")
            codex = load(ROOT / plugin_id / ".codex-plugin" / "plugin.json")
            for key in ("name", "version", "description", "homepage", "license", "author", "keywords"):
                with self.subTest(plugin=plugin_id, field=key):
                    self.assertIn(key, claude, f"{plugin_id}/.claude-plugin/plugin.json: no {key}")
                    self.assertIn(key, codex, f"{plugin_id}/.codex-plugin/plugin.json: no {key}")
                    self.assertEqual(claude[key], codex[key])

    def test_the_record_is_checked_against_the_claude_manifest_as_well(self) -> None:
        # `validate_plugin` resolves the record's `manifest` field, which points
        # at `.codex-plugin/plugin.json` for all three plugins. The Claude
        # manifest is the one users actually install from and is compared
        # against nothing, so a hand-edit there drifts silently.
        for plugin_id, record in records().items():
            claude = load(ROOT / plugin_id / ".claude-plugin" / "plugin.json")
            with self.subTest(plugin=plugin_id):
                self.assertEqual(claude["name"], record["id"])
                self.assertEqual(claude["version"], record["version"])
                self.assertEqual(claude["homepage"], record["homepage"])

    def test_the_display_name_is_one_string_on_all_four_surfaces(self) -> None:
        # Four different keys hold it - `name` in the record, `displayName` in
        # the Claude manifest and marketplace entry, `interface.displayName` in
        # the Codex manifest - so no tool can spot that they are the same fact.
        for plugin_id, record in records().items():
            codex = load(ROOT / plugin_id / ".codex-plugin" / "plugin.json")
            claude = load(ROOT / plugin_id / ".claude-plugin" / "plugin.json")
            with self.subTest(plugin=plugin_id):
                self.assertEqual(
                    {
                        record["name"],
                        claude["displayName"],
                        codex["interface"]["displayName"],
                        claude_entries()[plugin_id]["displayName"],
                    },
                    {record["name"]},
                )

    def test_the_category_reaches_the_codex_plugin_manifest_too(self) -> None:
        # `validate_categories` compares the three marketplace manifests and the
        # catalog record - the four surfaces the original drift was found in. It
        # does not know about `interface.category`, which is a fifth copy of the
        # same string and the one Codex actually shows a user.
        for plugin_id, record in records().items():
            codex = load(ROOT / plugin_id / ".codex-plugin" / "plugin.json")
            with self.subTest(plugin=plugin_id):
                self.assertEqual(codex["interface"]["category"], record["category"])

    def test_the_description_is_identical_wherever_it_appears(self) -> None:
        # `description_drift` covers this, at warning strength, inside
        # `claim-check` - a hook that `scripts/validate-repo.py` never runs and
        # that reports `blocking: False`. CONTRIBUTING calls the three copies out
        # by name because nothing keeps them in step; a warning nobody runs does
        # not keep them in step either.
        for plugin_id in plugin_ids():
            claude = load(ROOT / plugin_id / ".claude-plugin" / "plugin.json")
            codex = load(ROOT / plugin_id / ".codex-plugin" / "plugin.json")
            with self.subTest(plugin=plugin_id):
                self.assertEqual(
                    {claude["description"], codex["description"], claude_entries()[plugin_id]["description"]},
                    {claude["description"]},
                )

    def test_the_keywords_are_the_same_list_in_manifest_and_marketplace(self) -> None:
        # Order included: these are published verbatim, and a reordering that
        # looks harmless here is a diff in the marketplace listing.
        for plugin_id in plugin_ids():
            claude = load(ROOT / plugin_id / ".claude-plugin" / "plugin.json")
            with self.subTest(plugin=plugin_id):
                self.assertEqual(claude["keywords"], claude_entries()[plugin_id]["keywords"])


class SyntheticMarketplace:
    """A throwaway marketplace the real tooling can be pointed at.

    Shared by the two classes below rather than owned by one of them: asserting
    against the checked-in data proves only that nobody has broken it yet, and
    both the `bump-version` contract and the containment checks need a tree they
    are allowed to tamper with. Mixed into a `TestCase`, which is where
    `addCleanup` comes from.
    """

    def _codex_paths(self, root: Path) -> list[Path]:
        return [root / "marketplace.json", root / ".agents" / "plugins" / "marketplace.json"]

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _point_module_at(self, module, root: Path) -> None:
        """Redirect the module's path constants at a throwaway tree.

        They are computed once at import time from the module's own location, so
        every one of them has to move together or the tool reads the synthetic
        catalog and the real schemas.
        """
        originals = {name: getattr(module, name) for name in ("ROOT", "CATALOG", "SCHEMAS")}
        self.addCleanup(lambda: [setattr(module, name, value) for name, value in originals.items()])
        module.ROOT = root
        module.CATALOG = root / "marketplace" / "catalog.json"
        module.SCHEMAS = root / "marketplace" / "schemas"

    def _synthetic_marketplace(self, root: Path) -> None:
        """A one-plugin marketplace with every surface the real one has.

        Built rather than copied: copying the repository would make the test
        depend on the repository's current contents, and the point is the tool's
        behaviour, not this month's plugin list.
        """
        write = self._write

        schemas = root / "marketplace" / "schemas"
        schemas.mkdir(parents=True)
        for name in ("catalog.schema.json", "plugin.schema.json"):
            shutil.copyfile(ROOT / "marketplace" / "schemas" / name, schemas / name)

        write(
            root / "marketplace" / "catalog.json",
            {
                "id": "synthetic",
                "name": "synthetic",
                "description": "Synthetic marketplace.",
                "version": "0.0.1",
                "updated_at": "2026-01-01T00:00:00Z",
                "plugins": [{"id": "demo", "record": "marketplace/plugins/demo.json"}],
            },
        )
        write(
            root / "marketplace" / "plugins" / "demo.json",
            {
                "id": "demo",
                "name": "Demo",
                "summary": "A synthetic plugin.",
                "status": "local",
                "category": "Developer Tools",
                "version": "0.1.0",
                "homepage": "https://example.invalid",
                "path": "demo",
                "manifest": "demo/.codex-plugin/plugin.json",
                "source": {"type": "local", "url": ""},
                "capabilities": ["skills"],
                "tags": ["demo"],
                "risk": "low",
                "install": {"type": "local-path", "instructions": ["Use the local demo directory."]},
                "validation": {"commands": ["true"]},
            },
        )
        manifest = {"name": "demo", "version": "0.1.0", "homepage": "https://example.invalid"}
        write(root / "demo" / ".claude-plugin" / "plugin.json", dict(manifest))
        write(root / "demo" / ".codex-plugin" / "plugin.json", dict(manifest))
        write(
            root / ".claude-plugin" / "marketplace.json",
            {
                "name": "synthetic",
                "version": "0.0.1",
                "plugins": [
                    {
                        "name": "demo",
                        "source": "./demo",
                        "version": "0.1.0",
                        "homepage": "https://example.invalid",
                        "category": "Developer Tools",
                    }
                ],
            },
        )
        codex = {
            "name": "synthetic",
            "plugins": [
                {
                    "name": "demo",
                    "source": {"source": "local", "path": "./demo"},
                    "category": "Developer Tools",
                }
            ],
        }
        for path in self._codex_paths(root):
            write(path, codex)


class CodexSurfaceTests(SyntheticMarketplace, unittest.TestCase):
    """The two Codex manifests, and the fields they deliberately do not carry."""

    def test_the_two_codex_manifests_are_byte_identical(self) -> None:
        # They are copies, kept by hand, and Codex reads whichever it finds -
        # so a change applied to one and not the other means the answer depends
        # on which file the client looked at. Byte equality rather than parsed
        # equality on purpose: there is no reason for these two to differ even
        # in whitespace, and "same JSON, different bytes" is how a copy starts
        # drifting.
        first, second = (path.read_bytes() for path in CODEX_MARKETPLACES)
        self.assertEqual(
            first,
            second,
            f"{rel(CODEX_MARKETPLACES[0])} and {rel(CODEX_MARKETPLACES[1])} have diverged",
        )

    def test_the_codex_marketplaces_carry_no_version_and_no_description(self) -> None:
        """The intended shape is absence, and absence is what has to be asserted.

        Documented at `CONTRIBUTING.md:63` and in ADR-0001: these two files carry
        no version field, so `bump-version` does not touch them and adding one is
        how drift gets introduced rather than avoided. Nothing enforces that
        today, which means the next person to "fix the missing version" meets no
        resistance until Codex rejects the manifest.
        """
        for path in CODEX_MARKETPLACES:
            data = load(path)
            for key in ("version", "description"):
                with self.subTest(surface=rel(path), field=key):
                    self.assertNotIn(key, data)
            for plugin in data["plugins"]:
                for key in ("version", "description"):
                    with self.subTest(surface=rel(path), plugin=plugin["name"], field=key):
                        self.assertNotIn(key, plugin)

    def test_bump_version_leaves_the_codex_marketplaces_untouched(self) -> None:
        """The rule above, enforced against the tool rather than the current files.

        Asserting that the checked-in files have no version proves only that
        nobody has broken it yet. This runs `bump-version` over a synthetic
        marketplace and proves the tool itself will not introduce one - which is
        the property CONTRIBUTING relies on when it says to bump with the script
        and edit nothing by hand.
        """
        module = marketplace_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self._synthetic_marketplace(root)
            before = [path.read_bytes() for path in self._codex_paths(root)]

            self._point_module_at(module, root)
            with contextlib.redirect_stdout(io.StringIO()):
                code = module.command_bump_version(argparse.Namespace(plugin_id="demo", version="9.9.9"))

            self.assertEqual(code, 0, "the synthetic marketplace should validate after the bump")
            after = [path.read_bytes() for path in self._codex_paths(root)]
            self.assertEqual(after, before, "bump-version wrote to a Codex marketplace that carries no version")

            # And it did do the job it was asked to do, on the surfaces that
            # carry a version - otherwise "untouched" is satisfied by a no-op.
            for path in (
                root / "marketplace" / "plugins" / "demo.json",
                root / "demo" / ".claude-plugin" / "plugin.json",
                root / "demo" / ".codex-plugin" / "plugin.json",
            ):
                self.assertEqual(load(path)["version"], "9.9.9", str(path))
            self.assertEqual(load(root / ".claude-plugin" / "marketplace.json")["plugins"][0]["version"], "9.9.9")


class SourceContainmentTests(SyntheticMarketplace, unittest.TestCase):
    """`command_validate` run against sources that point outside the checkout.

    `SourcePathTests.test_no_source_escapes_the_repository` states the invariant
    about today's checked-in data, which never exercises the checker - and the
    checker did not have one. Every existence test in
    `scripts/johns-os-marketplace.py` was `(ROOT / declared).is_dir()`, which
    answers "does this exist" and not "is it ours".

    Two spellings, because they fail differently. `..` is the obvious one. The
    absolute one is worse and silent: `Path.__truediv__` discards the left
    operand entirely when the right side is absolute, so `"/etc"` on POSIX or
    `"C:\\Windows"` on Windows never involved ROOT at all. Both are exercised
    against a directory that really exists, so nothing passes merely because the
    target is absent.
    """

    def _tampered(self, mutate) -> tuple[int, str]:
        """Build a valid synthetic marketplace, apply `mutate`, then validate it.

        `mutate(root, escape)` is handed the marketplace root and a path to a
        real directory outside it.
        """
        module = marketplace_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / "repo"
            root.mkdir()
            # A complete, well-formed plugin directory that merely sits outside
            # the marketplace. Anything less and a rejection would prove only
            # that the escape target was incomplete, which is not the property
            # under test - `validate_platform_surfaces` reads a manifest out of
            # the directory it resolved, and would report *that* as missing.
            escape = base / "outside"
            manifest = {"name": "demo", "version": "0.1.0", "homepage": "https://example.invalid"}
            for kind in (".claude-plugin", ".codex-plugin"):
                self._write(escape / kind / "plugin.json", dict(manifest))
            self._synthetic_marketplace(root)
            mutate(root, escape)

            self._point_module_at(module, root)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = module.command_validate(argparse.Namespace())
            return code, stdout.getvalue() + stderr.getvalue()

    def test_the_untampered_synthetic_marketplace_validates(self) -> None:
        # The control. Without it, every rejection below could be the harness
        # failing rather than the containment check firing - and a checker that
        # refuses everything is no more use than one that refuses nothing.
        code, output = self._tampered(lambda root, escape: None)
        self.assertEqual(code, 0, output)

    def _record_path(self, root: Path, value: str) -> None:
        record = root / "marketplace" / "plugins" / "demo.json"
        self._write(record, {**load(record), "path": value})

    def _codex_source(self, root: Path, value: str) -> None:
        for path in self._codex_paths(root):
            data = load(path)
            data["plugins"][0]["source"]["path"] = value
            self._write(path, data)

    def _claude_source(self, root: Path, value: str) -> None:
        path = root / ".claude-plugin" / "marketplace.json"
        data = load(path)
        data["plugins"][0]["source"] = value
        self._write(path, data)

    def test_a_source_that_traverses_upward_is_refused_on_every_surface(self) -> None:
        for label, tamper in (
            ("record", self._record_path),
            ("codex marketplace", self._codex_source),
            ("claude marketplace", self._claude_source),
        ):
            with self.subTest(surface=label):
                code, output = self._tampered(lambda root, escape, t=tamper: t(root, "../outside"))
                self.assertEqual(code, 1, f"../outside validated clean:\n{output}")
                self.assertIn("demo", output)

    def test_an_absolute_source_is_refused_on_every_surface(self) -> None:
        # The one `..` filtering would miss. `ROOT / "/etc"` is `/etc`.
        for label, tamper in (
            ("record", self._record_path),
            ("codex marketplace", self._codex_source),
            ("claude marketplace", self._claude_source),
        ):
            with self.subTest(surface=label):
                code, output = self._tampered(lambda root, escape, t=tamper: t(root, str(escape)))
                self.assertEqual(code, 1, f"an absolute source validated clean:\n{output}")
                self.assertIn("demo", output)

    def test_bump_version_refuses_to_write_outside_the_repository(self) -> None:
        """The one place the record's `path` is used to write rather than read.

        `bump-version` staged `ROOT / path / ".claude-plugin" / "plugin.json"`,
        so the same absolute-path hole did not merely validate an escape - it
        set a version inside a file outside the checkout.
        """
        module = marketplace_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / "repo"
            root.mkdir()
            self._synthetic_marketplace(root)
            outside = base / "outside"
            manifest = outside / ".claude-plugin" / "plugin.json"
            self._write(manifest, {"name": "demo", "version": "0.1.0", "homepage": "https://example.invalid"})
            self._write(outside / ".codex-plugin" / "plugin.json", load(manifest))
            self._record_path(root, str(outside))

            self._point_module_at(module, root)
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                module.command_bump_version(argparse.Namespace(plugin_id="demo", version="9.9.9"))
            self.assertEqual(load(manifest)["version"], "0.1.0", "bump-version wrote outside the marketplace root")

    def test_the_ordinary_relative_spellings_are_still_accepted(self) -> None:
        # The other half of the guard. A containment check that rejected `./demo`
        # or a path that merely passes through a subdirectory would block every
        # legitimate record in the repository, and a checker that cries wolf gets
        # switched off.
        for spelling in ("demo", "./demo", "demo/../demo", ".//demo"):
            with self.subTest(path=spelling):
                code, output = self._tampered(lambda root, escape, value=spelling: self._record_path(root, value))
                self.assertEqual(code, 0, f"{spelling!r} was refused:\n{output}")


class SourcePathTests(unittest.TestCase):
    """Where a marketplace entry says the plugin is, against where it is."""

    @classmethod
    def setUpClass(cls) -> None:
        # The repository's own containment helper. Loaded once: the escape tests
        # below have to exercise `johns-os-marketplace.py` rather than restate
        # what `Path.resolve()` and `is_relative_to()` do, which is what they
        # used to do - a test that touched no repository code and could not fail.
        cls.marketplace = marketplace_module()

    def _sources(self) -> list[tuple[str, str, str, str]]:
        """(surface, plugin, declared path, kind) for every source across all four.

        `kind` is carried because the production checkers disagree on purpose:
        `validate_plugin` wants the record's `path` to be a directory and its
        `manifest` to be a file, and `validate_platform_surfaces` wants every
        marketplace `source` to be a directory. A single `exists()` here accepted
        a `source` of `"README.md"` that `johns-os-marketplace.py validate`
        rejects - the suite green while the tool it documents was red.
        """
        found: list[tuple[str, str, str, str]] = []
        for path in CODEX_MARKETPLACES:
            for plugin in load(path)["plugins"]:
                found.append((rel(path), plugin["name"], plugin["source"]["path"], "directory"))
        for name, entry in claude_entries().items():
            found.append((rel(CLAUDE_MARKETPLACE), name, entry["source"], "directory"))
        for entry in catalog_entries():
            record = load(ROOT / entry["record"])
            found.append((entry["record"], entry["id"], record["path"], "directory"))
            found.append((f"{entry['record']} (manifest)", entry["id"], record["manifest"], "file"))
        # Three marketplace manifests plus the record's two path fields, per
        # plugin. Stated as a count so a surface that stops being read here -
        # a renamed key, a manifest that moved - fails rather than shrinking the
        # loop that follows into a no-op.
        self.assertEqual(len(found), len(plugin_ids()) * 5, found)
        return found

    def test_every_declared_source_resolves_to_something_that_exists(self) -> None:
        # `validate_platform_surfaces` checks the three marketplace manifests.
        # The record's own `path` and `manifest` are checked by `validate_plugin`.
        # Collected here in one place so a fifth surface cannot be added without
        # the check coming with it - and asserted at the same strength the
        # production checkers use, because a weaker test that passes on data the
        # real validator refuses is not documenting the contract, it is hiding it.
        for surface, plugin, declared, kind in self._sources():
            with self.subTest(surface=surface, plugin=plugin):
                target = ROOT / declared
                found = target.is_dir() if kind == "directory" else target.is_file()
                self.assertTrue(found, f"{surface}: {plugin} points at {declared}, which is no {kind}")

    def test_no_source_escapes_the_repository(self) -> None:
        """Every declared source, run through the checker that now guards them.

        Every existence check in `johns-os-marketplace.py` used to be
        `(ROOT / value).is_dir()` with no containment test, so `../../somewhere`
        passed validation and the published marketplace told a client to install
        from outside the repo it cloned. `contained()` closed that, and this
        asserts the checked-in data satisfies the real helper - not a
        reimplementation of it that could drift from what the tool enforces.
        `SourceContainmentTests` covers the other direction, that the checker
        refuses when it should.
        """
        for surface, plugin, declared, _kind in self._sources():
            with self.subTest(surface=surface, plugin=plugin):
                self.assertIsNotNone(
                    self.marketplace.contained(declared),
                    f"{surface}: {plugin} declares {declared}, which resolves outside the repository",
                )

    def test_the_containment_helper_refuses_both_spellings_of_an_escape(self) -> None:
        # The assertion above passes trivially against a helper that returns a
        # Path for everything, so the helper itself is pinned here. Two spellings
        # because they fail differently: `..` is the obvious one, and the
        # absolute one is silent - `ROOT / "/etc"` is `/etc`, the anchor is
        # discarded, and `is_dir()` cheerfully confirms it.
        for escape in (
            "../elsewhere",
            "./engineering-lifecycle/../../elsewhere",
            str(ROOT.parent / "elsewhere"),
        ):
            with self.subTest(path=escape):
                self.assertIsNone(self.marketplace.contained(escape))

    def test_every_surface_names_the_same_directory_for_a_plugin(self) -> None:
        """Four surfaces declare where a plugin lives; nothing compared them.

        Each `source` and the record's `path` were only ever checked for
        resolving to something that exists, one surface at a time - so
        `./engineering-lifecycle` in one manifest and a stale
        `./engineering-lifecycle-old` in another would both resolve, both pass,
        and hand two clients two different directories depending on which surface
        their client reads. Resolved paths rather than strings, because `./demo`
        and `demo` are the same directory and both spellings are in use.
        """
        declared: dict[str, dict[str, Path]] = {}
        for path in CODEX_MARKETPLACES:
            for plugin in load(path)["plugins"]:
                declared.setdefault(plugin["name"], {})[rel(path)] = (ROOT / plugin["source"]["path"]).resolve()
        for name, entry in claude_entries().items():
            declared.setdefault(name, {})[rel(CLAUDE_MARKETPLACE)] = (ROOT / entry["source"]).resolve()
        for entry in catalog_entries():
            record = load(ROOT / entry["record"])
            declared.setdefault(entry["id"], {})[entry["record"]] = (ROOT / record["path"]).resolve()
        self.assertEqual(sorted(declared), sorted(plugin_ids()))
        for plugin_id, surfaces in sorted(declared.items()):
            with self.subTest(plugin=plugin_id):
                self.assertEqual(len(surfaces), 4, surfaces)
                self.assertEqual(len(set(surfaces.values())), 1, {key: str(v) for key, v in surfaces.items()})

    def test_the_record_manifest_lives_inside_the_directory_the_record_names(self) -> None:
        # `path` and `manifest` are two independent strings in one record, and
        # `validate_plugin` checks each on its own. A `manifest` left pointing at
        # the previous plugin's directory after a rename resolves, exists, is
        # inside the repository, and is compared against the `path` sitting two
        # lines above it by nobody.
        for entry in catalog_entries():
            record = load(ROOT / entry["record"])
            with self.subTest(plugin=entry["id"]):
                self.assertTrue(
                    (ROOT / record["manifest"]).resolve().is_relative_to((ROOT / record["path"]).resolve()),
                    f"{entry['record']}: manifest {record['manifest']} is outside path {record['path']}",
                )


class ComponentDeclarationTests(unittest.TestCase):
    """What a manifest says the plugin ships, against what is on disk."""

    def _declarations(self) -> list[tuple[str, str, str, str]]:
        """(plugin, manifest, key, declared path) for every component declaration.

        This is NOT 3 plugins x 2 manifests x 4 keys. All three
        `.claude-plugin/plugin.json` declare none of `COMPONENT_KEYS` - Claude
        Code discovers components by convention - so the loops that used to live
        in each test `continue`d past the entire Claude half and read as
        twenty-four checks while making four. The Claude manifests are still
        walked, because declaring there is legal and a declaration must be true
        wherever it is written; what is new is that the harvest is counted, so a
        Codex manifest that quietly drops its `skills` key fails here instead of
        shrinking every loop below into a passing no-op.

        A present-but-not-a-string declaration is a failure rather than something
        to skip: `"skills": true` loads nothing, and the old `isinstance` guard
        waved it through.
        """
        found: list[tuple[str, str, str, str]] = []
        for plugin_id in plugin_ids():
            for manifest_name in (".claude-plugin", ".codex-plugin"):
                manifest = load(ROOT / plugin_id / manifest_name / "plugin.json")
                for key in COMPONENT_KEYS:
                    if key not in manifest:
                        continue
                    declared = manifest[key]
                    self.assertIsInstance(declared, str, f"{plugin_id}/{manifest_name}: {key} is not a path")
                    found.append((plugin_id, f"{manifest_name}/plugin.json", key, declared))
        # Every plugin declares its skills directory to Codex, so one per plugin
        # is the floor. A floor and not a count: ai-utilities declares `commands`
        # as well, and ws-05 may add more.
        self.assertGreaterEqual(len(found), len(plugin_ids()), found)
        return found

    def test_every_component_directory_a_manifest_declares_exists(self) -> None:
        # Claude Code discovers components by convention; Codex is told, via
        # `"skills": "./skills/"` and friends. A declaration pointing at a
        # directory that was renamed or removed loads nothing and says nothing.
        for plugin_id, manifest_name, key, declared in self._declarations():
            with self.subTest(plugin=plugin_id, manifest=manifest_name, component=key):
                self.assertTrue((ROOT / plugin_id / declared.lstrip("./")).is_dir(), declared)

    def test_a_declared_component_directory_holds_components_of_that_kind(self) -> None:
        # Declaring `./commands/` and shipping nothing loadable in it is the same
        # outcome as not declaring it, but it reads as coverage. Checked against
        # the glob a client actually loads rather than `iterdir()`, because a
        # directory holding one stray README is non-empty and still ships nothing.
        for plugin_id, manifest_name, key, declared in self._declarations():
            with self.subTest(plugin=plugin_id, manifest=manifest_name, component=key):
                directory = ROOT / plugin_id / declared.lstrip("./")
                contents = sorted(directory.glob(COMPONENT_CONTENTS[key]))
                self.assertTrue(contents, f"{plugin_id}: declares {key} but {declared} holds no {key}")

    # OPEN QUESTION, tracked as ws-05 in
    # `.project/.engineering/tracker/workstreams.md` - "Does the Codex plugin
    # manifest honour agents/commands/hooks keys?". engineering-lifecycle ships
    # four slash commands (initiative, project-init, track, triage) that its
    # Codex manifest never declares; ai-utilities declares its single one. The
    # two cannot both be right, but which is wrong depends on whether Codex reads
    # the key at all, and that is unresolved.
    #
    # `skip` and deliberately not `expectedFailure`: the marker asserts an answer
    # ("engineering-lifecycle's manifest is the one to change") that nobody has
    # agreed, and it turns the build RED for whoever resolves ws-05 the other
    # way, because removing ai-utilities' declaration would make this an
    # unexpected success. The half of the invariant that is settled either way -
    # a declaration that exists must be true - is asserted unskipped above.
    @unittest.skip("ws-05: whether Codex honours the commands key is an open question, not a settled defect")
    def test_a_plugin_that_ships_commands_declares_them_to_codex(self) -> None:
        for plugin_id in plugin_ids():
            commands = sorted((ROOT / plugin_id / "commands").glob("*.md"))
            if not commands:
                continue
            codex = load(ROOT / plugin_id / ".codex-plugin" / "plugin.json")
            with self.subTest(plugin=plugin_id):
                self.assertIn(
                    "commands",
                    codex,
                    f"{plugin_id} ships {len(commands)} command(s) that its Codex manifest never declares",
                )

    def test_nothing_on_disk_falls_outside_a_declared_component_directory(self) -> None:
        # The inverse of the check above: a skill added under a directory no
        # manifest points at is invisible on at least one platform. Skills are
        # declared as a directory rather than one entry each, so this holds as
        # long as every SKILL.md lives under the declared root.
        for plugin_id in plugin_ids():
            plugin_root = ROOT / plugin_id
            declared = load(plugin_root / ".codex-plugin" / "plugin.json").get("skills")
            self.assertIsInstance(declared, str, f"{plugin_id}: no skills directory declared to Codex")
            skills_root = (plugin_root / str(declared).lstrip("./")).resolve()
            for skill in plugin_root.glob("**/SKILL.md"):
                if NOT_OURS.intersection(skill.parts):
                    continue
                with self.subTest(plugin=plugin_id, skill=skill.parent.name):
                    self.assertTrue(skill.resolve().is_relative_to(skills_root), str(skill))


class ComponentIdentityTests(unittest.TestCase):
    """A component's name on disk, against the name it declares."""

    def test_a_skill_directory_is_named_after_the_skill_inside_it(self) -> None:
        # Claude Code addresses a skill by its directory name and displays the
        # front-matter `name`. When they disagree, `/plugin:skill` and the name
        # in every document that mentions it are two different strings, and the
        # plugin's own validator only checks that `name` is present.
        for skill in sorted(ROOT.glob("*/skills/*/SKILL.md")):
            with self.subTest(skill=str(skill.relative_to(ROOT).as_posix())):
                self.assertEqual(front_matter(skill).get("name"), skill.parent.name)

    def test_a_command_file_is_named_after_the_command_inside_it(self) -> None:
        # `/track` is the filename, not the front matter - so a mismatch renames
        # the command without renaming anything that documents it.
        for command in sorted(ROOT.glob("*/commands/*.md")):
            with self.subTest(command=str(command.relative_to(ROOT).as_posix())):
                self.assertEqual(front_matter(command).get("name"), command.stem)

    def test_no_two_plugins_ship_a_component_of_the_same_name(self) -> None:
        """Unqualified names have to stay unique, because tooling flattens them.

        `references.build_namespaces` collapses every skill, agent and command
        across the marketplace into one unqualified set per kind. A name shipped
        by two plugins would make the reference checker accept a bare mention of
        it while the reader has no way to tell which plugin's copy is meant -
        and the checker exists precisely to catch names that resolve to nothing.
        """
        for kind, pattern, name_of in (
            ("skill", "*/skills/*/SKILL.md", lambda path: path.parent.name),
            ("agent", "*/agents/*.md", lambda path: path.stem),
            ("command", "*/commands/*.md", lambda path: path.stem),
        ):
            owners: dict[str, list[str]] = {}
            for path in sorted(ROOT.glob(pattern)):
                owners.setdefault(name_of(path), []).append(path.relative_to(ROOT).parts[0])
            duplicates = {name: sorted(where) for name, where in owners.items() if len(where) > 1}
            with self.subTest(kind=kind):
                self.assertEqual(duplicates, {}, f"duplicate {kind} names across plugins")

    def test_no_two_marketplace_entries_share_a_plugin_name(self) -> None:
        # `validate_catalog_shape` catches a duplicate `id` in the catalog. The
        # three marketplace manifests are lists with no such check, and a
        # duplicate there is a set-comparison away from invisible: every existing
        # cross-surface test compares `{names}`, which silently deduplicates.
        surfaces = [(rel(path), [p["name"] for p in load(path)["plugins"]]) for path in CODEX_MARKETPLACES]
        surfaces.append((rel(CLAUDE_MARKETPLACE), [p["name"] for p in load(CLAUDE_MARKETPLACE)["plugins"]]))
        surfaces.append((rel(CATALOG), [entry["id"] for entry in catalog_entries()]))
        for surface, names in surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(len(names), len(set(names)), f"{surface}: duplicate plugin name")


class HookRegistrationTests(unittest.TestCase):
    """Every hook a plugin registers, against the script it names.

    `validate-plugin.py` has a `validate_hooks` that does this, and nothing runs
    it over more than one plugin: `scripts/validate-repo.py` calls
    `eng-life validate`, which passes `--root <engineering-lifecycle>` and never
    `--all`. So `ai-utilities` - the plugin with the broadest tool permissions in
    the marketplace, and the only one whose hooks shell out - has never had a
    hook target checked by anything.
    """

    def _registrations(self) -> list[tuple[str, str, dict[str, Any]]]:
        found: list[tuple[str, str, dict[str, Any]]] = []
        for plugin_id in plugin_ids():
            path = ROOT / plugin_id / "hooks" / "hooks.json"
            if not path.is_file():
                continue
            for event, entries in load(path)["hooks"].items():
                for entry in entries:
                    for hook in entry.get("hooks", []):
                        found.append((plugin_id, event, hook))
        return found

    def test_the_marketplace_registers_hooks_at_all(self) -> None:
        # Guards every other test in this class against passing vacuously if the
        # discovery above stops finding anything.
        self.assertTrue(self._registrations())

    def test_every_hook_names_a_script_that_exists(self) -> None:
        for plugin_id, event, hook in self._registrations():
            targets = PLUGIN_ROOT_REF.findall(str(hook.get("command", "")))
            for arg in hook.get("args", []):
                targets.extend(PLUGIN_ROOT_REF.findall(str(arg)))
            with self.subTest(plugin=plugin_id, event=event, command=hook.get("command")):
                self.assertTrue(targets, "hook names no ${CLAUDE_PLUGIN_ROOT} target")
                for target in targets:
                    self.assertTrue((ROOT / plugin_id / target).is_file(), f"{plugin_id}: missing {target}")


class AgentBindingTests(unittest.TestCase):
    """Agents named by code and prose, against the agent files on disk."""

    def test_every_agent_the_router_can_choose_exists(self) -> None:
        """`AGENT_ROUTES` is the one place an agent name is chosen by code.

        `triage.py` falls back to `general-purpose` when a routed agent's file is
        missing, so a renamed agent does not crash - it quietly degrades every
        workstream that would have routed to it into a generic analysis, and the
        dispatch-plan test only covers the agents its fixture happens to route.
        """
        source = ROOT / "engineering-lifecycle" / "scripts" / "workstreams.py"
        routed = {route[0] for route in literal_from_source(source, "AGENT_ROUTES")}
        routed.add(literal_from_source(source, "DEFAULT_AGENT"))
        self.assertTrue(routed)
        for agent in sorted(routed):
            with self.subTest(agent=agent):
                self.assertTrue((ROOT / "engineering-lifecycle" / "agents" / f"{agent}.md").is_file())

    def test_every_council_role_has_the_advisor_agent_it_spawns(self) -> None:
        # `run-engineering-council` spawns `council-<role>` for each role in
        # `council.py`, plus the chairperson. The deterministic fallback path is
        # the one the tests exercise, so a missing advisor file surfaces only in
        # a live subagent run - where five parallel spawns fail at once.
        roles = literal_from_source(ROOT / "engineering-lifecycle" / "scripts" / "council.py", "ROLES")
        expected = {f"council-{role}" for role, _ in roles} | {"council-chairperson"}
        for agent in sorted(expected):
            with self.subTest(agent=agent):
                self.assertTrue((ROOT / "engineering-lifecycle" / "agents" / f"{agent}.md").is_file())

    def test_no_skill_reaches_for_an_agent_from_another_plugin(self) -> None:
        """Plugins are installed one at a time, so a cross-plugin agent is absent.

        CONTRIBUTING's first rule is that each plugin stays self-contained. An
        agent lives in its own plugin's `agents/`, and a skill naming a sibling
        plugin's agent works only on a machine that happens to have both
        installed - the same class of defect the reference checker was written
        for, where `audit-resolver` routed to agents that are not in this
        marketplace at all.
        """
        owners = {path.stem: path.relative_to(ROOT).parts[0] for path in ROOT.glob("*/agents/*.md")}
        self.assertTrue(owners)
        for skill in sorted(ROOT.glob("*/skills/*/SKILL.md")):
            plugin_id = skill.relative_to(ROOT).parts[0]
            text = skill.read_text(encoding="utf-8")
            for agent, owner in sorted(owners.items()):
                if owner == plugin_id or not re.search(rf"`{re.escape(agent)}`", text):
                    continue
                self.fail(f"{skill.relative_to(ROOT).as_posix()} names `{agent}`, which ships with {owner}")

    def test_every_shipped_agent_is_reachable_from_a_skill_or_command(self) -> None:
        # An agent nothing dispatches is shipped, installed, and read by nobody.
        # `test_agents_have_full_role_contracts` checks that each agent file is
        # well formed; nothing checks that anything ever spawns it.
        for plugin_id in plugin_ids():
            agents_dir = ROOT / plugin_id / "agents"
            if not agents_dir.is_dir():
                continue
            plugin_root = ROOT / plugin_id
            surfaces = sorted(plugin_root.glob("skills/*/SKILL.md")) + sorted(plugin_root.glob("commands/*.md"))
            prose = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)
            for agent in sorted(agents_dir.glob("*.md")):
                with self.subTest(plugin=plugin_id, agent=agent.stem):
                    # Whole-token, because `\b` does not separate `engineer`
                    # from `backend-engineer` and the point is to prove the
                    # specific agent is named, not a longer one containing it.
                    named = re.search(rf"(?<![\w-]){re.escape(agent.stem)}(?![\w-])", prose)
                    self.assertTrue(named, f"{plugin_id}: no skill or command mentions {agent.stem}")


class VersionConsistencyTests(unittest.TestCase):
    """One version per plugin, and one version for the marketplace itself."""

    def test_every_surface_that_carries_a_plugin_version_carries_the_same_one(self) -> None:
        # These are exactly the four files `bump-version` writes. Running it is
        # the documented way to bump; a hand-edit to any one of them is the
        # failure this catches, and `validate_platform_surfaces` only compares
        # two of the four.
        for plugin_id, record in records().items():
            versions = {
                "record": record["version"],
                ".claude-plugin/plugin.json": load(ROOT / plugin_id / ".claude-plugin" / "plugin.json")["version"],
                ".codex-plugin/plugin.json": load(ROOT / plugin_id / ".codex-plugin" / "plugin.json")["version"],
                ".claude-plugin/marketplace.json": claude_entries()[plugin_id]["version"],
            }
            with self.subTest(plugin=plugin_id):
                self.assertEqual(set(versions.values()), {record["version"]}, versions)

    def test_the_marketplace_version_is_the_same_in_the_catalog_and_the_cli(self) -> None:
        # `check-cli-version.py` compares the CLI against
        # `.claude-plugin/marketplace.json`, and `bump-version` rewrites the
        # catalog's `updated_at` while leaving its `version` alone. So the
        # catalog is the one copy of the marketplace version that no tool has
        # ever compared against the two that are published.
        published = load(CLAUDE_MARKETPLACE)["version"]
        self.assertEqual(load(CATALOG)["version"], published)
        self.assertEqual(load(ROOT / "cli" / "package.json")["version"], published)


if __name__ == "__main__":
    unittest.main()
