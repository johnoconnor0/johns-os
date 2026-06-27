#!/usr/bin/env python3
"""Deterministic local Engineering Council runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eng_common import engineering_root, now_iso, repo_root, slugify, write_json, write_text


ROLES = [
    ("contrarian", "Challenge weak assumptions and identify downside risk."),
    ("first-principles", "Reduce the decision to constraints, invariants, and necessary tradeoffs."),
    ("expansionist", "Look for broader opportunity, extensibility, and optionality."),
    ("outsider", "Apply an external, cross-domain perspective."),
    ("executor", "Focus on implementation cost, sequencing, reversibility, and delivery risk."),
]


def event(path: Path, name: str, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"at": now_iso(), "event": name, "payload": payload}, sort_keys=True) + "\n")


def context_files(contexts: list[str], root: Path) -> list[str]:
    files: list[str] = []
    for ctx in contexts:
        path = Path(ctx)
        full = path if path.is_absolute() else root / path
        if full.is_dir():
            files.extend(str(p.relative_to(root)).replace("\\", "/") for p in sorted(full.rglob("*")) if p.is_file())
        elif full.exists():
            files.append(str(full.relative_to(root)).replace("\\", "/"))
    return sorted(set(files))


def source_block(files: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in files) if files else "  - none"


def make_advisor(role: str, purpose: str, question: str, files: list[str], run_id: str) -> str:
    evidence = "\n".join(f"- `{item}`" for item in files) or "- No context files supplied."
    return f"""---
initiative_id: council-{run_id}
skill: run-engineering-council
created_at: {now_iso()}
status: draft
confidence: medium
source_artifacts:
{source_block(files)}
---

# {role.title()} Advisor Draft

## Position

Use the {role} lens to answer: {question}

## Evidence Reviewed

{evidence}

## Analysis

{purpose} This deterministic draft is a local placeholder for a future live model adapter. It must be replaced or reviewed by a human/LLM before treating the council as authoritative.

## Recommendation

Proceed only if the implementation plan records assumptions, rollback points, and unresolved evidence gaps.
"""


def make_peer_review(role: str, peers: list[str], files: list[str], run_id: str) -> str:
    peer_list = "\n".join(f"- {peer}" for peer in peers if peer != role)
    return f"""---
initiative_id: council-{run_id}
skill: run-engineering-council
created_at: {now_iso()}
status: draft
confidence: medium
source_artifacts:
{source_block(files)}
---

# {role.title()} Peer Review

## Peer Drafts Reviewed

{peer_list}

## Review

No deterministic peer found a blocking contradiction. Preserve any dissent from advisor drafts in the chair synthesis.
"""


def make_synthesis(question: str, files: list[str], run_id: str, quorum: bool) -> str:
    evidence = "\n".join(f"- `{item}`" for item in files) or "- No context files supplied."
    status = "quorum-met" if quorum else "quorum-failed"
    return f"""---
initiative_id: council-{run_id}
skill: run-engineering-council
created_at: {now_iso()}
status: draft
confidence: medium
source_artifacts:
{source_block(files)}
---

# Engineering Council Synthesis

## Question

{question}

## Council Status

{status}

## Evidence

{evidence}

## Recommendation

Use the executor recommendation as the default unless the contrarian draft identifies an unreduced safety, security, migration, or reversibility risk.

## Dissent

Deterministic mode preserves role-specific drafts but cannot independently verify their quality. Treat unresolved disagreement as an action item.

## Next Actions

- [ ] Review advisor drafts and replace placeholder analysis with evidence-bound judgment where needed.
- [ ] Record the accepted decision as an ADR if the choice changes architecture or operations.
"""


def ask(root: Path, question: str, contexts: list[str], run_id: str | None) -> Path:
    run_id = run_id or slugify(question)[:48]
    base = engineering_root(root) / "council" / run_id
    events = base / "events.jsonl"
    files = context_files(contexts, root)
    input_payload = {"question": question, "context": files, "run_id": run_id, "created_at": now_iso(), "mode": "deterministic-local"}
    write_json(base / "input.json", input_payload)
    event(events, "input_recorded", {"run_id": run_id})
    advisor_dir = base / "advisor-drafts"
    peer_dir = base / "peer-reviews"
    roles = [role for role, _ in ROLES]
    for role, purpose in ROLES:
        write_text(advisor_dir / f"{role}.md", make_advisor(role, purpose, question, files, run_id))
        event(events, "advisor_draft_written", {"role": role})
    quorum = len(list(advisor_dir.glob("*.md"))) >= 3
    for role in roles:
        write_text(peer_dir / f"{role}.md", make_peer_review(role, roles, files, run_id))
    event(events, "peer_reviews_written", {"count": len(roles)})
    write_text(base / "synthesis.md", make_synthesis(question, files, run_id, quorum))
    write_json(
        base / "council-report.json",
        {
            "run_id": run_id,
            "question": question,
            "status": "quorum-met" if quorum else "quorum-failed",
            "advisor_count": len(roles),
            "context": files,
            "synthesis": str((base / "synthesis.md").relative_to(root)).replace("\\", "/"),
        },
    )
    event(events, "synthesis_written", {"quorum": quorum})
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ask_parser = sub.add_parser("ask")
    ask_parser.add_argument("--question", required=True)
    ask_parser.add_argument("--context", action="append", default=[])
    ask_parser.add_argument("--run-id")
    ask_parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    if args.command == "ask":
        path = ask(root, args.question, args.context, args.run_id)
        print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
