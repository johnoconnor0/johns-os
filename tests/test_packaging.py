"""Supply-chain contract for the published `johns-os` npm artifact.

## Why this file exists

Version 0.3.0 shipped with `list` silently degraded and `install` throwing, and
both defects were invisible to CI because the smoke test ran `node cli/index.js`
from the **checkout**. A checkout has `../.claude-plugin/marketplace.json`; a
tarball cannot, because `files` in package.json is unable to reference a parent
directory. The published package therefore took a code path CI never executed.

Every test here is written against the artifact - the file list `npm pack`
produces after running `prepack`, and for `InstalledArtifactTests` the installed
and executed tarball - rather than against the working tree, because the
difference between those two is the entire bug class.

`tests/test_marketplace.py` already checks that the metadata *surfaces* agree
with one another (catalog, plugin manifests, the four marketplace files). This
file is deliberately one level lower: what bytes leave the machine, what must
never be among them, and whether the result runs.

## Why the npm-dependent tests are quarantined in two classes

`npm` is genuinely absent on a Python contributor's machine, so packing has to
degrade to a skip. It must not take the rest of the suite with it - the version
guard, the allowlist shape checks, the credential scan and the licence checks
need no Node at all, and those are the ones protecting a public repository. Only
`PackedArtifactTests` and `InstalledArtifactTests` need npm; everything else runs
unconditionally.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli"
MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
VERSION_GUARD = ROOT / "scripts" / "check-cli-version.py"
TRACKER_SETTINGS = ROOT / ".project" / ".engineering" / "settings.json"

# npm packs these from the package root regardless of `files`, so the
# reconstruction below has to account for them or it will disagree with the real
# tarball - and the credential scan would then be reading a fiction.
#
# This is a pattern rather than a list of names because npm's rule is a pattern:
# npm-packlist force-includes `package.json` plus `readme`, `copying`, `license`
# and `licence` with any extension, matched case-insensitively. A hand-kept tuple
# of the six spellings someone thought of first silently omits `COPYING`,
# `licence.txt` and `Readme.rst` - all of which npm ships and none of which the
# scan would have looked at. Verified empirically against npm 11 by packing a
# fixture holding every shape: NOTICE, CHANGELOG, AUTHORS and CONTRIBUTING are
# *not* force-included, which is exactly the sort of detail a guessed list gets
# wrong in the unsafe direction.
ALWAYS_PACKED = re.compile(r"(?i)^(?:package\.json|readme|copying|licen[cs]e)(?:\..*)?$")

# Directory and file shapes that must never reach a published tarball. `.project`
# is the lifecycle plugin's runtime workspace, `test/` is source-only, and the
# rest are the usual suspects that an allowlist regression would let through.
FORBIDDEN_SEGMENTS = (".git", "node_modules", "test", ".project", "__pycache__", ".venv")
FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"\.log$"),
    re.compile(r"\.tgz$"),
    re.compile(r"\.py[co]$"),
)

# Deliberately not "any long random-looking string": a scanner that fires on
# hashes and base64 blobs gets muted, and a muted scanner is worse than none.
# These are the prefixes and shapes of credentials that would plausibly appear
# in this repository's blast radius.
CREDENTIAL_PATTERNS = {
    "PEM private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "OpenSSH/PGP key block": re.compile(r"-----BEGIN (?:OPENSSH|PGP|RSA|EC|DSA) "),
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    "OpenAI API key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "AWS access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Linear API key": re.compile(r"\blin_(?:api|oauth)_[A-Za-z0-9]{20,}\b"),
    "inline credential assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|passwd|password|credential)s?\b\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']"
    ),
}

# Linear team and project identifiers are UUIDs, and a UUID in a public file
# names a private workspace. This exact pattern was committed once already,
# which is why `scope.team` and `scope.project` are pinned to null.
UUID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")

# `prepack` is a one-liner of inlined Node. Reading the copy calls out of it as
# (source, destination) pairs is what lets the tests below assert about both
# ends - a substring check for "marketplace.json" is satisfied by the
# destination alone, which is how a relocated source would go unnoticed.
COPY_CALL = re.compile(r"copyFileSync\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)")

# The shapes `cli/index.js` may use to reach a file beside itself. Anything else
# mentioning HERE is reported rather than ignored; see `here_resolved_paths`.
HERE_DEFINITION = re.compile(r"\bconst\s+HERE\b\s*=")
HERE_TOKEN = re.compile(r"\bHERE\b")
HERE_CALL = re.compile(r"\bpath\.(?:join|resolve)\(\s*HERE\s*((?:,[^()]*)?)\)")
STRING_LITERAL = re.compile(r"^\s*(['\"])([^'\"]*)\1\s*$")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cli_source() -> str:
    return (CLI / "index.js").read_text(encoding="utf-8")


def manifest_plugins() -> list[dict]:
    return [entry for entry in load(MANIFEST)["plugins"] if isinstance(entry, dict) and "name" in entry]


def manifest_plugin_names() -> set[str]:
    return {entry["name"] for entry in manifest_plugins()}


def fallback_table() -> str:
    """The hardcoded plugin array in `marketplacePlugins()`, or "" if it moved.

    Shared so that the tests comparing the fallback table with the manifest and
    the test proving an *installed* package never printed it are reading the same
    text out of the same source, rather than two copies that can drift apart.
    """
    marker = "if (declared.length) return declared;"
    source = cli_source()
    if marker not in source:
        return ""
    block, separator, _ = source.split(marker, 1)[1].partition("];")
    return block if separator else ""


def fallback_descriptions() -> list[str]:
    return re.findall(r"description:\s*'([^']+)'", fallback_table())


def prepack_copies() -> list[tuple[str, str]]:
    """(source, destination) pairs the `prepack` script copies.

    Both sides are relative to `cli/`, because npm runs lifecycle scripts with
    the package directory as cwd.
    """
    return COPY_CALL.findall(load(CLI / "package.json").get("scripts", {}).get("prepack", ""))


def here_resolved_paths() -> tuple[set[str], set[str], list[str]]:
    """Every path `cli/index.js` resolves against its own directory.

    Returns `(beside, escaping, unreadable)`:

    * `beside`  - package-relative paths that must therefore be in the tarball.
    * `escaping` - paths containing `..`, the deliberate checkout-only fallback
      that `files` can never ship.
    * `unreadable` - HERE usages this function could not decode. Those are
      *reported*, not skipped. The previous version of this scan matched only
      `path.join(HERE, '<one single-quoted segment>')`, so
      `path.join(HERE, 'lib', 'x.json')`, a double-quoted name and a template
      literal were all invisible - and invisible meant the caller's loop simply
      had one fewer entry and passed. That is the 0.3.0 defect reproduced inside
      the test written to catch it: a file read beside the binary that nothing
      checked was packed.

    A HERE mention this function cannot place inside a recognised call - a new
    resolution shape, or prose in a comment using the identifier - lands in
    `unreadable` so the test fails loudly and a human decides. Failing on prose
    is the safe direction; silently not looking is the direction that shipped.
    """
    source = cli_source()
    beside: set[str] = set()
    escaping: set[str] = set()
    unreadable: list[str] = []
    covered: list[tuple[int, int]] = []

    definition = HERE_DEFINITION.search(source)
    if definition is None:
        unreadable.append("cli/index.js no longer defines HERE at all")
    else:
        covered.append(definition.span())

    for call in HERE_CALL.finditer(source):
        covered.append(call.span())
        segments: list[str] | None = []
        for argument in call.group(1).split(","):
            if not argument.strip():
                continue
            literal = STRING_LITERAL.match(argument)
            if literal is None:
                unreadable.append(f"computed argument in {call.group(0).strip()}")
                segments = None
                break
            assert segments is not None
            segments.append(literal.group(2))
        if not segments:
            continue
        (escaping if ".." in segments else beside).add("/".join(segments))

    lines = source.splitlines()
    for token in HERE_TOKEN.finditer(source):
        if any(start <= token.start() and token.end() <= end for start, end in covered):
            continue
        number = source.count("\n", 0, token.start()) + 1
        unreadable.append(f"line {number}: {lines[number - 1].strip()}")

    return beside, escaping, unreadable


def shipped_sources() -> dict[str, Path]:
    """Tarball path -> the checkout file whose bytes ship at that path.

    `cli/marketplace.json` is generated by `prepack` and gitignored, so the
    checkout file backing it is `.claude-plugin/marketplace.json`. Resolving that
    indirection here is what lets the credential scan run with no npm present:
    the shipped byte set is fully determined by `files` plus npm's always-packed
    names, and `PackedArtifactTests` proves this reconstruction is exact.

    This is a reconstruction, not the artifact. `PackedArtifactTests` scans the
    real packed bytes as well, because a `prepack` that ever transformed rather
    than copied would make the two disagree in content while agreeing in name.
    """
    package = load(CLI / "package.json")
    mapping: dict[str, Path] = {"package.json": CLI / "package.json"}
    generated = {destination: source for source, destination in prepack_copies()}

    for entry in package.get("files", []):
        if entry in generated:
            mapping[entry] = (CLI / generated[entry]).resolve()
            continue
        candidate = CLI / entry
        if candidate.is_dir():
            for child in sorted(candidate.rglob("*")):
                if child.is_file():
                    mapping[child.relative_to(CLI).as_posix()] = child
        else:
            mapping[entry] = candidate

    for child in sorted(CLI.iterdir()):
        if child.is_file() and ALWAYS_PACKED.match(child.name) and child.name not in mapping:
            mapping[child.name] = child
    return mapping


def stage_package(stage: Path, decoys: dict[str, str] | None = None) -> Path:
    """Reproduce the publish-time tree under `stage`; return the package directory.

    Packing happens here rather than in `cli/` because `prepack` writes its
    output into the package directory as a side effect. Running it against the
    real checkout would mutate repository state from a test, and
    `npm pack --dry-run` is only dry about the tarball - it still executes the
    lifecycle script.

    Only what `prepack` reaches for is copied in, so a broadened copy cannot mask
    a dependency on some other part of the tree. Every destination the prepack
    script writes is then deleted from the staged package directory:
    `cli/marketplace.json` is generated and gitignored so a stale one is usually
    sitting in the checkout, and `cli/LICENSE` is committed. Either would stand
    in for a prepack that never ran, making the outcome assertions pass while
    proving nothing.
    """
    (stage / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, stage / ".claude-plugin" / "marketplace.json")
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")

    staged_cli = stage / "cli"
    shutil.copytree(
        CLI,
        staged_cli,
        ignore=shutil.ignore_patterns("node_modules", ".git", "__pycache__", "*.tgz"),
    )
    for _, destination in prepack_copies():
        (staged_cli / destination).unlink(missing_ok=True)

    for relative, body in (decoys or {}).items():
        planted = staged_cli / relative
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(body, encoding="utf-8")
    return staged_cli


class PackedArtifactTests(unittest.TestCase):
    """What `npm pack` actually emits, packed from a staged copy of the tree.

    The staged tree is salted with decoys: a `.git`, a `node_modules`, a stray
    file under `test/`, a `.project/`, `.env` files, a `.log` and a leftover
    `.tgz`. None of those exist in the real `cli/`, so asserting their absence
    against the checkout would prove nothing. Planting them means this test fails
    the moment the `files` allowlist is weakened or removed - which is the
    realistic regression, since npm's own default ignore rules cover `.git` and
    `node_modules` but not `.env`, `.project`, `test/` or `__pycache__`.

    The one directory that genuinely exists - `cli/test/` - gets its own
    assertion against its real contents rather than a planted stand-in, because
    a decoy sitting at the same path as a real file proves only that the decoy
    stayed out.
    """

    tmp: tempfile.TemporaryDirectory
    staged_cli: Path
    packed: list[str]
    pack_error: str | None = None

    # Contents are inert placeholders; the point is the filename, not the bytes.
    # Nothing here may collide with a path that exists in the real `cli/`, or the
    # decoy would shadow the file it is meant to be distinguishable from.
    DECOYS = {
        ".env": "PLACEHOLDER=1\n",
        ".env.local": "PLACEHOLDER=2\n",
        ".env.production": "PLACEHOLDER=3\n",
        "debug.log": "noise\n",
        "johns-os-0.0.0.tgz": "stale artifact\n",
        ".git/HEAD": "ref: refs/heads/main\n",
        "node_modules/left-pad/index.js": "module.exports = 1;\n",
        "test/planted-decoy.test.js": "// planted, not the real suite\n",
        ".project/.engineering/settings.json": "{}\n",
        "__pycache__/hook.cpython-312.pyc": "not really bytecode\n",
    }

    @classmethod
    def setUpClass(cls) -> None:
        npm = shutil.which("npm")
        if npm is None:
            raise unittest.SkipTest("`npm` is not on PATH; the artifact cannot be packed here")

        cls.pack_error = None
        cls.tmp = tempfile.TemporaryDirectory()
        cls.staged_cli = stage_package(Path(cls.tmp.name), cls.DECOYS)

        # The same invocation the publish workflow uses, so this measures the
        # artifact that would really be uploaded.
        result = subprocess.run(
            [npm, "pack", "--dry-run", "--json", "--workspaces=false"],
            cwd=cls.staged_cli,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            cls.pack_error = (
                f"`npm pack` exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
            cls.packed = []
            return

        start = result.stdout.find("[")
        if start < 0:
            cls.pack_error = f"`npm pack --json` produced no JSON array:\n{result.stdout}"
            cls.packed = []
            return
        payload = json.loads(result.stdout[start:])
        cls.packed = sorted(entry["path"] for entry in payload[0]["files"])

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def paths(self) -> list[str]:
        if self.pack_error:
            self.fail(self.pack_error)
        return self.packed

    def test_packing_runs_the_prepack_script_and_succeeds(self) -> None:
        # `prepack` is the fix for the original defect, so a silently skipped or
        # failing lifecycle script would restore it exactly.
        #
        # This used to assert that the string "prepack" appeared in npm's stderr.
        # That is npm's undocumented lifecycle logging, not a contract: it moves
        # between major versions and disappears under `--silent`, so the test
        # tracked npm's log format rather than the repository's invariant. The
        # outcome is what matters, and `stage_package` deletes every destination
        # the script writes beforehand - so their existence here can only mean
        # the script ran.
        self.assertIsNone(self.pack_error, self.pack_error)
        destinations = [destination for _, destination in prepack_copies()]
        self.assertTrue(destinations, "cli/package.json's prepack script copies nothing")
        for destination in destinations:
            with self.subTest(produced=destination):
                self.assertTrue(
                    (self.staged_cli / destination).is_file(),
                    f"prepack did not produce {destination}; nothing copied it into the package directory",
                )

    def test_the_files_the_cli_needs_at_runtime_are_all_present(self) -> None:
        # `index.js` is the bin, `marketplace.json` is what `list` reads before
        # falling back, `package.json` is what `--version` prints, and `README`
        # is the npm landing page. Losing any one of them degrades a published
        # command rather than breaking the install, which is why it went
        # unnoticed for a release.
        packed = self.paths()
        for required in ("index.js", "marketplace.json", "package.json", "README.md"):
            self.assertIn(required, packed, f"{required} is missing from the tarball:\n{packed}")

    def test_the_licence_notice_travels_in_the_tarball(self) -> None:
        # MIT requires the notice to travel with every copy, and an npm tarball
        # is a copy. `LicenseTests` checks the file exists beside the code and
        # matches the root notice; this is the only assertion that it is
        # actually in the artifact, which is the part a user receives.
        packed = self.paths()
        licences = [name for name in packed if name.lower().startswith(("license", "licence"))]
        self.assertTrue(licences, f"no licence notice is in the tarball:\n{packed}")
        for name in licences:
            with self.subTest(licence=name):
                self.assertEqual(
                    (self.staged_cli / name).read_bytes(),
                    (ROOT / "LICENSE").read_bytes(),
                    f"the packed {name} is not the repository's licence text",
                )

    def test_every_file_the_cli_opens_beside_itself_is_in_the_tarball(self) -> None:
        # This is the 0.3.0 defect stated at the level it actually occurred:
        # `index.js` resolved a path against its own directory, that path was
        # not in the tarball, and the read failed into a fallback instead of an
        # error. Checking the filename against the packed list - rather than
        # against the checkout, where every such file exists - is the only form
        # of this assertion that could have caught it.
        #
        # `here_resolved_paths` reports every HERE usage it cannot decode instead
        # of skipping it; see its docstring for why a scan that quietly matches
        # fewer sites is this bug wearing a test's clothes.
        packed = self.paths()
        beside, escaping, unreadable = here_resolved_paths()
        self.assertEqual(
            unreadable,
            [],
            "cli/index.js resolves something against its own directory in a shape this test cannot read, "
            "so it cannot tell whether that file ships. Teach `here_resolved_paths` the new shape.",
        )
        self.assertTrue(beside, "cli/index.js no longer resolves anything against its own directory")

        # Pinned by name because these two ARE the invariant, not an example of
        # it: `list` degrades when the manifest is not beside the binary, and
        # `--version` prints "unknown" when package.json is not.
        self.assertLessEqual(
            {"marketplace.json", "package.json"},
            beside,
            f"cli/index.js stopped reading the packaged manifest or its own package.json: {sorted(beside)}",
        )
        for name in sorted(beside):
            with self.subTest(reads=name):
                self.assertIn(name, packed, f"cli/index.js reads {name}, which the tarball does not contain")

        # The parent-relative read is the deliberate checkout-only path. Recorded
        # rather than asserted on, because `files` can never ship it - but if it
        # ever disappeared, the fallback chain in `marketplacePlugins` changed
        # shape and this test's exclusion should be revisited.
        for name in sorted(escaping):
            with self.subTest(checkout_only=name):
                self.assertNotIn(name, packed, f"{name} escapes the package directory yet appears in the tarball")

    def test_no_development_only_file_reaches_the_tarball(self) -> None:
        # Only the planted decoys are asserted on. The previous version also
        # looped over the packed list checking each path for a forbidden segment
        # or extension - but `files` is an exact allowlist of four filenames, so
        # that loop iterated over five known-good names and could not fail. It
        # read as a scan of the tarball while the decoys did all the work.
        # `FilesAllowlistTests` covers the allowlist shape without npm.
        packed = self.paths()
        for decoy in sorted(self.DECOYS):
            with self.subTest(decoy=decoy):
                self.assertNotIn(decoy, packed, f"{decoy} reached the tarball; the `files` allowlist has a hole")

    def test_the_real_source_only_test_suite_stays_out_of_the_tarball(self) -> None:
        # `cli/test/` now genuinely exists and is 50KB of Node test source. The
        # decoy above proves a planted `test/` file stays out; this proves the
        # real one does, which is the file set that would actually be published.
        packed = self.paths()
        staged = {p.relative_to(self.staged_cli).as_posix() for p in self.staged_cli.rglob("*") if p.is_file()}
        source_only = sorted(p.relative_to(CLI).as_posix() for p in (CLI / "test").rglob("*") if p.is_file())
        self.assertTrue(source_only, "cli/test/ is empty or missing, so this test would prove nothing")
        for name in source_only:
            with self.subTest(source_only=name):
                self.assertIn(name, staged, f"{name} was not staged, so its absence from the tarball proves nothing")
                self.assertNotIn(name, packed, f"{name} is source-only and must not be published")
        self.assertEqual(
            [path for path in packed if path.split("/")[0] == "test"],
            [],
            "the tarball carries a `test/` directory",
        )

    def test_the_reconstruction_the_other_suites_rely_on_is_exact(self) -> None:
        # `shipped_sources()` lets the credential and licence checks run with no
        # Node installed. That is only sound while it agrees with npm to the
        # filename - if npm's always-packed set or the `files` list changes shape
        # and this drifts, those suites would be scanning a fiction.
        self.assertEqual(self.paths(), sorted(shipped_sources()))

    def test_prepack_copies_the_real_manifest_rather_than_an_empty_placeholder(self) -> None:
        # The published `list` degraded because the manifest was absent, not
        # because it was wrong - so it is the *content* landing in the package
        # directory that matters, byte for byte.
        copied = self.staged_cli / "marketplace.json"
        self.assertTrue(copied.is_file(), "prepack did not produce cli/marketplace.json")
        self.assertEqual(
            copied.read_bytes(),
            MANIFEST.read_bytes(),
            "the packaged manifest is not a faithful copy of .claude-plugin/marketplace.json",
        )
        self.assertIsInstance(load(copied).get("plugins"), list, "the packaged manifest declares no plugin list")

    def test_no_credential_or_identifier_is_in_the_bytes_that_would_be_published(self) -> None:
        # `PackagedSecretTests` scans a *reconstruction* of the shipped set, and
        # it has to, because it must run with no npm. But the file most likely
        # to carry a copied identifier is `cli/marketplace.json`, which does not
        # exist in the checkout - it is generated by prepack and gitignored - so
        # the reconstruction substitutes the file prepack reads from. That is a
        # different file, and every assertion about "the package" that never
        # opens the generated one is an assertion about the generator's input.
        # Here the staged directory holds the real post-prepack bytes.
        packed = self.paths()
        self.assertIn("marketplace.json", packed, "the generated manifest is not packed; this scan would miss it")
        for name in packed:
            shipped = self.staged_cli / name
            self.assertTrue(shipped.is_file(), f"{name} is in the tarball but not on disk in the staged package")
            text = shipped.read_text(encoding="utf-8", errors="replace")
            for label, pattern in CREDENTIAL_PATTERNS.items():
                with self.subTest(file=name, credential=label):
                    self.assertIsNone(pattern.search(text), f"the packed {name} looks like it contains a {label}")
            with self.subTest(file=name, credential="workspace UUID"):
                self.assertEqual(
                    UUID_PATTERN.findall(text),
                    [],
                    f"the packed {name} contains a UUID; publication to npm is irreversible",
                )


class InstalledArtifactTests(unittest.TestCase):
    """The tarball, installed the way a user installs it, and executed.

    Everything else in this file reasons about a file *list* or about source
    text. None of it runs the thing. The 0.3.0 defect was not a missing name in
    a manifest - it was `list` printing a different table and `install` throwing
    when the process ran from somewhere with no `../.claude-plugin` above it.
    A file-list test can say the manifest is packed; only executing the
    installed copy can say the code reads the packed one.

    The install deliberately goes into a temp directory with no repository above
    it. A checkout above the package is exactly what hid the bug for a release,
    so an assertion made from inside the checkout is the assertion that already
    failed to catch this once.
    """

    tmp: tempfile.TemporaryDirectory
    node: str
    consumer: Path
    installed: Path
    env: dict[str, str]
    setup_error: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        npm = shutil.which("npm")
        node = shutil.which("node")
        if npm is None or node is None:
            raise unittest.SkipTest("`npm` and `node` are both required to install and run the tarball")
        cls.node = node

        cls.setup_error = None
        cls.tmp = tempfile.TemporaryDirectory()
        stage = Path(cls.tmp.name)
        staged_cli = stage_package(stage)

        destination = stage / "tarball"
        destination.mkdir()
        packed = subprocess.run(
            [npm, "pack", "--json", "--workspaces=false", f"--pack-destination={destination}"],
            cwd=staged_cli,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if packed.returncode != 0 or "[" not in packed.stdout:
            cls.setup_error = f"`npm pack` failed:\nstdout:\n{packed.stdout}\nstderr:\n{packed.stderr}"
            return
        tarball = destination / json.loads(packed.stdout[packed.stdout.find("[") :])[0]["filename"]

        consumer = stage / "consumer"
        consumer.mkdir()
        (consumer / "package.json").write_text(
            json.dumps({"name": "consumer", "version": "1.0.0", "private": True}) + "\n", encoding="utf-8"
        )
        # `--offline` and `--ignore-scripts` keep this from touching the network
        # or executing anything: the package has no dependencies, so a registry
        # round trip would only add a way for this test to fail for reasons that
        # are not about the artifact.
        install = subprocess.run(
            [
                npm,
                "install",
                str(tarball),
                "--no-save",
                "--no-audit",
                "--no-fund",
                "--ignore-scripts",
                "--offline",
                "--loglevel=error",
            ],
            cwd=consumer,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if install.returncode != 0:
            cls.setup_error = f"`npm install <tarball>` failed:\nstdout:\n{install.stdout}\nstderr:\n{install.stderr}"
            return

        cls.consumer = consumer
        cls.installed = consumer / "node_modules" / "johns-os"
        if not cls.installed.is_dir():
            cls.setup_error = f"the tarball installed nothing at {cls.installed}"
            return

        # An empty config directory, so `list` reports the marketplace rather
        # than whatever the developer running the suite happens to have
        # installed - and so the test never reads a real ~/.claude.
        empty_home = stage / "claude-home"
        empty_home.mkdir()
        cls.env = dict(os.environ, CLAUDE_CONFIG_DIR=str(empty_home))

    @classmethod
    def tearDownClass(cls) -> None:
        tmp = getattr(cls, "tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def johns_os(self, *argv: str) -> subprocess.CompletedProcess[str]:
        if self.setup_error:
            self.fail(self.setup_error)
        return subprocess.run(
            [self.node, str(self.installed / "index.js"), *argv],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=self.env,
        )

    def test_the_installed_copy_has_no_checkout_above_it(self) -> None:
        # The precondition that makes every other test in this class mean
        # something. `marketplacePlugins()` falls back to
        # `path.resolve(HERE, '..', '.claude-plugin', 'marketplace.json')`; if
        # that resolved here, the packaged manifest could be missing entirely
        # and `list` would still look correct - which is precisely how CI passed
        # on a broken 0.3.0.
        if self.setup_error:
            self.fail(self.setup_error)
        self.assertFalse(
            (self.installed.parent / ".claude-plugin").exists(),
            "a .claude-plugin directory sits above the installed package; this test cannot prove anything",
        )
        self.assertFalse((self.consumer / ".claude-plugin").exists())

    def test_version_prints_the_published_version(self) -> None:
        # `--version` reads package.json out of its own directory. In the 0.3.0
        # shape that read was one of two files resolved beside the binary, and
        # the other one was not packed.
        result = self.johns_os("--version")
        self.assertEqual(result.returncode, 0, f"`johns-os --version` exited {result.returncode}: {result.stderr}")
        self.assertEqual(result.stdout.strip(), load(CLI / "package.json")["version"])

    def test_list_runs_from_the_install_and_reads_the_packaged_manifest(self) -> None:
        # The published defect exactly: `list` ran, exited 0 and printed a
        # plausible table built from the hardcoded fallback - no version column,
        # different wording. Nothing short of running the installed copy and
        # reading its output can tell the two tables apart.
        result = self.johns_os("list")
        self.assertEqual(result.returncode, 0, f"`johns-os list` exited {result.returncode}: {result.stderr}")
        output = result.stdout

        for plugin in manifest_plugins():
            with self.subTest(plugin=plugin["name"]):
                self.assertIn(plugin["name"], output)
                # The version column exists only on the manifest path; the
                # fallback table carries no versions at all.
                self.assertIn(f"(marketplace {plugin['version']})", output)
                self.assertIn(plugin["description"], output)

    def test_list_output_is_not_the_hardcoded_fallback_table(self) -> None:
        # Stated as the negative as well, because "the manifest values are
        # present" would still hold if the fallback ran and happened to agree.
        # The fallback's wording is read out of index.js rather than pinned here,
        # so this cannot drift into checking a string nobody uses.
        result = self.johns_os("list")
        declared = {plugin.get("description") for plugin in manifest_plugins()}
        distinctive = [text for text in fallback_descriptions() if text not in declared]
        self.assertTrue(
            distinctive,
            "every fallback description is also a manifest description, so the two tables are "
            "indistinguishable in `list` output and this test cannot tell them apart",
        )
        for text in distinctive:
            with self.subTest(fallback_wording=text):
                self.assertNotIn(text, result.stdout, "`list` printed the fallback table from an installed package")

    def test_the_declared_bin_points_at_a_file_that_was_packed(self) -> None:
        # `bin` naming a path `files` does not ship produces an install that
        # succeeds and a command that cannot start - the same class of failure,
        # one level further out.
        if self.setup_error:
            self.fail(self.setup_error)
        for name, target in load(CLI / "package.json")["bin"].items():
            with self.subTest(bin=name):
                self.assertTrue(
                    (self.installed / target).is_file(),
                    f"package.json's bin `{name}` points at {target}, which the tarball did not ship",
                )


class FilesAllowlistTests(unittest.TestCase):
    """The `files` allowlist itself, checked without running npm.

    `PackedArtifactTests` proves the planted decoys stay out of the tarball, but
    it needs npm and it can only speak about shapes somebody thought to plant.
    The allowlist is the mechanism keeping all of them out, and its realistic
    regression is someone reaching for a directory or a glob - `"files": ["."]`,
    `["*"]`, `["test"]` - each of which sweeps in whatever happens to be beside
    the CLI at pack time.

    Naming exact files is also what makes the packed set knowable from
    package.json alone, which is the assumption `shipped_sources()` and the
    credential scan are built on.
    """

    def setUp(self) -> None:
        self.package = load(CLI / "package.json")
        self.files = self.package.get("files", [])
        self.generated = {destination for _, destination in prepack_copies()}

    def test_the_allowlist_is_a_list_of_plain_filenames(self) -> None:
        self.assertTrue(self.files, "cli/package.json has no `files` allowlist, so npm packs the whole directory")
        for entry in self.files:
            with self.subTest(entry=entry):
                self.assertIsInstance(entry, str)
                self.assertNotIn("..", entry, f"{entry} reaches outside the package directory")
                self.assertFalse(re.search(r"[*?\[\]]", entry), f"{entry} is a glob, not a filename")
                self.assertNotIn("/", entry.strip("/"), f"{entry} names a path rather than a file beside package.json")
                self.assertFalse((CLI / entry).is_dir(), f"{entry} is a directory; everything inside it would ship")

    def test_no_allowlist_entry_names_a_development_only_shape(self) -> None:
        for entry in self.files:
            for segment in FORBIDDEN_SEGMENTS:
                with self.subTest(entry=entry, forbidden=segment):
                    self.assertNotIn(segment, entry.split("/"), f"{entry} would publish a development-only directory")
            for pattern in FORBIDDEN_PATTERNS:
                with self.subTest(entry=entry, pattern=pattern.pattern):
                    self.assertIsNone(pattern.search(entry), f"{entry} matches a never-publish pattern")

    def test_every_allowlist_entry_is_a_file_that_exists_or_prepack_creates(self) -> None:
        # npm silently skips a `files` entry that does not resolve, so a typo
        # here is a file quietly dropped from the tarball rather than an error -
        # which is how `marketplace.json` could go missing without a red build.
        for entry in self.files:
            with self.subTest(entry=entry):
                if entry in self.generated:
                    continue
                self.assertTrue((CLI / entry).is_file(), f"`files` names {entry}, which does not exist in cli/")


class PrepackContractTests(unittest.TestCase):
    """The `prepack` script's copy pairs, checked without running npm.

    `tests/test_marketplace.py` asserts the prepack string mentions
    `marketplace.json`. That passes even if the manifest it copies *from* has
    moved, because the substring is satisfied by the destination alone. The path
    that actually breaks is the source: relocate `.claude-plugin/` and the
    lifecycle script throws ENOENT at publish time, or - worse, on a machine
    where a stale copy is lying around - succeeds against yesterday's manifest.
    """

    def setUp(self) -> None:
        self.package = load(CLI / "package.json")
        self.copies = prepack_copies()

    def test_prepack_exists_and_every_copy_it_makes_is_readable_as_a_pair(self) -> None:
        prepack = self.package.get("scripts", {}).get("prepack", "")
        self.assertTrue(prepack, "cli/package.json has no prepack script")
        self.assertTrue(self.copies, f"no copyFileSync(source, destination) pair could be read out of: {prepack}")

    def test_every_source_prepack_reads_is_a_file_inside_the_repository(self) -> None:
        # Resolved the way npm resolves it: lifecycle scripts run with cwd set to
        # the package directory.
        for source, destination in self.copies:
            with self.subTest(source=source, destination=destination):
                resolved = (CLI / source).resolve()
                self.assertTrue(resolved.is_relative_to(ROOT.resolve()), f"prepack reads {resolved}, outside the repo")
                self.assertTrue(resolved.is_file(), f"prepack copies from {resolved}, which does not exist")

    def test_the_manifest_prepack_copies_from_is_the_marketplace_manifest(self) -> None:
        sources = [source for source, destination in self.copies if destination == "marketplace.json"]
        self.assertEqual(len(sources), 1, f"expected exactly one source for marketplace.json: {self.copies}")
        source = (CLI / sources[0]).resolve()
        self.assertEqual(source, MANIFEST.resolve())
        self.assertIsInstance(load(source).get("plugins"), list)

    def test_prepack_writes_only_names_the_files_allowlist_ships(self) -> None:
        # A destination the allowlist does not name is copied and then dropped,
        # which reproduces the original bug with an extra step in between.
        allowlist = self.package.get("files", [])
        destinations = [destination for _, destination in self.copies]
        self.assertIn("marketplace.json", destinations, "prepack no longer produces the packaged manifest")
        for destination in destinations:
            with self.subTest(destination=destination):
                self.assertNotIn("/", destination, f"prepack writes {destination} outside the package root")
                self.assertIn(destination, allowlist, f"prepack writes {destination}, which `files` does not ship")


class InstallTargetTests(unittest.TestCase):
    """What `johns-os install` with no arguments would actually try to install.

    `install` expands an empty argument list to `marketplacePlugins()`, which
    reads the packaged manifest - so the manifest *is* the install list, and a
    bad entry becomes a failed `claude plugin install` in the middle of the
    primary documented command.

    The previous version of this test was titled "the manifest declares every
    plugin the CLI can install" and then asserted the opposite direction: that
    each name the manifest declares has a plugin.json in the checkout. That is
    one necessary condition of three, and not the first one the CLI applies -
    `parseArgs` rejects a name failing `PLUGIN_NAME` before any lookup happens,
    so a manifest entry named `Engineering-Lifecycle` would be refused by the
    installer's own validator with "Invalid plugin name" while every file it
    names exists. The direction the old title described - a plugin the CLI knows
    and the manifest omits - is
    `FallbackTableTests.test_the_fallback_lists_exactly_the_marketplace_plugins`.
    """

    def setUp(self) -> None:
        self.plugins = manifest_plugins()
        self.assertTrue(self.plugins, ".claude-plugin/marketplace.json declares no plugins")

    def _cli_name_pattern(self) -> re.Pattern[str]:
        # Taken from index.js rather than restated, so this checks the validator
        # that actually runs rather than a copy of it that can drift.
        found = re.search(r"const PLUGIN_NAME\s*=\s*/(.+?)/;", cli_source())
        self.assertIsNotNone(found, "cli/index.js no longer defines PLUGIN_NAME as a literal regex")
        assert found is not None
        return re.compile(found.group(1))

    def test_every_declared_name_passes_the_cli_s_own_name_validator(self) -> None:
        pattern = self._cli_name_pattern()
        for plugin in self.plugins:
            with self.subTest(plugin=plugin["name"]):
                self.assertRegex(
                    plugin["name"],
                    pattern,
                    f"`johns-os install {plugin['name']}` would be refused by the CLI's own argument validator",
                )

    def test_every_declared_plugin_resolves_to_a_plugin_that_names_itself_the_same(self) -> None:
        for plugin in self.plugins:
            name = plugin["name"]
            with self.subTest(plugin=name):
                manifest = ROOT / name / ".claude-plugin" / "plugin.json"
                self.assertTrue(manifest.is_file(), f"{name} is offered for install but has no {manifest}")
                self.assertEqual(
                    load(manifest).get("name"),
                    name,
                    f"{manifest} calls itself something else, so `claude plugin install {name}@johns-os` "
                    "would install under a different name than the one advertised",
                )

    def test_every_declared_source_points_at_the_directory_it_names(self) -> None:
        # The `source` is what Claude Code fetches. A relative path that does not
        # match the entry name installs a different plugin under this one's name.
        for plugin in self.plugins:
            name = plugin["name"]
            with self.subTest(plugin=name):
                source = plugin.get("source")
                self.assertEqual(source, f"./{name}", f"{name} is sourced from {source!r}")
                self.assertTrue((ROOT / name).is_dir())


class FallbackTableTests(unittest.TestCase):
    """The hardcoded plugin table in `cli/index.js` against the real manifest.

    This table is only reachable when both manifest lookups miss, which is
    precisely the condition nobody exercises - and for one release it was the
    *only* live path, printing stale descriptions and no version column. A
    fourth plugin added to the marketplace would be invisible to it, silently,
    with no error anywhere. That divergence was filed as a bug.

    The comparison is against `.claude-plugin/marketplace.json` rather than a
    constant kept in the test file, because a hardcoded expectation in the test
    is the same failure mode one level up.
    """

    def setUp(self) -> None:
        self.source = cli_source()

    def _fallback_block(self) -> str:
        marker = "if (declared.length) return declared;"
        self.assertIn(marker, self.source, "cli/index.js no longer guards its fallback table the expected way")
        block = fallback_table()
        self.assertTrue(block, "could not find the end of the fallback array in cli/index.js")
        return block

    def test_the_fallback_lists_exactly_the_marketplace_plugins(self) -> None:
        names = re.findall(r"name:\s*'([a-z0-9-]+)'", self._fallback_block())
        self.assertEqual(len(names), len(set(names)), f"the fallback table repeats a plugin: {names}")
        self.assertEqual(
            set(names),
            manifest_plugin_names(),
            "cli/index.js's fallback table and .claude-plugin/marketplace.json disagree; "
            "add or remove the entry in the fallback array in marketplacePlugins()",
        )

    def test_every_fallback_entry_carries_a_description(self) -> None:
        # `list` prints the description line only when one is present, so an
        # entry without it degrades quietly rather than failing.
        entries = re.findall(r"\{[^{}]*name:\s*'[a-z0-9-]+'[^{}]*\}", self._fallback_block())
        self.assertEqual(len(entries), len(manifest_plugin_names()))
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertRegex(entry, r"description:\s*'[^']+'")


class VersionGuardTests(unittest.TestCase):
    """The installer's version against the marketplace it advertises.

    `scripts/check-cli-version.py` enforces this before the publish workflow
    packs anything, and that script is the only thing standing between a typo
    and an npm release that advertises a marketplace version which does not
    exist - unpublishable and irreversible once it is out.

    Asserting the invariant here rather than shelling out to the guard is
    deliberate: if the guard is ever rewritten to compare a different pair of
    files, delegating to it would keep passing while checking nothing. So this
    states the invariant independently, and separately pins which two files the
    guard is expected to be reading.
    """

    def setUp(self) -> None:
        self.cli_package = load(CLI / "package.json")
        self.manifest = load(MANIFEST)
        self.guard = VERSION_GUARD.read_text(encoding="utf-8")

    def test_the_cli_version_matches_the_marketplace_version(self) -> None:
        self.assertEqual(
            self.cli_package.get("version"),
            self.manifest.get("version"),
            "cli/package.json and .claude-plugin/marketplace.json disagree on the release version",
        )

    def test_the_published_version_is_a_semver_npm_will_accept(self) -> None:
        # npm rejects `v0.3.0` and `0.3` outright, and the failure surfaces at
        # `npm publish` - after the tag, after the release notes.
        version = self.cli_package.get("version", "")
        self.assertRegex(version, r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

    def test_the_guard_still_compares_the_two_files_this_suite_assumes(self) -> None:
        self.assertIn('"cli" / "package.json"', self.guard)
        self.assertIn('".claude-plugin" / "marketplace.json"', self.guard)
        self.assertIn('cli.get("version") != marketplace.get("version")', self.guard)

    def test_the_guard_runs_before_anything_is_published(self) -> None:
        # A guard nobody invokes is indistinguishable from no guard. It has to
        # sit on the publish path and in the local validation entry point.
        workflow = (ROOT / ".github" / "workflows" / "publish-cli.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/check-cli-version.py", workflow)
        self.assertIn("check-cli-version.py", (ROOT / "scripts" / "validate-repo.py").read_text(encoding="utf-8"))


class PackagedSecretTests(unittest.TestCase):
    """Nothing credential-shaped leaves in the tarball, and nothing identifying
    is committed to a public repository.

    A published npm tarball is permanent: unpublish windows are narrow and
    mirrors keep copies regardless. The repository is public, and a Linear
    workspace UUID was already caught being committed once - which is why
    `.project/.engineering/settings.json` pins `scope.team` and `scope.project`
    to null and expects them to arrive from the environment per machine. A
    regression there is not a broken build; it is a disclosure.

    These scans run against `shipped_sources()`, a *reconstruction* of the
    published byte set, because they must work on a machine with no npm. The
    settings file is not in that set - `.project` never ships - so the two
    concerns are asserted separately rather than one standing in for the other,
    and `PackedArtifactTests` re-runs the same patterns over the real
    post-prepack bytes.
    """

    def test_no_credential_shaped_string_ships_in_the_package(self) -> None:
        for shipped, source in sorted(shipped_sources().items()):
            self.assertTrue(source.is_file(), f"{shipped} maps to {source}, which does not exist")
            text = source.read_text(encoding="utf-8", errors="replace")
            for label, pattern in CREDENTIAL_PATTERNS.items():
                with self.subTest(file=shipped, credential=label):
                    self.assertIsNone(pattern.search(text), f"{shipped} (from {source}) looks like a {label}")

    def test_no_workspace_uuid_ships_in_the_package(self) -> None:
        for shipped, source in sorted(shipped_sources().items()):
            with self.subTest(file=shipped):
                self.assertTrue(source.is_file(), f"{shipped} maps to {source}, which does not exist")
                text = source.read_text(encoding="utf-8", errors="replace")
                # The message names both paths on purpose: for `marketplace.json`
                # the bytes come from `.claude-plugin/`, and a failure that names
                # only the tarball entry sends the reader to a file that does not
                # exist in the checkout.
                self.assertEqual(
                    UUID_PATTERN.findall(text),
                    [],
                    f"{shipped} (from {source}) contains a UUID; npm publication is irreversible",
                )

    def test_the_committed_tracker_settings_pin_no_workspace_identifiers(self) -> None:
        settings = load(TRACKER_SETTINGS)
        scope = settings["issue_filing"]["scope"]
        self.assertIsNone(scope["project"], "scope.project must stay null; it names a private Linear project")
        self.assertIsNone(scope["team"], "scope.team must stay null; it names a private Linear team")
        # mcp_server is nulled for a different reason - the server segment is
        # machine-specific - but a value there is just as identifying.
        self.assertIsNone(settings["issue_filing"]["mcp_server"])

    def test_the_only_committed_runtime_settings_file_carries_no_identifiers(self) -> None:
        # The null pins above cover the two known fields. This catches an id
        # arriving under some field nobody thought to pin.
        text = TRACKER_SETTINGS.read_text(encoding="utf-8")
        self.assertEqual(UUID_PATTERN.findall(text), [], f"{TRACKER_SETTINGS} contains a workspace identifier")
        for label, pattern in CREDENTIAL_PATTERNS.items():
            with self.subTest(credential=label):
                self.assertIsNone(pattern.search(text), f"{TRACKER_SETTINGS} looks like it contains a {label}")

    def test_the_ignore_rules_that_keep_credentials_out_are_still_in_place(self) -> None:
        # The scan above only sees files that exist. These rules are what stops
        # a real `.env` or key file from ever becoming one of them.
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for rule in (".env", ".env.*", "*.pem", "*.key", "cli/marketplace.json"):
            with self.subTest(rule=rule):
                self.assertIn(rule, ignored, f".gitignore no longer ignores {rule}")


class LicenseTests(unittest.TestCase):
    """The licence the package declares against the licence it distributes.

    MIT requires its notice to travel with every copy, and an npm tarball is a
    copy. `files` need not name it - npm packs `LICENSE` from the package
    directory automatically - which is exactly why its absence is easy to miss:
    nothing in package.json would look wrong.
    """

    def setUp(self) -> None:
        self.package = load(CLI / "package.json")

    def test_the_repository_ships_the_licence_it_names(self) -> None:
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn("Permission is hereby granted", text)
        self.assertEqual(self.package.get("license"), "MIT")

    def test_the_licence_text_ships_beside_the_code_it_licenses(self) -> None:
        # Discovered from the directory rather than checked against a list of
        # spellings, because npm's force-include rule is a pattern: `LICENCE.txt`
        # and `COPYING` ship too, and a name-list version of this test would call
        # a perfectly good notice missing.
        present = [
            child.name
            for child in sorted(CLI.iterdir())
            if child.is_file() and ALWAYS_PACKED.match(child.name) and child.name.lower().startswith(("licen", "copy"))
        ]
        self.assertTrue(
            present,
            "cli/package.json declares a license but no LICENSE file sits beside it, "
            "so the published tarball distributes the code without its notice",
        )
        for name in present:
            with self.subTest(licence=name):
                self.assertIn(name, shipped_sources(), f"{name} is not in the set this suite believes is published")

    def test_the_packaged_licence_is_the_repository_licence(self) -> None:
        # A second copy of a legal notice is a second thing that can drift, and
        # this repository's whole contract suite exists because hand-kept copies
        # do. `prepack` refreshes it from the root before every pack, so the two
        # can only disagree in a checkout - which is what this catches.
        self.assertEqual(
            (CLI / "LICENSE").read_bytes(),
            (ROOT / "LICENSE").read_bytes(),
            "cli/LICENSE has drifted from the repository LICENSE; prepack copies the root file",
        )

    def test_prepack_refreshes_the_licence_from_the_repository_root(self) -> None:
        # The committed copy is what `npm pack` picks up automatically, and what
        # the test above compares. Naming it in `prepack` as well is what stops
        # a stale copy being published after the root notice changes.
        licences = [(source, destination) for source, destination in prepack_copies() if "LICENSE" in destination]
        self.assertEqual(
            licences,
            [("../LICENSE", "LICENSE")],
            "prepack does not refresh cli/LICENSE from the repository root",
        )
        self.assertIn("LICENSE", self.package.get("files", []))


if __name__ == "__main__":
    unittest.main()
