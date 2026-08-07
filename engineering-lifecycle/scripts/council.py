#!/usr/bin/env python3
"""Engineering Council runner with deterministic and live-model adapters."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from eng_common import (
    classify_file_path,
    engineering_root,
    now_iso,
    redact_secrets,
    relpath,
    repo_root,
    slugify,
    write_json,
    write_text,
)
from quality_tools import extract_open_questions, record_questions

ROLES = [
    ("contrarian", "Challenge weak assumptions and identify downside risk."),
    ("first-principles", "Reduce the decision to constraints, invariants, and necessary tradeoffs."),
    ("expansionist", "Look for broader opportunity, extensibility, and optionality."),
    ("outsider", "Apply an external, cross-domain perspective."),
    ("executor", "Focus on implementation cost, sequencing, reversibility, and delivery risk."),
]


ROLE_GUIDANCE = {
    "contrarian": [
        "Test whether the leading option depends on unverified provider behavior, migration safety, or hidden operational cost.",
        "Name concrete failure modes and safer reversible alternatives.",
    ],
    "first-principles": [
        "Reduce the decision to required capabilities, constraints, invariants, and non-requirements.",
        "Prefer the simplest design that satisfies the hard constraints.",
    ],
    "expansionist": [
        "Identify options that preserve future product or technical flexibility without forcing broad v1 scope.",
        "Flag where a small abstraction prevents likely rework.",
    ],
    "outsider": [
        "Question local defaults and compare the decision to common industry patterns.",
        "Separate useful outside patterns from generic best-practice claims.",
    ],
    "executor": [
        "Assess sequencing, implementation cost, rollback, testing, and operational readiness.",
        "Prefer decisions that can be shipped and validated in small slices.",
    ],
}


def event(path: Path, name: str, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"at": now_iso(), "event": name, "payload": payload}, sort_keys=True) + "\n")


# Trees that are never worth sending and frequently hold credentials.
_EXCLUDED_PARTS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build"})


def is_sensitive_context(path: Path) -> bool:
    """Whether this file must not be sent to a model provider.

    Everything under `--context` ends up in a POST body. A directory argument used
    to be expanded with rglob("*") and every file read, so `--context .` swept
    `.env`, `.env.local`, key material and `.git/config` - which carries tokens -
    off to Anthropic or OpenAI. `--max-context-chars` bounded how much of that
    went, not whether.
    """
    return classify_file_path(path) == "secret-risk" or bool(_EXCLUDED_PARTS.intersection(path.parts))


def context_files(contexts: list[str], root: Path) -> tuple[list[str], list[str]]:
    """Context paths and the ones deliberately withheld, relative to the root.

    Uses relpath rather than Path.relative_to because the two can disagree about
    the same directory on Windows. A path handed in as an 8.3 short name
    (C:\\Users\\RUNNER~1\\...) and a root that has been resolved to its long form
    (C:\\Users\\runneradmin\\...) are the same location, but relative_to compares
    the components literally and raises. relpath resolves both sides first and
    degrades to the absolute path instead of failing.

    Exclusions are returned rather than dropped silently: a user who genuinely
    meant to include a file needs to know it did not go.
    """
    files: list[str] = []
    excluded: list[str] = []
    for ctx in contexts:
        path = Path(ctx)
        full = path if path.is_absolute() else root / path
        candidates = sorted(p for p in full.rglob("*") if p.is_file()) if full.is_dir() else []
        if not full.is_dir() and full.exists():
            candidates = [full]
        for candidate in candidates:
            target = excluded if is_sensitive_context(candidate) else files
            target.append(relpath(candidate, root))
    return sorted(set(files)), sorted(set(excluded))


def context_snippets(root: Path, files: list[str], max_chars: int) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    remaining = max_chars
    for item in files:
        if remaining <= 0:
            break
        path = root / item
        if not path.exists() or not path.is_file():
            continue
        # Redacted before truncation, so a key split across the boundary cannot
        # survive as a fragment. The file-level exclusion above is the first line;
        # this catches a credential pasted into an ordinary source file.
        text = redact_secrets(path.read_text(encoding="utf-8", errors="replace"))
        chunk = text[:remaining]
        snippets.append({"path": item, "content": chunk})
        remaining -= len(chunk)
    return snippets


def source_block(files: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in files) if files else "  - none"


def evidence_markdown(files: list[str]) -> str:
    return "\n".join(f"- `{item}`" for item in files) or "- No context files supplied."


def prompt_context(snippets: list[dict[str, str]]) -> str:
    if not snippets:
        return "No context file contents were supplied. Work only from the question and explicitly mark uncertainty."
    blocks = []
    for snippet in snippets:
        blocks.append(f"### {snippet['path']}\n\n```text\n{snippet['content']}\n```")
    return "\n\n".join(blocks)


def render_advisor_prompt(role: str, purpose: str, question: str, snippets: list[dict[str, str]]) -> str:
    guidance = "\n".join(f"- {item}" for item in ROLE_GUIDANCE[role])
    return f"""You are the {role} advisor in an engineering council.

Decision question:
{question}

Role purpose:
{purpose}

Role-specific instructions:
{guidance}

Evidence:
{prompt_context(snippets)}

Return Markdown with exactly these sections:
# {role.title()} Advisor Draft
## Position
## Evidence Reviewed
## Analysis
## Evidence Gaps
## Recommendation

Rules:
- Ground claims in the supplied evidence or mark them as assumptions.
- Do not invent repository facts, external provider behavior, test results, or production status.
- Prefer concrete tradeoffs, risks, and next actions over generic advice.
"""


def render_peer_prompt(role: str, anonymous_ids: list[str], anonymous_texts: list[str]) -> str:
    drafts = "\n\n".join(anonymous_texts) or "No anonymous drafts were supplied."
    return f"""You are the {role} peer reviewer in an engineering council.

Review these anonymized advisor drafts without using role labels:
{drafts}

Return Markdown with exactly these sections:
# {role.title()} Peer Review
## Peer Drafts Reviewed
## Strongest Arguments
## Weak Assumptions
## Missing Evidence
## Findings

Rules:
- Preserve useful dissent.
- Flag unsupported claims and irreversible risks.
- Do not infer the original advisor role from anonymous IDs.
"""


def render_synthesis_prompt(
    question: str, files: list[str], advisor_texts: list[str], peer_texts: list[str], quorum: bool
) -> str:
    advisors = "\n\n".join(advisor_texts) or "No advisor drafts."
    peers = "\n\n".join(peer_texts) or "No peer reviews."
    return f"""You are the engineering council chairperson.

Decision question:
{question}

Council status:
{"quorum-met" if quorum else "quorum-failed"}

Evidence files:
{evidence_markdown(files)}

Advisor drafts:
{advisors}

Peer reviews:
{peers}

Return Markdown with exactly these sections:
# Engineering Council Synthesis
## Question
## Council Status
## Evidence
## Advisor Positions
## Blind Peer Review Summary
## Recommendation
## Dissent Log
## Decision
## Confidence
## Follow-up Artifacts
## Next Actions

Rules:
- Do not present a recommendation as final when quorum failed.
- Preserve meaningful dissent tied to evidence, reversibility, security, migration, or delivery risk.
- Separate recommendation from the owner decision.
"""


def front_matter(run_id: str, files: list[str]) -> str:
    return f"""---
initiative_id: council-{run_id}
skill: run-engineering-council
created_at: {now_iso()}
status: draft
confidence: medium
source_artifacts:
{source_block(files)}
---
"""


def with_front_matter(run_id: str, files: list[str], body: str) -> str:
    if body.startswith("---\n"):
        return body
    return front_matter(run_id, files) + "\n" + body.strip() + "\n"


def make_deterministic_advisor(role: str, purpose: str, question: str, files: list[str], run_id: str) -> str:
    guidance = "\n".join(f"- {item}" for item in ROLE_GUIDANCE[role])
    body = f"""# {role.title()} Advisor Draft

## Position

Use the {role} lens to answer: {question}

## Evidence Reviewed

{evidence_markdown(files)}

## Analysis

{purpose}

{guidance}

The draft is limited to the supplied context. Any recommendation below is conditional on resolving the evidence gaps listed in this artifact.

## Evidence Gaps

- Confirm whether the supplied context covers current implementation, constraints, and operational requirements.
- Confirm whether any external provider, security, migration, or compliance assumption affects the decision.

## Recommendation

Proceed only when the accepted plan records assumptions, rollback points, validation steps, and unresolved evidence gaps.
"""
    return with_front_matter(run_id, files, body)


def make_anonymized(anonymous_id: str, source: str, content: str) -> str:
    redacted = content.replace("Contrarian", "Advisor").replace("First-Principles", "Advisor")
    redacted = redacted.replace("Expansionist", "Advisor").replace("Outsider", "Advisor").replace("Executor", "Advisor")
    return f"# {anonymous_id}\n\nSource draft: `{source}`\n\nRole label removed for blind peer review.\n\n{redacted}\n"


def make_deterministic_peer_review(role: str, anonymous_ids: list[str], files: list[str], run_id: str) -> str:
    peer_list = "\n".join(f"- {peer}" for peer in anonymous_ids)
    body = f"""# {role.title()} Peer Review

## Peer Drafts Reviewed

{peer_list}

## Strongest Arguments

- Reversibility, evidence quality, and implementation sequencing are the strongest decision criteria.

## Weak Assumptions

- Any external provider, security, migration, or production assumption not present in supplied context remains unresolved.

## Missing Evidence

- Confirm current implementation files, operational constraints, and rollout requirements.

## Findings

- No deterministic contradiction was found from file presence alone.
- Chair synthesis must preserve any advisor concern tied to evidence gaps or irreversible risk.
"""
    return with_front_matter(run_id, files, body)


def make_deterministic_synthesis(question: str, files: list[str], run_id: str, quorum: bool) -> str:
    status = "quorum-met" if quorum else "quorum-failed"
    body = f"""# Engineering Council Synthesis

## Question

{question}

## Council Status

{status}

## Evidence

{evidence_markdown(files)}

## Advisor Positions

The council produced role-specific drafts for contrarian, first-principles, expansionist, outsider, and executor perspectives.

## Blind Peer Review Summary

An anonymized copy of each advisor draft was created before peer review. Deterministic peer review records the drafts reviewed and requires the chair to preserve evidence-bound dissent.

## Recommendation

Adopt the lowest-risk reversible option that satisfies the hard constraints unless the contrarian or executor draft identifies an unreduced safety, security, migration, or reversibility risk.

## Dissent Log

Preserve disagreements about irreversible decisions, external provider assumptions, migration risk, security posture, or delivery feasibility as action items.

## Decision

No final decision is automatic. The user or owning engineer must accept, reject, or revise the recommendation.

## Confidence

Medium when context files are supplied; low when no context files are supplied.

## Follow-up Artifacts

- ADR for accepted architecture or operations decisions.
- Implementation plan with rollback and validation steps.

## Next Actions

- [ ] Review advisor drafts and verify evidence gaps.
- [ ] Record the accepted decision as an ADR if the choice changes architecture or operations.
"""
    return with_front_matter(run_id, files, body)


def command_parts(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def extract_text_response(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise RuntimeError("live adapter returned no content")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict):
        for key in ("content", "text", "markdown", "response"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return text


def call_command_adapter(payload: dict[str, Any], timeout: int) -> str:
    command = os.environ.get("ENGINEERING_COUNCIL_ADAPTER_COMMAND", "").strip()
    if not command:
        raise RuntimeError("ENGINEERING_COUNCIL_ADAPTER_COMMAND is required for command adapter")
    proc = subprocess.run(
        command_parts(command),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if proc.returncode != 0:
        # Persisted verbatim into events.jsonl by the caller, and an adapter that
        # logs its configuration on failure logs its credentials with it.
        detail = redact_secrets(proc.stderr.strip())[:1000]
        raise RuntimeError(detail or f"command adapter exited {proc.returncode}")
    return extract_text_response(proc.stdout)


# The two providers this script knows how to speak to. The endpoint is
# env-overridable, which is useful for a proxy and is also how repository context
# and a live API key end up somewhere unintended.
ALLOWED_ADAPTER_HOSTS = frozenset({"api.anthropic.com", "api.openai.com"})


def check_endpoint(url: str) -> None:
    """Refuse to send context and a credential somewhere unverified.

    ENGINEERING_COUNCIL_ANTHROPIC_URL and _OPENAI_URL replace the endpoint
    outright, and nothing checked the scheme or the host - so an http:// override
    sent the whole prompt and the live x-api-key header in clear text to whatever
    host was named. Overriding is still supported; it now has to be deliberate.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(f"refusing to send context and credentials over {parsed.scheme or 'no'} scheme: {url}")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_ADAPTER_HOSTS and not os.environ.get("ENGINEERING_COUNCIL_ALLOW_ANY_HOST"):
        raise RuntimeError(
            f"adapter host {host!r} is not allowlisted. "
            f"Expected one of {sorted(ALLOWED_ADAPTER_HOSTS)}; "
            "set ENGINEERING_COUNCIL_ALLOW_ANY_HOST=1 to override deliberately."
        )


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    check_endpoint(url)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Provider error bodies echo request fragments, and this message is
        # persisted verbatim into council/<run>/events.jsonl by the caller.
        body = redact_secrets(exc.read().decode("utf-8", errors="replace"))[:1000]
        raise RuntimeError(f"adapter HTTP {exc.code}: {body}") from exc


def call_anthropic_adapter(prompt: str, timeout: int) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("ENGINEERING_COUNCIL_MODEL")
    if not key or not model:
        raise RuntimeError("ANTHROPIC_API_KEY and ENGINEERING_COUNCIL_MODEL are required for anthropic adapter")
    data = post_json(
        os.environ.get("ENGINEERING_COUNCIL_ANTHROPIC_URL", "https://api.anthropic.com/v1/messages"),
        {"x-api-key": key, "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01")},
        {
            "model": model,
            "max_tokens": int(os.environ.get("ENGINEERING_COUNCIL_MAX_TOKENS", "1600")),
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout,
    )
    parts = data.get("content", [])
    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict) and part.get("type") == "text")
    return extract_text_response(text)


def call_openai_adapter(prompt: str, timeout: int) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("ENGINEERING_COUNCIL_MODEL")
    if not key or not model:
        raise RuntimeError("OPENAI_API_KEY and ENGINEERING_COUNCIL_MODEL are required for openai adapter")
    base_url = os.environ.get("ENGINEERING_COUNCIL_OPENAI_URL", "https://api.openai.com/v1/chat/completions")
    data = post_json(
        base_url,
        {"Authorization": f"Bearer {key}"},
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a rigorous engineering council advisor. Return concise Markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": int(os.environ.get("ENGINEERING_COUNCIL_MAX_TOKENS", "1600")),
        },
        timeout,
    )
    return extract_text_response(data["choices"][0]["message"]["content"])


def call_live_adapter(adapter: str, payload: dict[str, Any], timeout: int) -> str:
    if adapter == "command":
        return call_command_adapter(payload, timeout)
    if adapter == "anthropic":
        return call_anthropic_adapter(payload["prompt"], timeout)
    if adapter == "openai":
        return call_openai_adapter(payload["prompt"], timeout)
    raise RuntimeError(f"unsupported live adapter: {adapter}")


def render_live_or_deterministic(
    *,
    mode: str,
    adapter: str,
    timeout: int,
    events: Path,
    payload: dict[str, Any],
    fallback: str,
) -> str:
    if mode != "live-model":
        return fallback
    try:
        result = call_live_adapter(adapter, payload, timeout)
        event(events, "live_adapter_success", {"kind": payload.get("kind"), "adapter": adapter})
        return result
    except Exception as exc:
        event(events, "live_adapter_failed", {"kind": payload.get("kind"), "adapter": adapter, "error": str(exc)})
        if payload.get("fallback_on_error"):
            return fallback
        raise


def ask(
    root: Path,
    question: str,
    contexts: list[str],
    run_id: str | None,
    mode: str = "deterministic-local",
    adapter: str = "command",
    fallback_on_error: bool = False,
    max_context_chars: int = 24000,
    timeout: int = 120,
    selected_roles: list[str] | None = None,
    quorum_min: int = 3,
) -> Path:
    run_id = run_id or slugify(question)[:48]
    base = engineering_root(root) / "council" / run_id
    events = base / "events.jsonl"
    files, withheld = context_files(contexts, root)
    snippets = context_snippets(root, files, max_context_chars)
    input_payload = {
        "question": question,
        "context": files,
        "context_withheld": withheld,
        "run_id": run_id,
        "created_at": now_iso(),
        "mode": mode,
        "adapter": adapter if mode == "live-model" else None,
        "max_context_chars": max_context_chars,
    }
    write_json(base / "input.json", input_payload)
    event(
        events, "input_recorded", {"run_id": run_id, "mode": mode, "adapter": adapter if mode == "live-model" else None}
    )
    if withheld:
        # Named, not merely counted: a silently dropped file reads as an advisor
        # ignoring evidence, and the user is the only one who can decide whether
        # it genuinely needed to go.
        event(events, "context_withheld", {"paths": withheld[:50], "count": len(withheld)})
        print(f"council: withheld {len(withheld)} credential-bearing or vendored file(s) from the prompt")

    advisor_dir = base / "advisor-drafts"
    anonymized_dir = base / "anonymized-drafts"
    peer_dir = base / "peer-reviews"
    role_defs = [(role, purpose) for role, purpose in ROLES if selected_roles is None or role in selected_roles]
    roles = [role for role, _ in role_defs]
    advisor_texts: list[str] = []
    anonymous_ids: list[str] = []

    for idx, (role, purpose) in enumerate(role_defs, 1):
        fallback = make_deterministic_advisor(role, purpose, question, files, run_id)
        prompt = render_advisor_prompt(role, purpose, question, snippets)
        draft = render_live_or_deterministic(
            mode=mode,
            adapter=adapter,
            timeout=timeout,
            events=events,
            payload={
                "kind": "advisor",
                "role": role,
                "question": question,
                "context": snippets,
                "prompt": prompt,
                "fallback_on_error": fallback_on_error,
            },
            fallback=fallback,
        )
        draft = with_front_matter(run_id, files, draft)
        advisor_path = advisor_dir / f"{role}.md"
        write_text(advisor_path, draft)
        advisor_texts.append(draft)
        anonymous_id = f"advisor-{idx}"
        anonymous_ids.append(anonymous_id)
        write_text(
            anonymized_dir / f"{anonymous_id}.md",
            make_anonymized(anonymous_id, str(advisor_path.relative_to(base)).replace("\\", "/"), draft),
        )
        event(events, "advisor_draft_written", {"role": role, "mode": mode})

    quorum = len(list(advisor_dir.glob("*.md"))) >= quorum_min
    anonymous_texts = [
        (anonymized_dir / f"{anonymous_id}.md").read_text(encoding="utf-8") for anonymous_id in anonymous_ids
    ]
    peer_texts: list[str] = []
    for role in roles:
        fallback = make_deterministic_peer_review(role, anonymous_ids, files, run_id)
        prompt = render_peer_prompt(role, anonymous_ids, anonymous_texts)
        review = render_live_or_deterministic(
            mode=mode,
            adapter=adapter,
            timeout=timeout,
            events=events,
            payload={
                "kind": "peer-review",
                "role": role,
                "question": question,
                "anonymous_ids": anonymous_ids,
                "prompt": prompt,
                "fallback_on_error": fallback_on_error,
            },
            fallback=fallback,
        )
        review = with_front_matter(run_id, files, review)
        write_text(peer_dir / f"{role}.md", review)
        peer_texts.append(review)
    event(events, "peer_reviews_written", {"count": len(roles), "mode": mode})

    fallback_synthesis = make_deterministic_synthesis(question, files, run_id, quorum)
    synthesis_prompt = render_synthesis_prompt(question, files, advisor_texts, peer_texts, quorum)
    synthesis = render_live_or_deterministic(
        mode=mode,
        adapter=adapter,
        timeout=timeout,
        events=events,
        payload={
            "kind": "synthesis",
            "role": "chairperson",
            "question": question,
            "prompt": synthesis_prompt,
            "fallback_on_error": fallback_on_error,
        },
        fallback=fallback_synthesis,
    )
    synthesis = with_front_matter(run_id, files, synthesis)
    write_text(base / "synthesis.md", synthesis)
    record_council_questions(root, run_id, question, synthesis, quorum)

    write_json(
        base / "council-report.json",
        {
            "run_id": run_id,
            "question": question,
            "status": "quorum-met" if quorum else "quorum-failed",
            "advisor_count": len(roles),
            "quorum_min": quorum_min,
            "context": files,
            "synthesis": str((base / "synthesis.md").relative_to(root)).replace("\\", "/"),
            "mode": mode,
            "adapter": adapter if mode == "live-model" else None,
        },
    )
    event(events, "synthesis_written", {"quorum": quorum, "mode": mode})
    return base


def record_council_questions(root: Path, run_id: str, question: str, synthesis: str, quorum: bool) -> None:
    """Push a council run's unresolved questions into the open-questions store.

    A council run used to be write-only: the ledger recorded that it happened
    and where its files were, but the question it was convened to answer, and
    any question it raised in turn, went nowhere a human would see again.
    """
    source = relpath(engineering_root(root) / "council" / run_id / "synthesis.md", root)
    entries: list[dict[str, Any]] = [
        {"question": item, "kind": "council", "source_artifact": source, "skill": "run-engineering-council"}
        for item in extract_open_questions(synthesis)
    ]
    if not quorum and question:
        # A failed quorum means the decision is still the human's to make.
        entries.append(
            {
                "question": f"Council run {run_id} did not reach quorum. Decide directly: {question}",
                "kind": "council",
                "source_artifact": source,
                "skill": "run-engineering-council",
            }
        )
    if entries:
        record_questions(root, entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ask_parser = sub.add_parser("ask")
    ask_parser.add_argument("--question", required=True)
    ask_parser.add_argument("--context", action="append", default=[])
    ask_parser.add_argument("--run-id")
    ask_parser.add_argument("--root", default=".")
    ask_parser.add_argument(
        "--mode",
        choices=["deterministic-local", "live-model"],
        default=os.environ.get("ENGINEERING_COUNCIL_MODE", "deterministic-local"),
    )
    ask_parser.add_argument(
        "--adapter",
        choices=["command", "anthropic", "openai"],
        default=os.environ.get("ENGINEERING_COUNCIL_ADAPTER", "command"),
    )
    ask_parser.add_argument(
        "--fallback-on-error", action="store_true", help="Use deterministic output when a live adapter fails"
    )
    ask_parser.add_argument(
        "--max-context-chars", type=int, default=int(os.environ.get("ENGINEERING_COUNCIL_MAX_CONTEXT_CHARS", "24000"))
    )
    ask_parser.add_argument(
        "--timeout", type=int, default=int(os.environ.get("ENGINEERING_COUNCIL_TIMEOUT_SECONDS", "120"))
    )
    ask_parser.add_argument("--role", action="append", choices=[role for role, _ in ROLES], dest="roles")
    ask_parser.add_argument(
        "--quorum-min", type=int, default=int(os.environ.get("ENGINEERING_COUNCIL_QUORUM_MIN", "3"))
    )
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    if args.command == "ask":
        path = ask(
            root,
            args.question,
            args.context,
            args.run_id,
            args.mode,
            args.adapter,
            args.fallback_on_error,
            args.max_context_chars,
            args.timeout,
            args.roles,
            args.quorum_min,
        )
        print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
