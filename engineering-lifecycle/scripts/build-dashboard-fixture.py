#!/usr/bin/env python3
"""Generate a populated workspace so the dashboard can be tested in a browser.

`project-dashboard.html` is the only browser-facing thing the plugin produces and
it had no rendering verification at all. Testing it needs a workspace with enough
variety to exercise the filters and the sort, which this builds deterministically.

Deterministic on purpose: a fixture with changing timestamps produces a dashboard
whose "stale" badges flip between runs, and a test that depends on the calendar
fails on a Monday for no reason.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from eng_common import emit_json, engineering_root, relpath, write_json, write_text

PLUGIN = Path(__file__).resolve().parents[1]

ARTIFACTS = [
    ("initiatives/billing-exports/requirements/prd.md", "create-prd", "approved"),
    ("initiatives/billing-exports/testing/test-strategy.md", "create-test-strategy", "draft"),
    ("initiatives/billing-exports/review/change-review.md", "review-change", "reviewed"),
    ("initiatives/push-notifications/requirements/prd.md", "create-prd", "draft"),
    ("decisions/ADR-0001-queue-over-cron.md", "create-technical-design-document", "accepted"),
]


def front_matter(initiative: str, skill: str, status: str) -> str:
    return (
        "---\n"
        f"initiative_id: {initiative}\n"
        f"skill: {skill}\n"
        "created_at: 2026-01-01T00:00:00+00:00\n"
        f"status: {status}\n"
        "confidence: medium\n"
        "source_artifacts:\n  - none\n"
        "---\n\n"
    )


def build(root: Path) -> dict:
    base = engineering_root(root)
    for directory in ("ledger", "questions", "dashboards", "hygiene", "decisions", "council/cli-run"):
        (base / directory).mkdir(parents=True, exist_ok=True)

    for relative, skill, status in ARTIFACTS:
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        initiative = relative.split("/")[1] if relative.startswith("initiatives/") else "billing-exports"
        write_text(path, front_matter(initiative, skill, status) + f"# {path.stem}\n\nFixture content.\n")

    write_json(
        base / "ledger" / "action-items.json",
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "action_items": [
                {
                    "id": "ai-001",
                    "title": "Add a retention policy to the export bucket",
                    "status": "open",
                    "source": "initiatives/billing-exports/requirements/prd.md",
                },
                {
                    "id": "ai-002",
                    "title": "Confirm the CSV column order with finance",
                    "status": "open",
                    "source": "initiatives/billing-exports/requirements/prd.md",
                },
                {"id": "ai-003", "title": "Wire the export button", "status": "done", "source": "prd.md"},
            ],
        },
    )
    write_json(
        base / "ledger" / "human-tasks.json",
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "human_tasks": [
                {
                    "id": "ht-001",
                    "task": "Confirm the production rollout window",
                    "status": "open",
                    "reason": "The assistant cannot verify this from repository evidence.",
                },
            ],
        },
    )
    write_json(
        base / "questions" / "open-questions.json",
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "open_questions": [
                {
                    "id": "q-fixture00001",
                    "question": "Which region hosts the export bucket?",
                    "kind": "artifact",
                    "status": "open",
                    "asked_at": "2026-01-01T00:00:00+00:00",
                    "source_artifact": "initiatives/billing-exports/requirements/prd.md",
                },
                {
                    "id": "q-fixture00002",
                    "question": "Is CSV acceptable to auditors?",
                    "kind": "clarification",
                    "status": "open",
                    "asked_at": "2026-01-01T00:00:00+00:00",
                    "options": ["Yes", "No", "Ask them"],
                },
                {
                    "id": "q-fixture00003",
                    "question": "How long is a session token valid?",
                    "kind": "council",
                    "status": "answered",
                    "asked_at": "2026-01-01T00:00:00+00:00",
                    "answer": "Thirty minutes.",
                },
            ],
        },
    )
    write_json(
        base / "hygiene" / "hygiene-report.json",
        {
            "status": "attention",
            "risks": ["Two environment variables are referenced but absent from .env.example."],
            "new_env_vars": [{"name": "EXPORT_BUCKET"}, {"name": "EXPORT_SIGNING_KEY"}],
            "gitignore_candidates": [],
        },
    )
    write_json(
        base / "council" / "cli-run" / "input.json",
        {
            "run_id": "cli-run",
            "question": "Queue or cron for exports?",
            "context": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "mode": "deterministic",
        },
    )
    write_text(base / "council" / "cli-run" / "synthesis.md", "# Council Synthesis\n\nRecommendation: use a queue.\n")

    subprocess.run(
        [sys.executable, "-B", str(PLUGIN / "scripts" / "sync-ledger.py"), "--root", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "root": str(root),
        "dashboard": relpath(base / "dashboards" / "project-dashboard.html", root),
        "data": relpath(base / "dashboards" / "dashboard-data.json", root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Directory to build the fixture workspace in")
    args = parser.parse_args()
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # `repo_root` walks up looking for `.git` or `.claude-plugin/plugin.json`, so a
    # fixture built inside the plugin tree would otherwise resolve to the plugin
    # itself and write the dashboard there. This marker stops the walk at the
    # fixture, which is exactly the repo boundary the fixture stands in for.
    (root / ".git").mkdir(exist_ok=True)
    emit_json(build(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
