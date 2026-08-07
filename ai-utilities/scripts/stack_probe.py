#!/usr/bin/env python3
"""What stack this repository is, resolved through a ladder rather than an import.

The audit gates its check families on the detected stack: no frontend means no
frontend checks, no database means no data-layer section. `engineering-lifecycle`
already has a good detector, but this plugin cannot import it - the two install into
separate directories and either can be installed without the other.

So three rungs, best first, and the answer always records which one produced it:

  workspace  Read `.project/.engineering/context/stack.json`. Free, and written by
             the other plugin's SessionStart hook against the same repository. If it
             is there it is authoritative and nothing needs to be re-derived.
  imported   Find `stack_detection.py` next door and use the real detector.
  vendored   Fall back to the small probe below, which covers only the markers the
             audit actually gates on.

`detector` and `evidence` travel with the result for the same reason `dialects.py`
returns its reason: a wrong answer should be traceable to its cause rather than
silently deciding which half of the audit runs.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from audit_common import plugin_root, read_json

STACK_JSON = Path(".project") / ".engineering" / "context" / "stack.json"

# Marker file -> what its presence proves. Only what the families below gate on.
_FRAMEWORKS = (
    ("next.config.js", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("nuxt.config.ts", "Nuxt"),
    ("svelte.config.js", "Svelte"),
    ("astro.config.mjs", "Astro"),
    ("vite.config.ts", "Vite"),
    ("angular.json", "Angular"),
)
_BACKEND = (
    ("pyproject.toml", "Python"),
    ("requirements.txt", "Python"),
    ("go.mod", "Go"),
    ("Cargo.toml", "Rust"),
    ("composer.json", "PHP"),
    ("Gemfile", "Ruby"),
    ("pom.xml", "Java"),
    ("build.gradle", "Java"),
)
_DATABASE = (
    ("supabase/config.toml", "Supabase"),
    ("prisma/schema.prisma", "Prisma"),
    ("drizzle.config.ts", "Drizzle"),
    ("alembic.ini", "PostgreSQL"),
)
_PACKAGE_MANAGERS = (
    ("pnpm-lock.yaml", "pnpm"),
    ("bun.lockb", "bun"),
    ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"),
    ("package.json", "npm"),
    ("pyproject.toml", "python"),
    ("requirements.txt", "python"),
    ("composer.json", "composer"),
    ("Cargo.toml", "cargo"),
    ("go.mod", "go"),
)
# The JS managers, mapped to how each runs a binary out of node_modules.
_JS_MANAGERS = {"npm": "npx", "pnpm": "pnpm exec", "yarn": "yarn", "bun": "bunx"}


def _from_workspace(root: Path) -> dict[str, Any] | None:
    data = read_json(root / STACK_JSON)
    if not isinstance(data, dict) or not data:
        return None
    data = dict(data)
    data["detector"] = "workspace"
    data.setdefault("evidence", {})
    return data


def _sibling_detector(root: Path) -> Path | None:
    """`stack_detection.py` from a co-installed engineering-lifecycle, if present.

    The plugin cache only. This used to also accept
    ``root/"engineering-lifecycle"/"scripts"`` - a path *inside the repository
    being audited* - and `_from_import` executes what it finds there in-process,
    with that directory inserted at the front of `sys.path` so every subsequent
    import resolves from it too. Since this plugin exists to be pointed at
    repositories nobody controls, a repo shipping that directory pair got code
    execution simply by being audited.

    `root` is unused now. The parameter stays because `resolve_stack` dispatches
    every rung with the same signature.
    """
    directory = plugin_root().parent / "engineering-lifecycle" / "scripts"
    if (directory / "stack_detection.py").is_file() and (directory / "eng_common.py").is_file():
        return directory
    return None


def _from_import(root: Path) -> dict[str, Any] | None:
    directory = _sibling_detector(root)
    if directory is None:
        return None
    added = str(directory) not in sys.path
    if added:
        sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location("_el_stack_detection", directory / "stack_detection.py")
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = dict(module.detect_stack(root))
    # SystemExit is not an Exception, so a module calling sys.exit() during import
    # used to take the whole audit down instead of falling through.
    except (Exception, SystemExit):
        # A detector that raises is a detector that did not answer. Fall through to
        # the vendored probe rather than letting the whole audit fail on it.
        return None
    finally:
        if added and str(directory) in sys.path:
            sys.path.remove(str(directory))
    data["detector"] = "imported"
    return data


def _package_scripts(root: Path) -> dict[str, str]:
    data = read_json(root / "package.json", {})
    scripts = data.get("scripts") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in scripts.items()} if isinstance(scripts, dict) else {}


def _vendored(root: Path) -> dict[str, Any]:
    evidence: dict[str, dict[str, str]] = {"frameworks": {}, "backend": {}, "database": {}, "testing": {}}
    for markers, key in ((_FRAMEWORKS, "frameworks"), (_BACKEND, "backend"), (_DATABASE, "database")):
        for filename, label in markers:
            if (root / filename).exists() and label not in evidence[key]:
                evidence[key][label] = filename

    package_manager = next((name for filename, name in _PACKAGE_MANAGERS if (root / filename).exists()), None)
    scripts = _package_scripts(root)
    commands: dict[str, str] = {}
    # The detected manager, not npm. This used to resolve `package_manager` above
    # and then ignore it, so a pnpm, yarn or bun repo got `npm test` - which
    # either fails outright or installs a divergent dependency tree.
    # `engineering-lifecycle/scripts/stack_detection.py` already did it this way.
    if package_manager in _JS_MANAGERS:
        for script, key in (("test", "unit"), ("build", "build"), ("lint", "lint")):
            if script in scripts:
                # `<mgr> run <script>` rather than `<mgr> <script>`, which is
                # equivalent everywhere except bun, where `bun test` is bun's own
                # test runner and not the package.json script at all.
                commands[key] = f"{package_manager} run {script}"
        if (root / "tsconfig.json").exists():
            commands["typecheck"] = f"{_JS_MANAGERS[package_manager]} tsc --noEmit"
    if package_manager == "python":
        if (root / "tests").is_dir():
            commands["unit"] = "python -m unittest discover -s tests"
        if (root / "pyproject.toml").exists():
            commands["lint"] = "python -m ruff check ."
    if package_manager == "cargo":
        commands["unit"] = "cargo test"
        commands["lint"] = "cargo check"
    if package_manager == "go":
        commands["unit"] = "go test ./..."
        commands["lint"] = "go vet ./..."

    return {
        "detector": "vendored",
        "frameworks": sorted(evidence["frameworks"]),
        "backend": sorted(evidence["backend"]),
        "database": sorted(evidence["database"]),
        "testing": [],
        "package_manager": package_manager,
        "test_commands": commands,
        "evidence": evidence,
    }


def resolve_stack(root: Path, prefer: str = "") -> dict[str, Any]:
    """The stack, and which rung of the ladder answered.

    `prefer` forces a rung, for tests and for the case where the workspace copy is
    known to be stale.
    """
    rungs = {"workspace": _from_workspace, "imported": _from_import, "vendored": _vendored}
    order = [prefer] if prefer in rungs else ["workspace", "imported", "vendored"]
    for name in order:
        result = rungs[name](root)
        if result:
            return _normalise(result)
    return _normalise(_vendored(root))


def _normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Every rung answers the same shape, so callers never branch on the detector."""
    for key in ("frameworks", "backend", "database", "testing"):
        value = data.get(key)
        data[key] = [str(item) for item in value] if isinstance(value, list) else []
    commands = data.get("test_commands")
    data["test_commands"] = {str(k): str(v) for k, v in commands.items()} if isinstance(commands, dict) else {}
    data.setdefault("package_manager", None)
    data.setdefault("evidence", {})
    data.setdefault("detector", "vendored")
    return data


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--prefer", default="", choices=["", "workspace", "imported", "vendored"])
    args = parser.parse_args()
    from audit_common import repo_root

    print(json.dumps(resolve_stack(repo_root(Path(args.root)), args.prefer), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
