#!/usr/bin/env python3
"""Detect a project's stack from its manifests, markers and workspace members.

Split out of quality_tools.py, which had grown past 2,400 lines. This concern is
self-contained: it reads the filesystem and returns a description, with no
dependency on prompts, hooks or the ledger.

Every detection records the file or dependency that proved it, so a wrong answer
can be traced to its cause rather than argued about.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eng_common import (
    SCAN_PRUNE_DIRS,
    engineering_root,
    now_iso,
    read_json_safe,
    workspace_exists,
    write_json,
)

# --- stack detection -------------------------------------------------------
#
# Detection is declarative so adding a framework is a table entry, not a branch.
# Three signal sources, in increasing cost:
#   1. marker files, stat'd at a known set of directories
#   2. dependency names in resolved package.json / pyproject / composer manifests
#   3. a bounded breadth-first search for marker directories the first two miss
#
# All three stay bounded because this runs on SessionStart. Listing the tree is
# what made an earlier version hang outside a git repo, and a test asserts that
# detect_stack never calls git_files.

# Directories a monorepo conventionally puts workspace members in, used only
# when nothing declares its workspaces explicitly.
_WORKSPACE_FALLBACK_GLOBS = ("apps/*", "packages/*", "services/*", "workers/*", "libs/*")
_MAX_WORKSPACE_MANIFESTS = 60

_FRAMEWORK_FILES: tuple[tuple[str, str], ...] = (
    ("next.config.js", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("next.config.cjs", "Next.js"),
    ("nuxt.config.ts", "Nuxt"),
    ("nuxt.config.js", "Nuxt"),
    ("vite.config.ts", "Vite"),
    ("vite.config.js", "Vite"),
    ("astro.config.mjs", "Astro"),
    ("astro.config.ts", "Astro"),
    ("svelte.config.js", "SvelteKit"),
    ("remix.config.js", "Remix"),
    ("angular.json", "Angular"),
    ("app.json", "Expo"),
    ("tailwind.config.js", "Tailwind CSS"),
    ("tailwind.config.ts", "Tailwind CSS"),
)

_FRAMEWORK_DEPS: dict[str, str] = {
    "next": "Next.js",
    "nuxt": "Nuxt",
    "@remix-run/react": "Remix",
    "astro": "Astro",
    "@sveltejs/kit": "SvelteKit",
    "@angular/core": "Angular",
    "vite": "Vite",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "solid-js": "Solid",
    "@builder.io/qwik": "Qwik",
    "expo": "Expo",
    "react-native": "React Native",
    "tailwindcss": "Tailwind CSS",
}

_BACKEND_DEPS: dict[str, str] = {
    "express": "Express",
    "fastify": "Fastify",
    "hono": "Hono",
    "@nestjs/core": "NestJS",
    "koa": "Koa",
    "@trpc/server": "tRPC",
    "graphql": "GraphQL",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "laravel/framework": "Laravel",
    "symfony/framework-bundle": "Symfony",
}

_DATABASE_DEPS: dict[str, str] = {
    "@prisma/client": "Prisma",
    "prisma": "Prisma",
    "drizzle-orm": "Drizzle",
    "@supabase/supabase-js": "Supabase",
    "supabase": "Supabase",
    "mongoose": "MongoDB",
    "mongodb": "MongoDB",
    "typeorm": "TypeORM",
    "knex": "Knex",
    "kysely": "Kysely",
    "pg": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "mysql2": "MySQL",
    "mysql": "MySQL",
    "mysqlclient": "MySQL",
    "pymysql": "MySQL",
    "mariadb": "MySQL",
    "better-sqlite3": "SQLite",
    "sqlite3": "SQLite",
    "@libsql/client": "SQLite",
    "mssql": "SQL Server",
    "tedious": "SQL Server",
    "pyodbc": "SQL Server",
    "pymssql": "SQL Server",
    "pymongo": "MongoDB",
    "motor": "MongoDB",
    "redis": "Redis",
    "ioredis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "django": "Django ORM",
}

_TESTING_DEPS: dict[str, str] = {
    "@playwright/test": "Playwright",
    "playwright": "Playwright",
    "@playwright/cli": "Playwright",
    "vitest": "Vitest",
    "jest": "Jest",
    "cypress": "Cypress",
    "@testing-library/react": "Testing Library",
    "pytest": "pytest",
    "phpunit/phpunit": "PHPUnit",
}

_TESTING_FILES: tuple[tuple[str, str], ...] = (
    ("playwright.config.ts", "Playwright"),
    ("playwright.config.js", "Playwright"),
    ("vitest.config.ts", "Vitest"),
    ("jest.config.js", "Jest"),
    ("jest.config.ts", "Jest"),
    ("cypress.config.ts", "Cypress"),
)

# Marker paths, relative to a candidate directory, that identify a technology
# without needing a dependency manifest. Found by a bounded BFS so a monorepo
# that keeps them below the root (supabase/, apps/api/prisma/) still matches.
_DATABASE_MARKERS: tuple[tuple[str, str], ...] = (
    ("prisma/schema.prisma", "Prisma"),
    ("supabase/config.toml", "Supabase"),
    ("supabase/migrations", "Supabase"),
    ("drizzle.config.ts", "Drizzle"),
    ("drizzle.config.js", "Drizzle"),
    ("alembic.ini", "Alembic"),
    ("knexfile.js", "Knex"),
    ("wrangler.toml", "Cloudflare D1"),
    ("wrangler.jsonc", "Cloudflare D1"),
    ("wrangler.json", "Cloudflare D1"),
)

# Language/runtime markers. Checked at the root and at each workspace member.
_BACKEND_MARKERS: tuple[tuple[str, str], ...] = (
    ("requirements.txt", "Python"),
    ("pyproject.toml", "Python"),
    ("Pipfile", "Python"),
    ("go.mod", "Go"),
    ("Cargo.toml", "Rust"),
    ("composer.json", "PHP"),
    ("Gemfile", "Ruby"),
    ("pom.xml", "Java"),
    ("build.gradle", "Java"),
    ("build.gradle.kts", "Kotlin"),
    ("deno.json", "Deno"),
    ("deno.jsonc", "Deno"),
    ("bun.lockb", "Bun"),
    ("wrangler.toml", "Cloudflare Workers"),
    ("wrangler.jsonc", "Cloudflare Workers"),
    ("wrangler.json", "Cloudflare Workers"),
)


def _yaml_string_list(text: str, key: str) -> list[str]:
    """Read one ``key:`` block of scalar list items out of simple YAML.

    These scripts are deliberately stdlib-only, and the only YAML this needs is
    pnpm-workspace.yaml's ``packages:`` block, which is a flat list of quoted
    globs. Pulling in a YAML parser for that would be a dependency for one field.
    """
    values: list[str] = []
    collecting = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")) and line.rstrip(":").strip() == key and line.endswith(":"):
            collecting = True
            continue
        if collecting:
            stripped = line.strip()
            if stripped.startswith("- "):
                values.append(stripped[2:].strip().strip("\"'"))
                continue
            if not line.startswith((" ", "\t")):  # next top-level key ends the block
                break
    return values


def workspace_globs(root: Path) -> list[str]:
    """Workspace member globs this repo declares, however it declares them."""
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.exists():
        try:
            globs = _yaml_string_list(pnpm.read_text(encoding="utf-8"), "packages")
        except OSError:
            globs = []
        if globs:
            return globs

    declared = read_json_safe(root / "package.json").get("workspaces")
    if isinstance(declared, dict):
        declared = declared.get("packages")
    if isinstance(declared, list):
        return [item for item in declared if isinstance(item, str)]
    return []


def workspace_manifests(root: Path, max_manifests: int = _MAX_WORKSPACE_MANIFESTS) -> list[Path]:
    """Resolve each workspace member's package.json, bounded and pruned.

    A monorepo keeps its real dependencies in members, not at the root: the root
    manifest of a turbo/pnpm repo typically lists only turbo, eslint and
    typescript. Reading only the root is why framework, backend and database
    detection came back empty for every monorepo.
    """
    patterns = workspace_globs(root) or list(_WORKSPACE_FALLBACK_GLOBS)
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        if len(found) >= max_manifests:
            break
        try:
            matches = sorted(root.glob(pattern))
        except (OSError, ValueError):  # malformed glob
            continue
        for member in matches:
            if len(found) >= max_manifests:
                break
            if not member.is_dir() or set(member.parts) & SCAN_PRUNE_DIRS:
                continue
            manifest = member / "package.json"
            if manifest.is_file() and manifest not in seen:
                seen.add(manifest)
                found.append(manifest)
    return found


def find_markers(
    root: Path,
    markers: tuple[tuple[str, str], ...],
    max_depth: int = 3,
    max_dirs: int = 2_000,
) -> dict[str, str]:
    """Map each matched marker to the relative path that proved it.

    Breadth-first and bounded rather than a full listing: the layouts this needs
    to catch (``apps/api/prisma/schema.prisma``, ``workers/api/wrangler.toml``)
    sit a couple of levels down, so a capped walk finds them without the cost of
    enumerating the tree, which on a mis-resolved root never terminated.
    """
    evidence: dict[str, str] = {}
    frontier = [root]
    visited = 0
    for _ in range(max_depth + 1):
        if not frontier:
            break
        nxt: list[Path] = []
        for directory in frontier:
            for relative, name in markers:
                if name in evidence:
                    continue
                candidate = directory / relative
                if candidate.exists():
                    evidence[name] = candidate.relative_to(root).as_posix()
            visited += 1
            if visited >= max_dirs:
                return evidence
            try:
                nxt.extend(
                    child for child in directory.iterdir() if child.is_dir() and child.name not in SCAN_PRUNE_DIRS
                )
            except OSError:  # unreadable directory: keep scanning the rest
                continue
        frontier = nxt
    return evidence


def has_prisma_schema(root: Path, max_depth: int = 3, max_dirs: int = 2_000) -> bool:
    """Kept for callers that only need the boolean."""
    return "Prisma" in find_markers(root, (("prisma/schema.prisma", "Prisma"),), max_depth, max_dirs)


def _manifest_dependencies(manifest: Path) -> dict[str, str]:
    """Every declared dependency name in a package.json, any section."""
    data = read_json_safe(manifest)
    deps: dict[str, str] = {}
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = data.get(section)
        if isinstance(block, dict):
            deps.update({str(key): section for key in block})
    return deps


def _python_dependencies(root: Path) -> set[str]:
    names: set[str] = set()
    for filename in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in re.findall(r"^\s*['\"]?([A-Za-z0-9_.\-]+)", text, re.MULTILINE):
            names.add(match.lower())
    return names


def _resolve_test_commands(root: Path, package_manager: str | None) -> dict[str, str]:
    """Only emit commands that actually exist.

    The previous version templated `<pm> test` / `lint` / `typecheck` off the
    package manager alone, so it advertised scripts that were never defined, and
    told this repo to run pytest when it runs unittest and does not depend on
    pytest.
    """
    commands: dict[str, str] = {}
    if package_manager in {"pnpm", "yarn", "npm", "bun"}:
        scripts = read_json_safe(root / "package.json").get("scripts")
        scripts = scripts if isinstance(scripts, dict) else {}
        runner = "npm run" if package_manager == "npm" else str(package_manager)
        for label, script in (("unit", "test"), ("lint", "lint"), ("typecheck", "typecheck"), ("build", "build")):
            if script in scripts:
                commands[label] = f"{runner} {script}"
        return commands

    if package_manager == "python":
        deps = _python_dependencies(root)
        if "pytest" in deps or "[tool.pytest" in _safe_read(root / "pyproject.toml"):
            commands["unit"] = "python -m pytest"
        elif (root / "tests").is_dir():
            commands["unit"] = "python -m unittest discover -s tests"
        if "ruff" in deps:
            commands["lint"] = "python -m ruff check ."
        if "mypy" in deps:
            commands["typecheck"] = "python -m mypy ."
    return commands


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def detect_stack(root: Path) -> dict[str, Any]:
    """Identify the project's stack across the repo root and its workspaces.

    Reads three bounded signal sources (marker files, resolved dependency
    manifests, a capped marker search) rather than listing the tree. Every
    detected item records the path that proved it in ``evidence`` so a wrong
    answer can be traced to its cause instead of argued about.
    """
    package_manager = None
    if (root / "pnpm-lock.yaml").exists() or (root / "pnpm-workspace.yaml").exists():
        package_manager = "pnpm"
    elif (root / "bun.lockb").exists():
        package_manager = "bun"
    elif (root / "yarn.lock").exists():
        package_manager = "yarn"
    elif (root / "package-lock.json").exists() or (root / "package.json").exists():
        package_manager = "npm"
    elif (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        package_manager = "python"
    elif (root / "composer.json").exists():
        package_manager = "composer"

    frameworks: dict[str, str] = {}
    backend: dict[str, str] = {}
    database: dict[str, str] = {}
    testing: dict[str, str] = {}

    # Every directory that can hold a manifest: the root plus each workspace
    # member. Root-only inspection is what produced the empty arrays.
    manifests = [root / "package.json", *workspace_manifests(root)]
    member_dirs = [root, *(manifest.parent for manifest in manifests[1:])]

    for directory in member_dirs:
        for filename, name in _FRAMEWORK_FILES:
            if name not in frameworks and (directory / filename).is_file():
                frameworks[name] = (directory / filename).relative_to(root).as_posix()
        for filename, name in _BACKEND_MARKERS:
            if name not in backend and (directory / filename).exists():
                backend[name] = (directory / filename).relative_to(root).as_posix()
        for filename, name in _TESTING_FILES:
            if name not in testing and (directory / filename).is_file():
                testing[name] = (directory / filename).relative_to(root).as_posix()

    node_seen = False
    for manifest in manifests:
        if not manifest.is_file():
            continue
        node_seen = True
        where = manifest.relative_to(root).as_posix()
        for dependency in _manifest_dependencies(manifest):
            if dependency in _FRAMEWORK_DEPS:
                frameworks.setdefault(_FRAMEWORK_DEPS[dependency], f"{where}:{dependency}")
            if dependency in _BACKEND_DEPS:
                backend.setdefault(_BACKEND_DEPS[dependency], f"{where}:{dependency}")
            if dependency in _DATABASE_DEPS:
                database.setdefault(_DATABASE_DEPS[dependency], f"{where}:{dependency}")
            if dependency in _TESTING_DEPS:
                testing.setdefault(_TESTING_DEPS[dependency], f"{where}:{dependency}")
    if node_seen:
        backend.setdefault("Node.js", "package.json")
        if (root / "tsconfig.json").is_file() or (root / "tsconfig.base.json").is_file():
            backend.setdefault("TypeScript", "tsconfig.json")

    for dependency in _python_dependencies(root):
        if dependency in _BACKEND_DEPS:
            backend.setdefault(_BACKEND_DEPS[dependency], f"python:{dependency}")
        if dependency in _DATABASE_DEPS:
            database.setdefault(_DATABASE_DEPS[dependency], f"python:{dependency}")
        if dependency in _TESTING_DEPS:
            testing.setdefault(_TESTING_DEPS[dependency], f"python:{dependency}")

    composer = read_json_safe(root / "composer.json")
    for section in ("require", "require-dev"):
        block = composer.get(section)
        if isinstance(block, dict):
            for dependency in block:
                if dependency in _BACKEND_DEPS:
                    backend.setdefault(_BACKEND_DEPS[dependency], f"composer.json:{dependency}")
    if (root / "wp-config.php").is_file() or (root / "wp-content").is_dir():
        frameworks.setdefault("WordPress", "wp-content")

    # Marker directories the manifests cannot reveal (a Supabase project has no
    # npm dependency; a D1 binding lives in wrangler.toml).
    database.update({name: where for name, where in find_markers(root, _DATABASE_MARKERS).items()})

    result = {
        "package_manager": package_manager,
        "frameworks": sorted(frameworks),
        "backend": sorted(backend),
        "database": sorted(database),
        "testing": sorted(testing),
        "test_commands": _resolve_test_commands(root, package_manager),
        "evidence": {
            "frameworks": dict(sorted(frameworks.items())),
            "backend": dict(sorted(backend.items())),
            "database": dict(sorted(database.items())),
            "testing": dict(sorted(testing.items())),
        },
        "workspace_manifests": [manifest.relative_to(root).as_posix() for manifest in manifests[1:]],
        "detected_at": now_iso(),
    }
    # Detection is always safe to run and report; persisting it is a workspace
    # write, so gate it on an initialized workspace. Running on SessionStart must
    # never create .project — it only refreshes stack.json once opted in.
    if workspace_exists(root):
        write_json(engineering_root(root) / "context" / "stack.json", result)
    return result
