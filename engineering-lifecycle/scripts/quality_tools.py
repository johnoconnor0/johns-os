#!/usr/bin/env python3
"""Shared deterministic quality-control tools for Engineering Lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eng_common import (
    ENV_VAR_RE,
    append_jsonl,
    changed_files,
    classify_file_path,
    emit_json,
    engineering_root,
    git_files,
    hook_additional_context,
    hook_output,
    load_hook_payload,
    nearest_env_example,
    now_iso,
    parse_env_example_keys,
    parse_front_matter,
    permission_output,
    placeholder_for_env,
    read_json,
    read_json_safe,
    relpath,
    repo_root,
    slugify,
    workspace_exists,
    write_json,
    write_text,
)

# Three concerns were extracted from this file once it passed 2,400 lines. They
# are re-exported here so every existing caller - 44 dispatcher shims, the hook
# wrappers, council.py and the test suite - keeps working unchanged.
from initiatives import (  # noqa: F401  (re-exported for backwards compatibility)
    active_initiative_resolver,
    initiative_command,
    initiative_dirs,
    initiative_drift_detector,
    load_initiative_registry,
    registry_path,
    save_initiative_registry,
)
from questions import (  # noqa: F401  (re-exported for backwards compatibility)
    QUESTION_KINDS,
    QUESTION_STATUSES,
    answer_question,
    capture_asked_questions,
    extract_open_questions,
    load_open_questions,
    question_id,
    questions_path,
    record_questions,
    render_questions_digest,
    scan_artifact_questions,
    sync_open_questions,
)
from stack_detection import (  # noqa: F401  (re-exported for backwards compatibility)
    detect_stack,
    find_markers,
    has_prisma_schema,
    workspace_globs,
    workspace_manifests,
)

INTENT_KEYWORDS = {
    "profile": [
        "profile",
        "understand this repo",
        "product system",
        "repo profile",
        "current stack",
        "engineering maturity",
    ],
    "lifecycle": ["lifecycle", "what should happen next", "missing artifacts", "current stage", "next skill"],
    "system-map": ["system map", "map the system", "external systems", "data flow", "failure points", "component map"],
    "api-contract": [
        "api contract",
        "request shape",
        "response shape",
        "webhook",
        "event contract",
        "pagination",
        "rate limit",
    ],
    "design-system": [
        "design system",
        "ui kit",
        "component system",
        "design tokens",
        "tokens",
        "colours",
        "colors",
        "typography",
        "spacing",
        "component standards",
        "accessibility rules",
    ],
    "ui-prototype": [
        "ui prototype",
        "clickable prototype",
        "prototype",
        "mvp shell",
        "app shell",
        "mock data",
        "demo-ready",
        "frontend proof-of-concept",
    ],
    "review": ["review", "audit", "find bugs", "security scan"],
    "testing": ["test", "failing", "coverage", "qa", "regression"],
    "implementation-plan": [
        "implementation plan",
        "break this",
        "approved design",
        "sequence",
        "sequenced",
        "slices",
        "dependencies",
        "rollback",
    ],
    "implementation": [
        "implement",
        "safe implementation",
        "verified slices",
        "fix",
        "build",
        "add",
        "change",
        "refactor",
    ],
    "architecture": ["architecture", "system map", "boundary", "adr", "design"],
    "data-model": ["schema", "database", "entity", "migration", "model"],
    "ux-design": ["ux", "screen", "flow", "wireframe", "user journey"],
    "requirements": ["prd", "requirements", "acceptance criteria"],
    "release": ["release", "deploy", "rollback", "launch"],
    "repo-hygiene": ["hygiene", "gitignore", "env.example", "cleanup"],
    "council-decision": ["council", "tradeoff", "build vs buy", "high-stakes"],
    "discovery": [
        "discover",
        "discovery",
        "clarify",
        "product idea",
        "assumptions",
        "open questions",
        "mvp boundary",
        "explore",
        "research",
        "brief",
    ],
}

SKILL_BY_INTENT = {
    "profile": "profile-product-system",
    "lifecycle": "map-product-lifecycle",
    "system-map": "create-system-map",
    "api-contract": "create-api-contract",
    "design-system": "create-design-system",
    "ui-prototype": "build-ui-prototype",
    "review": "review-change",
    "testing": "create-test-strategy",
    "implementation-plan": "create-engineering-plan",
    "implementation": "implement-feature-safely",
    "architecture": "create-technical-design-document",
    "data-model": "create-data-model",
    "ux-design": "create-ux-flow",
    "requirements": "create-prd",
    "release": "create-release-plan",
    "repo-hygiene": "update-repo-hygiene",
    "council-decision": "run-engineering-council",
    "discovery": "create-discovery-brief",
}

AMBIGUOUS_PHRASES = {
    "fix this": "target",
    "make it better": "objective",
    "clean up the repo": "scope",
    "improve architecture": "scope",
    "add tests": "coverage",
    "make production ready": "acceptance",
    "review everything": "scope",
    "do the whole thing": "scope",
}

DANGEROUS_COMMANDS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+\.",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-fdx",
    r"docker\s+system\s+prune",
    r"drop\s+database",
    r"truncate\s+table",
    r"curl\b.*\|\s*(sh|bash)",
    r"chmod\s+-R\s+777",
    r"Remove-Item\b.*-Recurse\b.*-Force\b.*C:\\",
]

PRODUCTION_PATTERNS = [
    r"DATABASE_URL=.*prod",
    r"vercel\s+--prod",
    r"railway\s+up",
    r"supabase\s+db\s+push\s+--linked",
    r"kubectl\s+apply",
    r"terraform\s+apply",
]

SECRET_PATTERNS = [
    r"\.env(\.|$|\s)",
    r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY",
    r"sk-[A-Za-z0-9_-]{12,}",
    r"gh[pousr]_[A-Za-z0-9_]{20,}",
    r"xox[baprs]-[A-Za-z0-9-]{20,}",
    r"postgres(?:ql)?://[^@\s]+:[^@\s]+@",
    r"service-account\.json",
]


def prompt_from_payload(payload: dict[str, Any]) -> str:
    for key in ("prompt", "message", "user_prompt", "input"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(payload, sort_keys=True) if payload else ""


def command_from_payload(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("toolInput") or {}
    if isinstance(tool_input, dict):
        for key in ("command", "cmd", "script"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
    for key in ("command", "cmd"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def file_from_payload(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("toolInput") or {}
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "filename"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
    return ""


def text_from_payload(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("toolInput") or {}
    if isinstance(tool_input, dict):
        values = [
            str(tool_input.get(key, ""))
            for key in ("content", "new_string", "old_string", "text")
            if tool_input.get(key)
        ]
        return "\n".join(values)
    return ""


def classify_user_intent(prompt: str) -> dict[str, Any]:
    text = prompt.lower()
    scores: dict[str, int] = {}
    for intent, words in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for word in words if word in text)
    intent, score = max(scores.items(), key=lambda item: item[1]) if scores else ("unknown", 0)
    if score == 0:
        intent = "unknown"
    return {
        "intent": intent,
        "confidence": "high" if score >= 2 else "medium" if score == 1 else "low",
        "recommended_skill": SKILL_BY_INTENT.get(intent),
        "requires_clarification": intent == "unknown",
    }


def prompt_quality_score(prompt: str) -> dict[str, Any]:
    checks = {
        "clear objective": bool(
            re.search(r"\b(add|build|fix|review|plan|create|implement|validate|check)\b", prompt, re.I)
        ),
        "target repo/module/file": bool(
            re.search(r"([A-Za-z]:\\|/|\.md|\.py|\.ts|repo|module|file|folder|directory)", prompt, re.I)
        ),
        "expected output": bool(
            re.search(r"\b(plan|patch|summary|report|script|tests?|implementation)\b", prompt, re.I)
        ),
        "constraints": bool(re.search(r"\b(do not|must|only|preserve|avoid|without|constraint)\b", prompt, re.I)),
        "success criteria": bool(
            re.search(r"\b(done|complete|success|acceptance|criteria|passes|working)\b", prompt, re.I)
        ),
        "whether edits are allowed": bool(
            re.search(r"\b(implement|edit|change|write|patch|plan only|review only)\b", prompt, re.I)
        ),
        "whether tests should be run": bool(re.search(r"\b(test|validate|check|verify|run)\b", prompt, re.I)),
        "whether external systems are involved": bool(
            re.search(r"\b(api|deploy|prod|github|slack|stripe|supabase|vercel|external)\b", prompt, re.I)
        ),
    }
    present = sum(1 for value in checks.values() if value)
    score = round(present / len(checks) * 100)
    return {
        "score": score,
        "missing": [name for name, ok in checks.items() if not ok],
        "risk": "high" if score < 50 else "medium" if score < 75 else "low",
    }


def ambiguity_patterns(prompt: str) -> dict[str, Any]:
    text = prompt.lower()
    matches = [
        {"phrase": phrase, "ambiguity_type": kind, "severity": "high"}
        for phrase, kind in AMBIGUOUS_PHRASES.items()
        if phrase in text
    ]
    question = None
    if matches:
        kind = matches[0]["ambiguity_type"]
        question = (
            "Should I scope this to the whole repo or a specific feature/module?"
            if kind == "scope"
            else "What exact outcome should be considered complete?"
        )
    return {"ambiguous": bool(matches), "matches": matches, "suggested_question": question}


def clarification_gate(prompt: str) -> dict[str, Any]:
    intent = classify_user_intent(prompt)
    quality = prompt_quality_score(prompt)
    ambiguity = ambiguity_patterns(prompt)
    questions: list[dict[str, Any]] = []
    if intent["intent"] == "unknown":
        questions.append(
            {
                "question": "What lifecycle mode should this use?",
                "options": ["Plan only", "Implement with edits", "Review existing code only"],
            }
        )
    if quality["score"] < 60:
        questions.append(
            {
                "question": "What outcome should count as complete?",
                "options": ["Working code and validation", "A decision-ready plan", "A review report"],
            }
        )
    if ambiguity["suggested_question"]:
        questions.append(
            {
                "question": ambiguity["suggested_question"],
                "options": ["Specific target", "Whole repo", "Decide from inspected context"],
            }
        )
    return {
        "requires_clarification": bool(questions),
        "reason": "Prompt is ambiguous or missing high-impact execution details."
        if questions
        else "Prompt has enough detail to start.",
        "questions": questions,
    }


def skill_router(prompt: str) -> dict[str, Any]:
    intent = classify_user_intent(prompt)
    secondary: list[str] = []
    if intent["intent"] in {"implementation", "architecture"}:
        secondary = ["create-test-strategy", "update-repo-hygiene"]
    return {
        "recommended_skill": intent.get("recommended_skill"),
        "reason": f"Detected intent {intent['intent']} with {intent['confidence']} confidence.",
        "secondary_skills": secondary,
    }


def repo_context_pack(root: Path) -> dict[str, Any]:
    files = git_files(root)
    stack = detect_stack(root)
    profile = {
        "generated_at": now_iso(),
        "repo_root": str(root),
        "stack": stack,
        "manifests": [
            relpath(root / p, root)
            for p in files
            if p.name in {"package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Dockerfile"}
        ],
        "docs": [relpath(root / p, root) for p in files if p.suffix.lower() in {".md", ".mdx"}][:50],
        "tests": [relpath(root / p, root) for p in files if classify_file_path(p) == "test"][:50],
        "ci": [relpath(root / p, root) for p in files if ".github/workflows" in str(p).replace("\\", "/")],
    }
    base = engineering_root(root) / "context"
    write_json(base / "repo-context.json", profile)
    md = [
        "# Repo Context",
        "",
        f"Generated: {profile['generated_at']}",
        "",
        "## Stack",
        json.dumps(stack, indent=2),
        "",
        "## Manifests",
    ]
    md.extend(f"- `{item}`" for item in profile["manifests"])
    write_text(base / "repo-context.md", "\n".join(md) + "\n")
    return profile


_MEMORY_MAX_DECISIONS = 20
_MEMORY_MAX_INITIATIVES = 12
_MEMORY_SUMMARY_CHARS = 280


def _markdown_section(body: str, headings: tuple[str, ...]) -> str:
    """First paragraph under the first matching heading, else the first prose."""
    lines = body.splitlines()
    wanted = {name.lower() for name in headings}
    collecting = False
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if collecting:
                break
            collecting = stripped.lstrip("#").strip().lower() in wanted
            continue
        if collecting:
            if stripped:
                buffer.append(stripped)
            elif buffer:
                break
    if not buffer:
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "---", "|", "<!--")):
                buffer = [stripped]
                break
    return " ".join(buffer)[:_MEMORY_SUMMARY_CHARS]


def _yaml_scalars(text: str, limit: int = 40) -> dict[str, str]:
    """Top-level ``key: value`` scalar pairs from a simple YAML profile.

    Deliberately stdlib-only (see _yaml_string_list). Nested blocks and lists are
    skipped rather than half-parsed, so what comes back is only what is certain.
    """
    values: dict[str, str] = {}
    for raw in text.splitlines():
        if len(values) >= limit:
            break
        if not raw or raw.startswith((" ", "\t", "#", "-")):
            continue
        key, sep, value = raw.partition(":")
        value = value.strip().strip("\"'")
        if sep and value and not key.strip().startswith("#"):
            values[key.strip()] = value[:_MEMORY_SUMMARY_CHARS]
    return values


def load_project_memory(root: Path) -> dict[str, Any]:
    """What this project has already decided, as content rather than filenames.

    The previous version returned an `rglob` listing of three directories: paths
    only, no file ever opened, and `initiatives/` — where every PRD, plan and
    review actually lives — omitted entirely. A list of filenames is not memory;
    injecting it into a session tells the model nothing it could act on.

    Everything here is bounded so this stays safe to run on SessionStart.
    """
    base = engineering_root(root)
    memory: dict[str, Any] = {
        "meta": {"loaded_at": now_iso(), "workspace": relpath(base, root), "exists": base.exists()},
        "profile": {},
        "decisions": [],
        "initiatives": [],
        "ledger": {},
    }
    if not base.exists():
        return memory

    for path in sorted((base / "profile").glob("*.yaml")):
        try:
            memory["profile"][path.stem] = _yaml_scalars(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    stack = base / "context" / "stack.json"
    if stack.is_file():
        detected = read_json_safe(stack)
        memory["profile"]["stack"] = {
            key: detected.get(key) for key in ("package_manager", "frameworks", "backend", "database", "testing")
        }

    decisions = sorted((base / "decisions").glob("*.md"))
    for path in decisions[:_MEMORY_MAX_DECISIONS]:
        try:
            front, body = parse_front_matter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        memory["decisions"].append(
            {
                "path": relpath(path, root),
                "title": next((line.lstrip("# ").strip() for line in body.splitlines() if line.startswith("# ")), ""),
                "status": front.get("status", "unknown"),
                "summary": _markdown_section(body, ("decision", "summary", "context")),
            }
        )

    initiatives_dir = base / "initiatives"
    if initiatives_dir.is_dir():
        entries = sorted(path for path in initiatives_dir.iterdir() if path.is_dir())
        for path in entries[:_MEMORY_MAX_INITIATIVES]:
            stages = {}
            for stage in sorted(child for child in path.iterdir() if child.is_dir()):
                artifacts = [item for item in sorted(stage.glob("*.md")) if item.is_file()]
                if artifacts:
                    stages[stage.name] = [relpath(item, root) for item in artifacts]
            memory["initiatives"].append({"id": path.name, "stages": stages, "stage_count": len(stages)})

    ledger = read_json_safe(base / "ledger" / "ledger.json")
    if ledger:
        memory["ledger"] = ledger.get("summary", {})

    memory["meta"]["truncated"] = len(decisions) > _MEMORY_MAX_DECISIONS
    return memory


def classify_changed(root: Path, explicit: list[str] | None = None) -> dict[str, Any]:
    paths = [Path(item) for item in explicit] if explicit else changed_files(root)
    items = [{"path": str(path).replace("\\", "/"), "category": classify_file_path(path)} for path in paths]
    result = {"files": items, "counts": {}}
    for item in items:
        result["counts"][item["category"]] = result["counts"].get(item["category"], 0) + 1
    write_json(engineering_root(root) / "reports" / "validation" / "changed-files.json", result)
    return result


def env_example_sync(root: Path, apply: bool = False) -> dict[str, Any]:
    found: dict[str, set[str]] = {}
    for path in git_files(root):
        full = root / path
        if classify_file_path(path) not in {"source", "config"} or not full.exists():
            continue
        text = full.read_text(encoding="utf-8", errors="ignore")
        for name in ENV_VAR_RE.findall(text):
            if name in {"PATH", "HOME", "USER", "SHELL"}:
                continue
            found.setdefault(name, set()).add(relpath(full, root))

    # A variable is documented if it appears in the nearest .env.example above ANY
    # file that references it (per-package resolution). This fixes the monorepo case
    # where code in apps/cloud/src is documented in apps/cloud/.env.example, and it
    # avoids a repo-wide union that would let one package's docs mask another's.
    key_cache: dict[str, set[str]] = {}

    def documented(name: str, rels: set[str]) -> bool:
        for rel in rels:
            example = nearest_env_example(root / rel, root)
            if example is None:
                continue
            cache_key = str(example)
            if cache_key not in key_cache:
                key_cache[cache_key] = parse_env_example_keys(example)
            if name in key_cache[cache_key]:
                return True
        return False

    missing = [
        {"name": name, "placeholder": f"{name}={placeholder_for_env(name)}", "seen_in": sorted(paths)}
        for name, paths in sorted(found.items())
        if not documented(name, paths)
    ]
    if apply and missing:
        env_path = nearest_env_example(root, root) or (root / ".env.example")
        with env_path.open("a", encoding="utf-8", newline="\n") as f:
            if env_path.exists() and env_path.stat().st_size:
                f.write("\n")
            f.write("# Added by Engineering Lifecycle\n")
            for item in missing:
                f.write(item["placeholder"] + "\n")
    result = {"missing": missing, "applied": apply}
    write_json(engineering_root(root) / "reports" / "validation" / "env-example-sync.json", result)
    return result


def gitignore_sync(root: Path, apply: bool = False) -> dict[str, Any]:
    safe = [".env.local", "*.log", ".cache/", ".turbo/", ".vercel/", "coverage/", "dist/", "build/"]
    unsafe = ["package-lock.json", "pnpm-lock.yaml", "migrations/", "schema/", "src/", "tests/"]
    path = root / ".gitignore"
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    missing_safe = [item for item in safe if item not in text]
    if apply and missing_safe:
        with path.open("a", encoding="utf-8", newline="\n") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write("\n# Engineering Lifecycle suggested ignores\n")
            for item in missing_safe:
                f.write(item + "\n")
    result = {"safe_additions": missing_safe, "unsafe_requires_approval": unsafe, "applied": apply}
    write_json(engineering_root(root) / "reports" / "validation" / "gitignore-sync.json", result)
    return result


def schema_validator(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    for path in (
        sorted((root / "schemas").glob("*.json"))
        + sorted((engineering_root(root)).rglob("*.json"))
        + sorted((root / "evals").rglob("*.json"))
    ):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{relpath(path, root)}: {exc}")
    result = {"valid": not errors, "errors": errors}
    write_json(engineering_root(root) / "reports" / "validation" / "schema-validator.json", result)
    return result


def markdown_artifact_validator(root: Path, files: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    targets = [root / f for f in files] if files else [p for p in engineering_root(root).rglob("*.md")]
    for path in targets:
        if not path.exists():
            errors.append(f"{relpath(path, root)}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm, body = parse_front_matter(text)
        if not fm:
            errors.append(f"{relpath(path, root)}: missing front matter")
        if re.search(r"TODO|TBD|<replace-me>|\\[.*?\\]", body, re.I):
            errors.append(f"{relpath(path, root)}: unresolved placeholder")
        if "```mermaid" in body and "```" not in body.split("```mermaid", 1)[1]:
            errors.append(f"{relpath(path, root)}: unclosed Mermaid block")
    result = {"valid": not errors, "errors": errors}
    write_json(engineering_root(root) / "reports" / "validation" / "markdown-artifact-validator.json", result)
    return result


def test_command_resolver(root: Path, files: list[str] | None = None) -> dict[str, Any]:
    stack = detect_stack(root)
    changed = classify_changed(root, files)
    commands: list[str] = []
    if stack["package_manager"] in {"pnpm", "yarn", "npm"}:
        pm = stack["package_manager"]
        commands.extend([f"{pm} typecheck", f"{pm} lint"])
        if any(item["category"] in {"source", "test"} for item in changed["files"]):
            commands.append(f"{pm} test")
    elif stack["package_manager"] == "python":
        commands.extend(["python -m pytest", "python -m compileall ."])
    else:
        commands.append("python scripts/validate-plugin.py")
    return {
        "recommended_commands": commands,
        "reason": "Commands selected from detected stack and changed-file categories.",
    }


def test_result_parser(text: str, command: str = "") -> dict[str, Any]:
    failed = bool(re.search(r"\b(fail|failed|error|traceback|exception)\b", text, re.I))
    failures = []
    for line in text.splitlines():
        if re.search(r"\b(fail|failed|error|traceback|exception)\b", line, re.I):
            failures.append({"line": line[:300]})
    return {"command": command, "status": "failed" if failed else "passed", "failures": failures[:20]}


def plan_quality_gate(text: str) -> dict[str, Any]:
    required = [
        "objective",
        "assumptions",
        "affected files",
        "risks",
        "rollback",
        "tests",
        "acceptance",
        "security",
        "migration",
        "docs",
    ]
    lower = text.lower()
    missing = [item for item in required if item not in lower]
    return {
        "complete": not missing,
        "missing": missing,
        "score": round((len(required) - len(missing)) / len(required) * 100),
    }


def completion_contract_check(root: Path, text: str = "") -> dict[str, Any]:
    lower = text.lower()
    claims_done = any(word in lower for word in ["completed", "done", "implemented", "fixed"])
    validation_mentions = any(word in lower for word in ["test", "validated", "verified", "not run"])
    blockers_hidden = "blocker" in lower and "unresolved" not in lower
    result = {
        "complete_enough": (not claims_done or validation_mentions) and not blockers_hidden,
        "claims_completion": claims_done,
        "validation_mentioned": validation_mentions,
        "changed_files": [str(p).replace("\\", "/") for p in changed_files(root)],
        "recommendations": [],
    }
    if claims_done and not validation_mentions:
        result["recommendations"].append("Mention validation performed or explicitly state why validation was not run.")
    if blockers_hidden:
        result["recommendations"].append("State unresolved blockers clearly before finishing.")
    write_json(engineering_root(root) / "reports" / "completion" / "completion-contract-check.json", result)
    return result


def definition_of_done_check(root: Path, task_type: str, final_text: str = "") -> dict[str, Any]:
    requirements = {
        "architecture": ["system map", "decision", "risk", "adr", "open question"],
        "implementation": ["changed", "test", "hygiene", "summary"],
        "review": ["severity", "file", "line", "recommendation"],
    }.get(task_type, ["summary", "validation"])
    lower = final_text.lower()
    missing = [item for item in requirements if item not in lower]
    return {"task_type": task_type, "done": not missing, "missing": missing}


def final_answer_structure_check(task_type: str, text: str) -> dict[str, Any]:
    required = (
        ["summary", "files", "validation", "risks"]
        if task_type == "implementation"
        else ["recommendation", "rationale", "trade", "structure", "sequence"]
    )
    lower = text.lower()
    missing = [item for item in required if item not in lower]
    return {"valid": not missing, "missing": missing}


def artifact_completeness_score(root: Path, files: list[str]) -> dict[str, Any]:
    targets = [root / item for item in files] if files else [p for p in engineering_root(root).rglob("*.md")]
    results = []
    for path in targets:
        if not path.exists():
            results.append({"artifact": relpath(path, root), "score": 0, "missing_sections": ["file missing"]})
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        headings = re.findall(r"^##+\s+(.+)$", text, re.M)
        fm, _ = parse_front_matter(text)
        missing = []
        if not fm:
            missing.append("front matter")
        if len(headings) < 3:
            missing.append("minimum headings")
        if re.search(r"TODO|TBD|<replace-me>", text, re.I):
            missing.append("resolved placeholders")
        score = max(0, 100 - len(missing) * 30)
        results.append(
            {
                "artifact": relpath(path, root),
                "score": score,
                "missing_sections": missing,
                "recommendation": "Revise before marking complete." if missing else "Ready.",
            }
        )
    result = {"artifacts": results}
    write_json(engineering_root(root) / "reports" / "validation" / "artifact-completeness-score.json", result)
    return result


def artifact_consistency_check(root: Path) -> dict[str, Any]:
    artifacts = [
        relpath(p, root) for p in engineering_root(root).rglob("*") if p.suffix in {".md", ".json", ".yaml", ".yml"}
    ]
    return {
        "checked_artifacts": artifacts,
        "warnings": [],
        "recommendation": "No deterministic cross-artifact contradictions detected.",
    }


def naming_consistency_check(root: Path) -> dict[str, Any]:
    names: dict[str, int] = {}
    for path in [p for p in engineering_root(root).rglob("*.md") if p.is_file()]:
        for name in re.findall(
            r"\b[A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b", path.read_text(encoding="utf-8", errors="ignore")
        ):
            names[name] = names.get(name, 0) + 1
    return {
        "canonical_candidates": dict(sorted(names.items(), key=lambda item: (-item[1], item[0]))[:50]),
        "warnings": [],
    }


def diagram_sync_check(root: Path) -> dict[str, Any]:
    diagrams = [relpath(p, root) for p in root.rglob("*.mmd") if ".git" not in p.parts]
    warnings = []
    for path_text in diagrams:
        text = (root / path_text).read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"\b(graph|flowchart|sequenceDiagram|classDiagram|erDiagram)\b", text):
            warnings.append(f"{path_text}: unknown Mermaid diagram type")
    return {"diagrams": diagrams, "warnings": warnings}


def example_output_validator(root: Path) -> dict[str, Any]:
    missing = []
    for skill in sorted((root / "skills").glob("*")):
        if not any((skill / name).exists() for name in ["examples", "templates"]):
            missing.append(relpath(skill, root))
    return {"valid": not missing, "skills_missing_examples_or_templates": missing}


def prompt_outcome_logger(root: Path, prompt: str, outcome: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "timestamp": now_iso(),
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
        "intent": classify_user_intent(prompt)["intent"],
        "outcome": outcome or {},
    }
    append_jsonl(engineering_root(root) / "reports" / "intake" / "prompt-outcomes.jsonl", item)
    return item


def skill_trigger_audit(root: Path) -> dict[str, Any]:
    skills = [p.name for p in sorted((root / "skills").glob("*")) if (p / "SKILL.md").exists()]
    trigger_data = (
        json.loads((root / "evals" / "trigger-evals.json").read_text(encoding="utf-8"))
        if (root / "evals" / "trigger-evals.json").exists()
        else {}
    )
    text = json.dumps(trigger_data)
    unused = [skill for skill in skills if skill not in text]
    prompt_cases = trigger_data.get("prompt_cases", []) if isinstance(trigger_data, dict) else []
    failures = []
    for case in prompt_cases:
        if not isinstance(case, dict) or not case.get("should_trigger"):
            continue
        routed = skill_router(case.get("query", "")).get("recommended_skill")
        if routed != case["should_trigger"]:
            failures.append({"id": case.get("id"), "expected": case["should_trigger"], "actual": routed})
    negative_failures = []
    for case in prompt_cases:
        if not isinstance(case, dict) or not case.get("should_not_trigger"):
            continue
        routed = skill_router(case.get("query", "")).get("recommended_skill")
        if routed == case["should_not_trigger"]:
            negative_failures.append({"id": case.get("id"), "forbidden": case["should_not_trigger"], "actual": routed})
    return {
        "unused_skills": unused,
        "overlapping_skills": [],
        "poor_trigger_descriptions": [],
        "prompt_case_count": len(prompt_cases),
        "trigger_failures": failures,
        "negative_trigger_failures": negative_failures,
        "valid": not unused and not failures and not negative_failures,
    }


def prompt_optimization_evaluator(root: Path) -> dict[str, Any]:
    audit = skill_trigger_audit(root)
    report = ["# Prompt Optimization Report", "", f"Generated: {now_iso()}", "", "## Findings"]
    if audit["unused_skills"]:
        report.append("- Some skills are not represented in trigger eval fixtures.")
    else:
        report.append("- Trigger fixtures mention the available skills.")
    if audit["trigger_failures"]:
        report.append(f"- {len(audit['trigger_failures'])} positive trigger case(s) route to the wrong skill.")
    if audit["negative_trigger_failures"]:
        report.append(
            f"- {len(audit['negative_trigger_failures'])} negative trigger case(s) route to a forbidden skill."
        )
    if not audit["trigger_failures"] and not audit["negative_trigger_failures"]:
        report.append("- Prompt trigger cases route as expected under the deterministic router.")
    out = root / "evals" / "reports" / "prompt-optimization-report.md"
    write_text(out, "\n".join(report) + "\n")
    return {"report": relpath(out, root), **audit}


def failure_pattern_miner(root: Path) -> dict[str, Any]:
    log = engineering_root(root) / "reports" / "intake" / "prompt-outcomes.jsonl"
    patterns: dict[str, int] = {}
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            status = item.get("outcome", {}).get("status", "unknown")
            patterns[status] = patterns.get(status, 0) + 1
    return {"patterns": patterns, "recommendations": []}


def dangerous_command_guard(command: str) -> dict[str, Any]:
    hits = [pattern for pattern in DANGEROUS_COMMANDS if re.search(pattern, command, re.I)]
    return {
        "blocked": bool(hits),
        "matches": hits,
        "reason": "Dangerous shell command detected." if hits else "No dangerous command detected.",
    }


def production_environment_guard(command: str) -> dict[str, Any]:
    hits = [pattern for pattern in PRODUCTION_PATTERNS if re.search(pattern, command, re.I)]
    return {"requires_approval": bool(hits), "matches": hits}


def secret_exfiltration_guard(command: str = "", text: str = "", path: str = "") -> dict[str, Any]:
    sample = "\n".join([command, text, path])
    hits = [pattern for pattern in SECRET_PATTERNS if re.search(pattern, sample, re.I)]
    return {
        "blocked": bool(hits),
        "matches": hits,
        "reason": "Potential secret exposure detected." if hits else "No secret exposure detected.",
    }


def sensitive_file_policy(path: str, action: str = "read") -> dict[str, Any]:
    category = classify_file_path(Path(path))
    sensitive = category == "secret-risk"
    decision = (
        "block"
        if sensitive and action in {"print", "copy"}
        else "ask"
        if sensitive and action in {"edit", "write"}
        else "warn"
        if sensitive
        else "allow"
    )
    return {"sensitive": sensitive, "category": category, "action": decision, "path": path}


def generated_file_guard(path: str) -> dict[str, Any]:
    generated = classify_file_path(Path(path)) == "generated"
    return {
        "generated": generated,
        "message": "Edit the source schema/template instead and regenerate."
        if generated
        else "Not recognized as generated.",
    }


def dependency_risk_check(root: Path) -> dict[str, Any]:
    package_files = [
        p
        for p in changed_files(root)
        if p.name in {"package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod"}
    ]
    return {
        "changed_package_files": [str(p).replace("\\", "/") for p in package_files],
        "requires_justification": bool(package_files),
    }


def migration_risk_check(root: Path, files: list[str] | None = None) -> dict[str, Any]:
    targets = (
        [root / f for f in files] if files else [root / p for p in changed_files(root) if "migration" in str(p).lower()]
    )
    warnings = []
    for path in targets:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for word in ["drop table", "drop column", "truncate", "not null", "delete from"]:
                if word in text:
                    warnings.append(f"{relpath(path, root)}: {word}")
    return {"warnings": warnings, "high_risk": bool(warnings)}


def api_contract_breaking_change_check(root: Path, files: list[str] | None = None) -> dict[str, Any]:
    targets = (
        [root / f for f in files]
        if files
        else [root / p for p in changed_files(root) if p.suffix.lower() in {".yaml", ".yml", ".json", ".ts", ".py"}]
    )
    warnings = []
    for path in targets:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if any(term in text for term in ["removed", "rename", "breaking", "deprecated"]):
                warnings.append(relpath(path, root))
    return {"possible_breaking_changes": warnings}


def architecture_decision_detector(root: Path, text: str) -> dict[str, Any]:
    detected = bool(
        re.search(r"\b(queue|sync|database model|service boundary|provider|auth|permission|deployment)\b", text, re.I)
    )
    adr_files = (
        list((engineering_root(root) / "decisions").glob("*.md"))
        if (engineering_root(root) / "decisions").exists()
        else []
    )
    return {
        "decision_detected": detected,
        "adr_required": detected and not adr_files,
        "suggested_title": "ADR-record-architecture-decision" if detected else None,
    }


# Council triggers use word-boundary regex (not bare substring) plus an AND rule:
# suggest the council for a strong signal on its own, OR a domain signal backed by a
# scale signal. This catches genuinely high-stakes work ("migrate the billing database",
# "integrate an external provider across all services") without firing on routine
# prompts like "add an auth header".
COUNCIL_STRONG_TRIGGERS = [
    r"build vs\.? buy",
    r"\birreversible\b",
    r"re-?architect",
    r"\brewrite\b",
    r"breaking change",
    r"\bmigrat(e|es|ing|ion)\b",
    r"new (plugin|subsystem|service|system)",
    r"architectur\w* decision",
    r"high[- ]stakes",
    r"\btradeoff\b",
]
COUNCIL_DOMAIN_TRIGGERS = [
    r"\bsecurity\b",
    r"\bauth(entication|orization)?\b",
    r"\boauth\b",
    r"\bprovider\b",
    r"\bintegrat(e|es|ing|ion)\b",
    r"\bscal(e|es|ing|ability)\b",
    r"\bai model\b",
    r"\bllm\b",
    r"\beval(uation)?s?\b",
    r"data model",
    r"schema change",
    r"deploy\w* pipeline",
    r"external system",
    r"\bcompliance\b",
    r"\bpayment\b",
    r"\bbilling\b",
]
COUNCIL_SCALE_SIGNALS = [
    r"cross-cutting",
    r"\bacross\b",
    r"\bmultiple\b",
    r"\bseveral\b",
    r"\bentire\b",
    r"\bwhole\b",
    r"end-to-end",
    r"\benormous\b",
    r"\bcritical\b",
    r"\bmajor\b",
    r"\bplugin\b",
    r"\bsubsystem\b",
    r"\bplatform\b",
    r"\ball (of|the)\b",
]


def _regex_hits(patterns: list[str], text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            hits.append(match.group(0).strip())
    return sorted(set(hits))


def council_trigger_detector(text: str) -> dict[str, Any]:
    low = text.lower()
    strong = _regex_hits(COUNCIL_STRONG_TRIGGERS, low)
    domain = _regex_hits(COUNCIL_DOMAIN_TRIGGERS, low)
    scale = _regex_hits(COUNCIL_SCALE_SIGNALS, low)
    recommend = bool(strong) or (bool(domain) and bool(scale))
    triggers = sorted(set(strong + (domain if recommend else [])))
    reason = (
        "High-impact decision detected ("
        + ", ".join(triggers)
        + ") — an engineering council review is recommended before proceeding."
        if recommend
        else "No high-stakes council trigger detected."
    )
    return {"recommend_council": recommend, "reason": reason, "triggers": triggers, "scale_signals": scale}


def linear_pending(root: Path) -> dict[str, Any]:
    """Deterministic 'tasks not yet in Linear' count for the intake reminder.

    Only reports when Linear is configured. Hooks cannot call MCP, so this compares
    the ledger tasks to the local sync state (linear-state.json) with no network.
    """
    ledger = engineering_root(root) / "ledger"
    config = read_json(ledger / "linear-config.json", None)
    if not isinstance(config, dict) or not config.get("team") or config.get("team") == "unknown":
        return {"configured": False, "pending": 0, "enforcement": "off"}
    state = read_json(ledger / "linear-state.json", {"tasks": {}})
    synced = state.get("tasks", {}) if isinstance(state, dict) else {}
    keys: set[str] = set()
    action_data = read_json(ledger / "action-items.json", {})
    for item in action_data.get("action_items", []) if isinstance(action_data, dict) else []:
        keys.add(f"action:{item.get('id')}")
    human_data = read_json(ledger / "human-tasks.json", {})
    for item in human_data.get("human_tasks", []) if isinstance(human_data, dict) else []:
        keys.add(f"human:{item.get('id')}")
    pending = sum(1 for key in keys if key not in synced)
    return {"configured": True, "pending": pending, "enforcement": config.get("enforcement", "remind")}


def council_enforcement(root: Path) -> str:
    """Council suggestion strength: off | remind (default) | ask.

    Never a hard block — honors the plugin's 'suggest, don't auto-run' council design.
    """
    config = read_json(engineering_root(root) / "council" / "council-config.json", None)
    if isinstance(config, dict) and config.get("enforcement") in {"off", "remind", "ask"}:
        return config["enforcement"]
    return "remind"


def council_input_builder(root: Path, question: str, contexts: list[str]) -> dict[str, Any]:
    data = repo_context_pack(root)
    payload = {
        "question": question,
        "repo_context": data,
        "context_files": contexts,
        "created_at": now_iso(),
        "success_criteria": [],
        "risk_tolerance": "unknown",
    }
    out = engineering_root(root) / "council" / f"{slugify(question)[:48] or 'council-input'}-input.json"
    write_json(out, payload)
    return {"input": relpath(out, root), **payload}


def council_synthesizer(root: Path, run_dir: str | None = None, question: str = "") -> dict[str, Any]:
    base = (
        root / run_dir
        if run_dir
        else engineering_root(root) / "council" / (slugify(question)[:48] or "council-synthesis")
    )
    drafts = list((base / "advisor-drafts").glob("*.md")) if (base / "advisor-drafts").exists() else []
    text = "# Council Synthesis\n\n"
    text += f"Question: {question or 'See input file.'}\n\n"
    text += f"Advisor drafts reviewed: {len(drafts)}\n\nRecommendation: Review dissent and record an ADR for accepted architecture decisions.\n"
    out = base / "synthesis.md"
    write_text(out, text)
    return {"synthesis": relpath(out, root), "advisor_count": len(drafts)}


def council_role_runner(role: str, question: str) -> dict[str, Any]:
    return {
        "role": role,
        "question": question,
        "draft": f"{role} perspective: identify evidence, tradeoffs, risks, and next actions.",
    }


def council_anonymizer(files: list[str]) -> dict[str, Any]:
    anonymized = [{"source": item, "anonymous_id": f"advisor-{idx + 1}"} for idx, item in enumerate(files)]
    return {"anonymized": anonymized}


def council_peer_review(files: list[str]) -> dict[str, Any]:
    return {
        "reviewed": files,
        "summary": "No deterministic contradictions detected; human or model review still required.",
    }


def council_fixture_recorder(root: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    out = root / "evals" / "fixtures" / f"{slugify(name)}.json"
    write_json(out, payload or {"recorded_at": now_iso(), "name": name})
    return {"fixture": relpath(out, root)}


def prompt_rewrite_suggestions(prompt: str) -> dict[str, Any]:
    intent = classify_user_intent(prompt)
    return {
        "interpreted_task": prompt.strip(),
        "required_context_to_inspect": ["relevant routes/modules", "tests", "recent diffs", "docs"],
        "before_editing": ["identify expected behavior", "locate failure or target files", "map affected components"],
        "completion_criteria": [
            "cause or rationale explained",
            "minimal change planned",
            "relevant validation identified",
        ],
        "intent": intent,
    }


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool might need, resolved once before dispatch.

    Tools take this rather than the raw Namespace so a registry entry can stay a
    single expression, and so the payload is parsed once instead of per branch.
    """

    args: argparse.Namespace
    root: Path
    payload: dict[str, Any]
    prompt: str
    text: str
    command: str
    path: str
    files: list[str]
    hook_tool_name: str


def _ask_user_question_bridge(c: ToolContext) -> Any:
    # Record the question before allowing the tool through. Previously this
    # returned allow and kept nothing, so every question the assistant asked and
    # every answer it received was discarded.
    capture_asked_questions(c.root, c.payload)
    return hook_output("PreToolUse", permissionDecision="allow")


def _open_questions(c: ToolContext) -> Any:
    if c.args.answer:
        return answer_question(c.root, c.args.id or c.args.question, c.args.answer, c.args.status)
    if c.args.question:
        record_questions(c.root, [{"question": c.args.question, "kind": c.args.kind}])
    return sync_open_questions(c.root)


def _sensitive_file_policy(c: ToolContext) -> Any:
    action = c.args.action
    if c.args.hook and c.hook_tool_name in {"Edit", "MultiEdit"}:
        action = "edit"
    elif c.args.hook and c.hook_tool_name == "Write":
        action = "write"
    return sensitive_file_policy(c.path, action)


def _edit_scope_guard(c: ToolContext) -> Any:
    allowed = load_current_plan_scope(c.root)
    outside = bool(c.path and allowed and str(Path(c.path)).replace("\\", "/") not in allowed)
    return {
        "outside_scope": outside,
        "allowed_files": allowed,
        "path": c.path,
        "wrong_initiative": wrong_initiative_write(c.root, c.path),
    }


def _post_edit_hygiene(c: ToolContext) -> Any:
    return {
        "changed_files": classify_changed(c.root, c.files),
        "env": env_example_sync(c.root, False),
        "gitignore": gitignore_sync(c.root, False),
        "schemas": schema_validator(c.root),
    }


def _stop_completion_check(c: ToolContext) -> Any:
    return {
        "completion": completion_contract_check(c.root, c.text or c.prompt),
        "artifact_completeness": artifact_completeness_score(c.root, c.files),
    }


def _user_prompt_intake(c: ToolContext) -> Any:
    intent = classify_user_intent(c.prompt)
    result = {
        "intent": intent,
        "quality": prompt_quality_score(c.prompt),
        "clarification": clarification_gate(c.prompt),
        "skill_route": skill_router(c.prompt),
        "council": {**council_trigger_detector(c.prompt), "enforcement": council_enforcement(c.root)},
        "linear": linear_pending(c.root),
        "questions": sync_open_questions(c.root) if workspace_exists(c.root) else {"open_count": 0},
        # Answers "which initiative is this?" every turn. The resolver existed
        # but was never called from anywhere, so nothing ever noticed a pivot.
        "initiative": initiative_drift_detector(c.root, c.prompt, intent),
    }
    # Always emit intake context (intent, quality, council, linear), but only
    # persist the intake log once the workspace exists. A UserPromptSubmit hook
    # must never create .project just because the user typed a prompt.
    if workspace_exists(c.root):
        write_json(engineering_root(c.root) / "reports" / "intake" / f"{now_iso().replace(':', '-')}.json", result)
    return result


# The dispatch table. Keys are tool names as invoked by the dispatcher scripts in
# this directory and by hooks.json; several tools carry a second name because a
# hook script and a CLI script address the same logic.
#
# A table rather than a chain of comparisons so the set of tools is enumerable:
# `test_every_dispatcher_script_resolves_to_a_registered_tool` walks these keys
# against the scripts on disk, which catches a shim whose name no tool answers to
# and a tool no shim can reach. A 57-branch if-chain cannot be checked that way.
TOOLS: dict[str, Callable[[ToolContext], Any]] = {
    # context and detection
    "detect-stack": lambda c: detect_stack(c.root),
    "repo-context-pack": lambda c: repo_context_pack(c.root),
    "load-project-memory": lambda c: load_project_memory(c.root),
    # prompt intake
    "classify-user-intent": lambda c: classify_user_intent(c.prompt),
    "prompt-quality-score": lambda c: prompt_quality_score(c.prompt),
    "prompt-rewrite-suggestions": lambda c: prompt_rewrite_suggestions(c.prompt),
    "skill-router": lambda c: skill_router(c.prompt),
    "clarification-gate": lambda c: clarification_gate(c.prompt),
    "ambiguity-patterns": lambda c: ambiguity_patterns(c.prompt),
    "user-prompt-intake": _user_prompt_intake,
    # questions and initiative identity
    "ask-user-question-bridge": _ask_user_question_bridge,
    "open-questions": _open_questions,
    "active-initiative-resolver": lambda c: active_initiative_resolver(c.root, c.prompt),
    "initiative-drift-detector": lambda c: initiative_drift_detector(c.root, c.prompt, classify_user_intent(c.prompt)),
    "initiative": lambda c: initiative_command(c.root, c.args.action, c.args.id or c.args.name, c.args.text),
    # planning and decisions
    "plan-quality-gate": lambda c: plan_quality_gate(c.text or c.prompt),
    "architecture-decision-detector": lambda c: architecture_decision_detector(c.root, c.text or c.prompt),
    "council-trigger-detector": lambda c: council_trigger_detector(c.text or c.prompt),
    # guards
    "dangerous-command-guard": lambda c: dangerous_command_guard(c.command),
    "production-environment-guard": lambda c: production_environment_guard(c.command),
    "secret-exfiltration-guard": lambda c: secret_exfiltration_guard(c.command, c.text, c.path),
    "sensitive-file-policy": _sensitive_file_policy,
    "generated-file-guard": lambda c: generated_file_guard(c.path),
    "edit-scope-guard": _edit_scope_guard,
    # hygiene
    "changed-files-classifier": lambda c: classify_changed(c.root, c.files),
    "env-example-sync": lambda c: env_example_sync(c.root, c.args.apply),
    "gitignore-sync": lambda c: gitignore_sync(c.root, c.args.apply),
    "schema-validator": lambda c: schema_validator(c.root),
    "markdown-artifact-validator": lambda c: markdown_artifact_validator(c.root, c.files),
    "post-edit-hygiene": _post_edit_hygiene,
    # verification
    "test-command-resolver": lambda c: test_command_resolver(c.root, c.files),
    "test-result-parser": lambda c: test_result_parser(c.text, c.command),
    "completion-contract-check": lambda c: completion_contract_check(c.root, c.text or c.prompt),
    "definition-of-done-check": lambda c: definition_of_done_check(c.root, c.args.task_type, c.text or c.prompt),
    "final-answer-structure-check": lambda c: final_answer_structure_check(c.args.task_type, c.text or c.prompt),
    "artifact-completeness-score": lambda c: artifact_completeness_score(c.root, c.files),
    "artifact-consistency-check": lambda c: artifact_consistency_check(c.root),
    "naming-consistency-check": lambda c: naming_consistency_check(c.root),
    "diagram-sync-check": lambda c: diagram_sync_check(c.root),
    "example-output-validator": lambda c: example_output_validator(c.root),
    "stop-completion-check": _stop_completion_check,
    # risk
    "dependency-risk-check": lambda c: dependency_risk_check(c.root),
    "migration-risk-check": lambda c: migration_risk_check(c.root, c.files),
    "api-contract-breaking-change-check": lambda c: api_contract_breaking_change_check(c.root, c.files),
    # telemetry and evaluation
    "prompt-outcome-logger": lambda c: prompt_outcome_logger(c.root, c.prompt),
    "skill-trigger-audit": lambda c: skill_trigger_audit(c.root),
    "prompt-optimization-evaluator": lambda c: prompt_optimization_evaluator(c.root),
    "failure-pattern-miner": lambda c: failure_pattern_miner(c.root),
    # council
    "council-input-builder": lambda c: council_input_builder(c.root, c.prompt or c.args.question, c.files),
    "council-synthesizer": lambda c: council_synthesizer(c.root, c.args.run_dir, c.prompt or c.args.question),
    "council-role-runner": lambda c: council_role_runner(c.args.role, c.prompt or c.args.question),
    "council-anonymizer": lambda c: council_anonymizer(c.files),
    "council-peer-review": lambda c: council_peer_review(c.files),
    "council-fixture-recorder": lambda c: council_fixture_recorder(c.root, c.args.name, c.payload),
}


def run_tool(name: str, args: argparse.Namespace) -> dict[str, Any]:
    handler = TOOLS.get(name)
    if handler is None:
        raise SystemExit(f"unknown tool: {name}")
    payload = load_hook_payload() if args.hook else {}
    return handler(
        ToolContext(
            args=args,
            root=repo_root(Path(args.root)),
            payload=payload,
            prompt=args.prompt or prompt_from_payload(payload),
            text=args.text or text_from_payload(payload),
            command=args.command or command_from_payload(payload),
            path=args.path or file_from_payload(payload),
            files=args.file or [],
            hook_tool_name=str(payload.get("tool_name") or payload.get("toolName") or ""),
        )
    )


def wrong_initiative_write(root: Path, path: str) -> dict[str, Any]:
    """True when an edit targets an initiative other than the active one.

    The last line of defence for initiative drift. The intake hook asks at the
    top of the turn; this catches the case where the model proceeded anyway, or
    where the drift only became apparent once a path was chosen.
    """
    result: dict[str, Any] = {"mismatch": False, "target": None, "active": None}
    if not path or not workspace_exists(root):
        return result
    parts = Path(str(path).replace("\\", "/")).as_posix().split("/")
    if "initiatives" not in parts:
        return result
    index = parts.index("initiatives")
    if index + 1 >= len(parts):
        return result
    target = parts[index + 1]
    if target.endswith(".json"):  # registry.json and friends are not initiatives
        return result
    active = load_initiative_registry(root)["active"]
    result.update(target=target, active=active, mismatch=bool(active and target != active))
    return result


def load_current_plan_scope(root: Path) -> list[str]:
    path = engineering_root(root) / "current-plan.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    values = data.get("affected_files") or data.get("files") or []
    return [str(item).replace("\\", "/") for item in values if isinstance(item, str)]


def render_hook(tool_name: str, result: dict[str, Any]) -> dict[str, Any] | None:
    if tool_name in {"dangerous-command-guard", "secret-exfiltration-guard"} and result.get("blocked"):
        return permission_output("PreToolUse", "deny", result.get("reason", "Blocked by Engineering Lifecycle guard."))
    if tool_name == "production-environment-guard" and result.get("requires_approval"):
        return permission_output("PreToolUse", "ask", "Command appears to target production.")
    if tool_name == "edit-scope-guard":
        wrong = result.get("wrong_initiative") or {}
        if wrong.get("mismatch"):
            return permission_output(
                "PreToolUse",
                "ask",
                f"This writes into initiative '{wrong['target']}' while '{wrong['active']}' is active. "
                f"Confirm the target, or run `/initiative switch {wrong['target']}` first.",
            )
        if result.get("outside_scope"):
            return permission_output("PreToolUse", "ask", "This file is outside the approved implementation scope.")
    if tool_name == "generated-file-guard" and result.get("generated"):
        return hook_additional_context("PreToolUse", result["message"])
    if tool_name == "sensitive-file-policy" and result.get("sensitive"):
        action = result.get("action")
        if action == "block":
            return permission_output("PreToolUse", "deny", "Sensitive file contents must not be printed or copied.")
        if action == "ask":
            return permission_output(
                "PreToolUse",
                "ask",
                "This edit targets a sensitive file. Confirm the change is intentional and does not expose secrets.",
            )
        return hook_additional_context(
            "PreToolUse", "Sensitive file detected. Do not expose secret values in outputs or generated artifacts."
        )
    if tool_name == "user-prompt-intake":
        quality = result["quality"]
        clarification = result["clarification"]
        messages = [
            f"Intent: {result['intent']['intent']} ({result['intent']['confidence']}).",
            f"Recommended skill: {result['skill_route'].get('recommended_skill')}.",
            f"Prompt quality score: {quality['score']} ({quality['risk']} risk).",
        ]
        # Surfaced before anything else that writes artifacts, so a pivot is
        # caught at the top of the turn rather than after the files land.
        initiative = result.get("initiative") or {}
        if initiative.get("active"):
            messages.append(f"Active initiative: {initiative['active']}.")
        if initiative.get("drift") and initiative.get("message"):
            messages.append(initiative["message"])
        if clarification["requires_clarification"]:
            messages.append("Clarification is recommended before implementation: " + clarification["reason"])
        council = result.get("council") or {}
        council_level = council.get("enforcement", "remind")
        if council.get("recommend_council") and council_level != "off":
            triggers = ", ".join(council.get("triggers", []))
            if council_level == "ask":
                messages.append(
                    "High-stakes work detected (" + triggers + "). Run the run-engineering-council "
                    "skill for independent review before proceeding, or explicitly confirm you are skipping it."
                )
            else:
                messages.append(
                    "High-stakes work detected (" + triggers + "). Consider running the "
                    "run-engineering-council skill for independent review before planning or "
                    "implementing. This is a suggestion, not a block."
                )
        linear = result.get("linear") or {}
        if linear.get("configured") and linear.get("pending") and linear.get("enforcement") != "off":
            messages.append(
                f"{linear['pending']} task(s) are not yet tracked in Linear. "
                "Run `eng-life linear-sync plan` to push them."
            )
        # Surfaced every turn so a question the human never answered stops being
        # forgotten the moment the turn that raised it ends.
        questions = result.get("questions") or {}
        if questions.get("open_count"):
            unanswered = [
                entry["question"] for entry in questions.get("open_questions", []) if entry.get("status") == "open"
            ][:3]
            listed = "".join(f"\n  - {item}" for item in unanswered)
            messages.append(
                f"{questions['open_count']} open question(s) awaiting a human answer "
                f"({questions.get('path', 'questions/open-questions.json')}):{listed}"
            )
        return hook_additional_context("UserPromptSubmit", "\n".join(messages))
    if tool_name == "post-edit-hygiene":
        return hook_additional_context(
            "PostToolBatch",
            "Post-edit hygiene checks completed. Review generated validation reports if issues are present.",
        )
    if tool_name == "stop-completion-check":
        # Stop hooks must stay silent. Any output from a Stop hook is injected
        # back into the conversation as context and re-invokes the model; with
        # no pending request the model replies "(Standing by.)" and stops again,
        # which re-fires this hook -> an endless loop. Recommendations are
        # available via the non-hook CLI output; never inject them on Stop.
        #
        # This is also why unanswered open questions are NOT surfaced here, which
        # is where you would first think to put them. They are surfaced at
        # UserPromptSubmit instead (see the "questions" branch below), which fires
        # on every turn rather than once at the end - strictly more visible, and
        # the only route that does not risk the loop above.
        return None
    return None


def cli_main(tool_name: str | None = None) -> int:
    inferred = Path(os.environ.get("QUALITY_TOOL_NAME", "") or Path(__file__).stem).stem
    name = (tool_name or inferred).replace(".py", "")
    parser = argparse.ArgumentParser(description=f"Run Engineering Lifecycle quality tool: {name}")
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--question", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--command", default="")
    parser.add_argument("--path", default="")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--run-dir")
    parser.add_argument("--role", default="executor")
    parser.add_argument("--name", default="council-fixture")
    parser.add_argument("--task-type", default="implementation")
    parser.add_argument(
        "--action", default="read", help="Verb for multi-action tools (initiative: new|switch|close|list)"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--id", default="", help="Open-question id to resolve")
    parser.add_argument("--answer", default="", help="Answer text that resolves an open question")
    parser.add_argument("--kind", default="general", choices=list(QUESTION_KINDS))
    parser.add_argument("--status", default="answered", choices=list(QUESTION_STATUSES))
    parser.add_argument(
        "--hook",
        action="store_true",
        help="Read Claude hook payload from stdin and emit hook-shaped JSON when applicable",
    )
    args = parser.parse_args()
    # Tools wired to the Stop event must stay silent unless render_hook returns
    # an explicit payload: any stdout from a Stop hook is injected back into the
    # conversation as context and re-invokes the model, producing an endless
    # "(Standing by.)" loop. Other events keep the raw-result fallback so the
    # PreToolUse guards still report their allow/block decisions.
    silent_when_empty = {"stop-completion-check"}
    result = run_tool(name, args)
    if args.hook:
        hook = render_hook(name, result)
        if hook is not None:
            emit_json(hook)
        elif name not in silent_when_empty:
            emit_json(result)
    else:
        emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
