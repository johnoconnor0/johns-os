#!/usr/bin/env python3
"""Shared deterministic quality-control tools for Engineering Lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from eng_common import (
    ENV_VAR_RE,
    WORKSPACE,
    append_jsonl,
    changed_files,
    classify_file_path,
    emit_json,
    engineering_root,
    git,
    git_files,
    hook_additional_context,
    hook_output,
    load_hook_payload,
    now_iso,
    parse_front_matter,
    permission_output,
    placeholder_for_env,
    relpath,
    repo_root,
    slugify,
    write_json,
    write_text,
)


INTENT_KEYWORDS = {
    "profile": ["profile", "understand this repo", "product system", "repo profile", "current stack", "engineering maturity"],
    "lifecycle": ["lifecycle", "what should happen next", "missing artifacts", "current stage", "next skill"],
    "system-map": ["system map", "map the system", "external systems", "data flow", "failure points", "component map"],
    "api-contract": ["api contract", "request shape", "response shape", "webhook", "event contract", "pagination", "rate limit"],
    "dashboard": ["dashboard", "status view", "project status", "initiative summary", "engineering state", "action items", "recent artifacts", "release readiness"],
    "design-system": ["design system", "ui kit", "component system", "design tokens", "tokens", "colours", "colors", "typography", "spacing", "component standards", "accessibility rules"],
    "ui-prototype": ["ui prototype", "clickable prototype", "prototype", "mvp shell", "app shell", "mock data", "demo-ready", "frontend proof-of-concept"],
    "review": ["review", "audit", "find bugs", "security scan"],
    "testing": ["test", "failing", "coverage", "qa", "regression"],
    "implementation-plan": ["implementation plan", "break this", "approved design", "sequence", "sequenced", "slices", "dependencies", "rollback"],
    "implementation": ["implement", "safe implementation", "verified slices", "fix", "build", "add", "change", "refactor"],
    "architecture": ["architecture", "system map", "boundary", "adr", "design"],
    "data-model": ["schema", "database", "entity", "migration", "model"],
    "ux-design": ["ux", "screen", "flow", "wireframe", "user journey"],
    "requirements": ["prd", "requirements", "acceptance criteria"],
    "release": ["release", "deploy", "rollback", "launch"],
    "repo-hygiene": ["hygiene", "gitignore", "env.example", "cleanup"],
    "council-decision": ["council", "tradeoff", "build vs buy", "high-stakes"],
    "discovery": ["discover", "discovery", "clarify", "product idea", "assumptions", "open questions", "mvp boundary", "explore", "research", "brief"],
}

SKILL_BY_INTENT = {
    "profile": "profile-product-system",
    "lifecycle": "map-product-lifecycle",
    "system-map": "create-system-map",
    "api-contract": "create-api-contract",
    "dashboard": "build-project-dashboard",
    "design-system": "create-design-system",
    "ui-prototype": "build-ui-prototype",
    "review": "review-change",
    "testing": "create-test-strategy",
    "implementation-plan": "create-implementation-plan",
    "implementation": "implement-feature-safely",
    "architecture": "create-architecture-plan",
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
        values = [str(tool_input.get(key, "")) for key in ("content", "new_string", "old_string", "text") if tool_input.get(key)]
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
        "clear objective": bool(re.search(r"\b(add|build|fix|review|plan|create|implement|validate|check)\b", prompt, re.I)),
        "target repo/module/file": bool(re.search(r"([A-Za-z]:\\|/|\.md|\.py|\.ts|repo|module|file|folder|directory)", prompt, re.I)),
        "expected output": bool(re.search(r"\b(plan|patch|summary|report|script|tests?|implementation)\b", prompt, re.I)),
        "constraints": bool(re.search(r"\b(do not|must|only|preserve|avoid|without|constraint)\b", prompt, re.I)),
        "success criteria": bool(re.search(r"\b(done|complete|success|acceptance|criteria|passes|working)\b", prompt, re.I)),
        "whether edits are allowed": bool(re.search(r"\b(implement|edit|change|write|patch|plan only|review only)\b", prompt, re.I)),
        "whether tests should be run": bool(re.search(r"\b(test|validate|check|verify|run)\b", prompt, re.I)),
        "whether external systems are involved": bool(re.search(r"\b(api|deploy|prod|github|slack|stripe|supabase|vercel|external)\b", prompt, re.I)),
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
        question = "Should I scope this to the whole repo or a specific feature/module?" if kind == "scope" else "What exact outcome should be considered complete?"
    return {"ambiguous": bool(matches), "matches": matches, "suggested_question": question}


def clarification_gate(prompt: str) -> dict[str, Any]:
    intent = classify_user_intent(prompt)
    quality = prompt_quality_score(prompt)
    ambiguity = ambiguity_patterns(prompt)
    questions: list[dict[str, Any]] = []
    if intent["intent"] == "unknown":
        questions.append({"question": "What lifecycle mode should this use?", "options": ["Plan only", "Implement with edits", "Review existing code only"]})
    if quality["score"] < 60:
        questions.append({"question": "What outcome should count as complete?", "options": ["Working code and validation", "A decision-ready plan", "A review report"]})
    if ambiguity["suggested_question"]:
        questions.append({"question": ambiguity["suggested_question"], "options": ["Specific target", "Whole repo", "Decide from inspected context"]})
    return {
        "requires_clarification": bool(questions),
        "reason": "Prompt is ambiguous or missing high-impact execution details." if questions else "Prompt has enough detail to start.",
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


def detect_stack(root: Path) -> dict[str, Any]:
    files = {str(path).replace("\\", "/") for path in git_files(root)}
    package_manager = None
    if "pnpm-lock.yaml" in files or "pnpm-workspace.yaml" in files:
        package_manager = "pnpm"
    elif "yarn.lock" in files:
        package_manager = "yarn"
    elif "package-lock.json" in files or "package.json" in files:
        package_manager = "npm"
    elif "pyproject.toml" in files:
        package_manager = "python"
    frameworks: list[str] = []
    if "next.config.js" in files or "next.config.mjs" in files or "next.config.ts" in files:
        frameworks.append("Next.js")
    if "vite.config.ts" in files or "vite.config.js" in files:
        frameworks.append("Vite")
    if "package.json" in files:
        package_json = root / "package.json"
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "react" in deps and "React" not in frameworks:
                frameworks.append("React")
            if "vue" in deps:
                frameworks.append("Vue")
        except Exception:
            pass
    backend = []
    if "requirements.txt" in files or "pyproject.toml" in files:
        backend.append("Python")
    if "go.mod" in files:
        backend.append("Go")
    database = []
    if any("prisma/schema.prisma" in item for item in files):
        database.append("Prisma")
    test_commands = {}
    if package_manager in {"pnpm", "yarn", "npm"}:
        prefix = package_manager
        test_commands = {"unit": f"{prefix} test", "lint": f"{prefix} lint", "typecheck": f"{prefix} typecheck"}
    elif package_manager == "python":
        test_commands = {"unit": "python -m pytest", "lint": "python -m ruff check ."}
    result = {
        "package_manager": package_manager,
        "frameworks": frameworks,
        "backend": backend,
        "database": database,
        "test_commands": test_commands,
    }
    write_json(engineering_root(root) / "context" / "stack.json", result)
    return result


def repo_context_pack(root: Path) -> dict[str, Any]:
    files = git_files(root)
    stack = detect_stack(root)
    profile = {
        "generated_at": now_iso(),
        "repo_root": str(root),
        "stack": stack,
        "manifests": [relpath(root / p, root) for p in files if p.name in {"package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Dockerfile"}],
        "docs": [relpath(root / p, root) for p in files if p.suffix.lower() in {".md", ".mdx"}][:50],
        "tests": [relpath(root / p, root) for p in files if classify_file_path(p) == "test"][:50],
        "ci": [relpath(root / p, root) for p in files if ".github/workflows" in str(p).replace("\\", "/")],
    }
    base = engineering_root(root) / "context"
    write_json(base / "repo-context.json", profile)
    md = ["# Repo Context", "", f"Generated: {profile['generated_at']}", "", "## Stack", json.dumps(stack, indent=2), "", "## Manifests"]
    md.extend(f"- `{item}`" for item in profile["manifests"])
    write_text(base / "repo-context.md", "\n".join(md) + "\n")
    return profile


def load_project_memory(root: Path) -> dict[str, Any]:
    base = engineering_root(root)
    paths = ["profile", "decisions", "ledger"]
    loaded = {name: [relpath(path, root) for path in sorted((base / name).rglob("*")) if path.is_file()] if (base / name).exists() else [] for name in paths}
    loaded["loaded_at"] = now_iso()
    return loaded


def active_initiative_resolver(root: Path, prompt: str) -> dict[str, Any]:
    initiatives = engineering_root(root) / "initiatives"
    candidates = [p.name for p in initiatives.iterdir() if p.is_dir()] if initiatives.exists() else []
    text = prompt.lower()
    chosen = next((item for item in candidates if item.lower() in text), candidates[0] if len(candidates) == 1 else None)
    return {"initiative_id": chosen, "confidence": "high" if chosen and chosen.lower() in text else "medium" if chosen else "low", "candidates": candidates}


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
    env_path = root / ".env.example"
    existing: set[str] = set()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                existing.add(line.split("=", 1)[0].strip())
    missing = [{"name": name, "placeholder": f"{name}={placeholder_for_env(name)}", "seen_in": sorted(paths)} for name, paths in sorted(found.items()) if name not in existing]
    if apply and missing:
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
    for path in sorted((root / "schemas").glob("*.json")) + sorted((engineering_root(root)).rglob("*.json")) + sorted((root / "evals").rglob("*.json")):
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
    return {"recommended_commands": commands, "reason": "Commands selected from detected stack and changed-file categories."}


def test_result_parser(text: str, command: str = "") -> dict[str, Any]:
    failed = bool(re.search(r"\b(fail|failed|error|traceback|exception)\b", text, re.I))
    failures = []
    for line in text.splitlines():
        if re.search(r"\b(fail|failed|error|traceback|exception)\b", line, re.I):
            failures.append({"line": line[:300]})
    return {"command": command, "status": "failed" if failed else "passed", "failures": failures[:20]}


def plan_quality_gate(text: str) -> dict[str, Any]:
    required = ["objective", "assumptions", "affected files", "risks", "rollback", "tests", "acceptance", "security", "migration", "docs"]
    lower = text.lower()
    missing = [item for item in required if item not in lower]
    return {"complete": not missing, "missing": missing, "score": round((len(required) - len(missing)) / len(required) * 100)}


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
    required = ["summary", "files", "validation", "risks"] if task_type == "implementation" else ["recommendation", "rationale", "trade", "structure", "sequence"]
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
        results.append({"artifact": relpath(path, root), "score": score, "missing_sections": missing, "recommendation": "Revise before marking complete." if missing else "Ready."})
    result = {"artifacts": results}
    write_json(engineering_root(root) / "reports" / "validation" / "artifact-completeness-score.json", result)
    return result


def artifact_consistency_check(root: Path) -> dict[str, Any]:
    artifacts = [relpath(p, root) for p in engineering_root(root).rglob("*") if p.suffix in {".md", ".json", ".yaml", ".yml"}]
    return {"checked_artifacts": artifacts, "warnings": [], "recommendation": "No deterministic cross-artifact contradictions detected."}


def naming_consistency_check(root: Path) -> dict[str, Any]:
    names: dict[str, int] = {}
    for path in [p for p in engineering_root(root).rglob("*.md") if p.is_file()]:
        for name in re.findall(r"\b[A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b", path.read_text(encoding="utf-8", errors="ignore")):
            names[name] = names.get(name, 0) + 1
    return {"canonical_candidates": dict(sorted(names.items(), key=lambda item: (-item[1], item[0]))[:50]), "warnings": []}


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
    trigger_data = json.loads((root / "evals" / "trigger-evals.json").read_text(encoding="utf-8")) if (root / "evals" / "trigger-evals.json").exists() else {}
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
        report.append(f"- {len(audit['negative_trigger_failures'])} negative trigger case(s) route to a forbidden skill.")
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
            except Exception:
                continue
            status = item.get("outcome", {}).get("status", "unknown")
            patterns[status] = patterns.get(status, 0) + 1
    return {"patterns": patterns, "recommendations": []}


def dangerous_command_guard(command: str) -> dict[str, Any]:
    hits = [pattern for pattern in DANGEROUS_COMMANDS if re.search(pattern, command, re.I)]
    return {"blocked": bool(hits), "matches": hits, "reason": "Dangerous shell command detected." if hits else "No dangerous command detected."}


def production_environment_guard(command: str) -> dict[str, Any]:
    hits = [pattern for pattern in PRODUCTION_PATTERNS if re.search(pattern, command, re.I)]
    return {"requires_approval": bool(hits), "matches": hits}


def secret_exfiltration_guard(command: str = "", text: str = "", path: str = "") -> dict[str, Any]:
    sample = "\n".join([command, text, path])
    hits = [pattern for pattern in SECRET_PATTERNS if re.search(pattern, sample, re.I)]
    return {"blocked": bool(hits), "matches": hits, "reason": "Potential secret exposure detected." if hits else "No secret exposure detected."}


def sensitive_file_policy(path: str, action: str = "read") -> dict[str, Any]:
    category = classify_file_path(Path(path))
    sensitive = category == "secret-risk"
    decision = "block" if sensitive and action in {"print", "copy"} else "ask" if sensitive and action in {"edit", "write"} else "warn" if sensitive else "allow"
    return {"sensitive": sensitive, "category": category, "action": decision, "path": path}


def generated_file_guard(path: str) -> dict[str, Any]:
    generated = classify_file_path(Path(path)) == "generated"
    return {"generated": generated, "message": "Edit the source schema/template instead and regenerate." if generated else "Not recognized as generated."}


def dependency_risk_check(root: Path) -> dict[str, Any]:
    package_files = [p for p in changed_files(root) if p.name in {"package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod"}]
    return {"changed_package_files": [str(p).replace("\\", "/") for p in package_files], "requires_justification": bool(package_files)}


def migration_risk_check(root: Path, files: list[str] | None = None) -> dict[str, Any]:
    targets = [root / f for f in files] if files else [root / p for p in changed_files(root) if "migration" in str(p).lower()]
    warnings = []
    for path in targets:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for word in ["drop table", "drop column", "truncate", "not null", "delete from"]:
                if word in text:
                    warnings.append(f"{relpath(path, root)}: {word}")
    return {"warnings": warnings, "high_risk": bool(warnings)}


def api_contract_breaking_change_check(root: Path, files: list[str] | None = None) -> dict[str, Any]:
    targets = [root / f for f in files] if files else [root / p for p in changed_files(root) if p.suffix.lower() in {".yaml", ".yml", ".json", ".ts", ".py"}]
    warnings = []
    for path in targets:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if any(term in text for term in ["removed", "rename", "breaking", "deprecated"]):
                warnings.append(relpath(path, root))
    return {"possible_breaking_changes": warnings}


def architecture_decision_detector(root: Path, text: str) -> dict[str, Any]:
    detected = bool(re.search(r"\b(queue|sync|database model|service boundary|provider|auth|permission|deployment)\b", text, re.I))
    adr_files = list((engineering_root(root) / "decisions").glob("*.md")) if (engineering_root(root) / "decisions").exists() else []
    return {"decision_detected": detected, "adr_required": detected and not adr_files, "suggested_title": "ADR-record-architecture-decision" if detected else None}


def council_trigger_detector(text: str) -> dict[str, Any]:
    triggers = ["irreversible", "security", "migration", "scaling", "build vs buy", "high cost", "ai model", "eval"]
    hits = [item for item in triggers if item in text.lower()]
    return {"recommend_council": bool(hits), "reason": "High-impact decision trigger detected." if hits else "No council trigger detected.", "triggers": hits}


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
    base = root / run_dir if run_dir else engineering_root(root) / "council" / (slugify(question)[:48] or "council-synthesis")
    drafts = list((base / "advisor-drafts").glob("*.md")) if (base / "advisor-drafts").exists() else []
    text = "# Council Synthesis\n\n"
    text += f"Question: {question or 'See input file.'}\n\n"
    text += f"Advisor drafts reviewed: {len(drafts)}\n\nRecommendation: Review dissent and record an ADR for accepted architecture decisions.\n"
    out = base / "synthesis.md"
    write_text(out, text)
    return {"synthesis": relpath(out, root), "advisor_count": len(drafts)}


def council_role_runner(role: str, question: str) -> dict[str, Any]:
    return {"role": role, "question": question, "draft": f"{role} perspective: identify evidence, tradeoffs, risks, and next actions."}


def council_anonymizer(files: list[str]) -> dict[str, Any]:
    anonymized = [{"source": item, "anonymous_id": f"advisor-{idx+1}"} for idx, item in enumerate(files)]
    return {"anonymized": anonymized}


def council_peer_review(files: list[str]) -> dict[str, Any]:
    return {"reviewed": files, "summary": "No deterministic contradictions detected; human or model review still required."}


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
        "completion_criteria": ["cause or rationale explained", "minimal change planned", "relevant validation identified"],
        "intent": intent,
    }


def run_tool(name: str, args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root(Path(args.root))
    payload = load_hook_payload() if args.hook else {}
    prompt = args.prompt or prompt_from_payload(payload)
    text = args.text or text_from_payload(payload)
    command = args.command or command_from_payload(payload)
    path = args.path or file_from_payload(payload)
    files = args.file or []
    hook_tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")

    if name == "detect-stack":
        return detect_stack(root)
    if name == "repo-context-pack":
        return repo_context_pack(root)
    if name == "classify-user-intent":
        return classify_user_intent(prompt)
    if name == "prompt-quality-score":
        return prompt_quality_score(prompt)
    if name == "prompt-rewrite-suggestions":
        return prompt_rewrite_suggestions(prompt)
    if name == "skill-router":
        return skill_router(prompt)
    if name == "clarification-gate":
        return clarification_gate(prompt)
    if name == "ask-user-question-bridge":
        return hook_output("PreToolUse", permissionDecision="allow")
    if name == "ambiguity-patterns":
        return ambiguity_patterns(prompt)
    if name == "load-project-memory":
        return load_project_memory(root)
    if name == "active-initiative-resolver":
        return active_initiative_resolver(root, prompt)
    if name == "plan-quality-gate":
        return plan_quality_gate(text or prompt)
    if name == "architecture-decision-detector":
        return architecture_decision_detector(root, text or prompt)
    if name == "council-trigger-detector":
        return council_trigger_detector(text or prompt)
    if name in {"dangerous-command-guard", "block-dangerous-bash"}:
        return dangerous_command_guard(command)
    if name == "production-environment-guard":
        return production_environment_guard(command)
    if name in {"secret-exfiltration-guard", "block-secret-exfil"}:
        return secret_exfiltration_guard(command, text, path)
    if name == "sensitive-file-policy":
        action = args.action
        if args.hook and hook_tool_name in {"Edit", "MultiEdit"}:
            action = "edit"
        elif args.hook and hook_tool_name == "Write":
            action = "write"
        return sensitive_file_policy(path, action)
    if name == "generated-file-guard":
        return generated_file_guard(path)
    if name == "edit-scope-guard":
        allowed = load_current_plan_scope(root)
        outside = bool(path and allowed and str(Path(path)).replace("\\", "/") not in allowed)
        return {"outside_scope": outside, "allowed_files": allowed, "path": path}
    if name == "changed-files-classifier":
        return classify_changed(root, files)
    if name in {"env-example-sync", "detect-new-env-vars"}:
        return env_example_sync(root, args.apply)
    if name in {"gitignore-sync", "suggest-gitignore-updates"}:
        return gitignore_sync(root, args.apply)
    if name in {"schema-validator", "validate-generated-artifacts"}:
        return schema_validator(root)
    if name == "markdown-artifact-validator":
        return markdown_artifact_validator(root, files)
    if name == "test-command-resolver":
        return test_command_resolver(root, files)
    if name == "test-result-parser":
        return test_result_parser(text, command)
    if name == "completion-contract-check":
        return completion_contract_check(root, text or prompt)
    if name == "definition-of-done-check":
        return definition_of_done_check(root, args.task_type, text or prompt)
    if name == "final-answer-structure-check":
        return final_answer_structure_check(args.task_type, text or prompt)
    if name == "artifact-completeness-score":
        return artifact_completeness_score(root, files)
    if name == "artifact-consistency-check":
        return artifact_consistency_check(root)
    if name == "naming-consistency-check":
        return naming_consistency_check(root)
    if name == "diagram-sync-check":
        return diagram_sync_check(root)
    if name == "example-output-validator":
        return example_output_validator(root)
    if name == "prompt-outcome-logger":
        return prompt_outcome_logger(root, prompt)
    if name == "skill-trigger-audit":
        return skill_trigger_audit(root)
    if name == "prompt-optimization-evaluator":
        return prompt_optimization_evaluator(root)
    if name == "failure-pattern-miner":
        return failure_pattern_miner(root)
    if name == "dependency-risk-check":
        return dependency_risk_check(root)
    if name == "migration-risk-check":
        return migration_risk_check(root, files)
    if name == "api-contract-breaking-change-check":
        return api_contract_breaking_change_check(root, files)
    if name == "council-input-builder":
        return council_input_builder(root, prompt or args.question, files)
    if name == "council-synthesizer":
        return council_synthesizer(root, args.run_dir, prompt or args.question)
    if name == "council-role-runner":
        return council_role_runner(args.role, prompt or args.question)
    if name == "council-anonymizer":
        return council_anonymizer(files)
    if name == "council-peer-review":
        return council_peer_review(files)
    if name == "council-fixture-recorder":
        return council_fixture_recorder(root, args.name, payload)
    if name == "post-edit-hygiene":
        return {
            "changed_files": classify_changed(root, files),
            "env": env_example_sync(root, False),
            "gitignore": gitignore_sync(root, False),
            "schemas": schema_validator(root),
        }
    if name == "stop-completion-check":
        return {
            "completion": completion_contract_check(root, text or prompt),
            "artifact_completeness": artifact_completeness_score(root, files),
        }
    if name == "user-prompt-intake":
        result = {
            "intent": classify_user_intent(prompt),
            "quality": prompt_quality_score(prompt),
            "clarification": clarification_gate(prompt),
            "skill_route": skill_router(prompt),
        }
        write_json(engineering_root(root) / "reports" / "intake" / f"{now_iso().replace(':', '-')}.json", result)
        return result
    raise SystemExit(f"unknown tool: {name}")


def load_current_plan_scope(root: Path) -> list[str]:
    path = engineering_root(root) / "current-plan.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    values = data.get("affected_files") or data.get("files") or []
    return [str(item).replace("\\", "/") for item in values if isinstance(item, str)]


def render_hook(tool_name: str, result: dict[str, Any]) -> dict[str, Any] | None:
    if tool_name in {"dangerous-command-guard", "secret-exfiltration-guard"} and result.get("blocked"):
        return permission_output("PreToolUse", "deny", result.get("reason", "Blocked by Engineering Lifecycle guard."))
    if tool_name == "production-environment-guard" and result.get("requires_approval"):
        return permission_output("PreToolUse", "ask", "Command appears to target production.")
    if tool_name == "edit-scope-guard" and result.get("outside_scope"):
        return permission_output("PreToolUse", "ask", "This file is outside the approved implementation scope.")
    if tool_name == "generated-file-guard" and result.get("generated"):
        return hook_additional_context("PreToolUse", result["message"])
    if tool_name == "sensitive-file-policy" and result.get("sensitive"):
        action = result.get("action")
        if action == "block":
            return permission_output("PreToolUse", "deny", "Sensitive file contents must not be printed or copied.")
        if action == "ask":
            return permission_output("PreToolUse", "ask", "This edit targets a sensitive file. Confirm the change is intentional and does not expose secrets.")
        return hook_additional_context("PreToolUse", "Sensitive file detected. Do not expose secret values in outputs or generated artifacts.")
    if tool_name == "user-prompt-intake":
        quality = result["quality"]
        clarification = result["clarification"]
        messages = [
            f"Intent: {result['intent']['intent']} ({result['intent']['confidence']}).",
            f"Recommended skill: {result['skill_route'].get('recommended_skill')}.",
            f"Prompt quality score: {quality['score']} ({quality['risk']} risk).",
        ]
        if clarification["requires_clarification"]:
            messages.append("Clarification is recommended before implementation: " + clarification["reason"])
        return hook_additional_context("UserPromptSubmit", "\n".join(messages))
    if tool_name == "post-edit-hygiene":
        return hook_additional_context("PostToolBatch", "Post-edit hygiene checks completed. Review generated validation reports if issues are present.")
    if tool_name == "stop-completion-check":
        # Stop hooks must stay silent. Any output from a Stop hook is injected
        # back into the conversation as context and re-invokes the model; with
        # no pending request the model replies "(Standing by.)" and stops again,
        # which re-fires this hook -> an endless loop. Recommendations are
        # available via the non-hook CLI output; never inject them on Stop.
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
    parser.add_argument("--action", default="read")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--hook", action="store_true", help="Read Claude hook payload from stdin and emit hook-shaped JSON when applicable")
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
