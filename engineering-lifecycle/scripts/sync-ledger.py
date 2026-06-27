#!/usr/bin/env python3
"""Build the normalized Engineering Lifecycle ledger and dashboard data."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from eng_common import engineering_root, now_iso, parse_front_matter, read_json, repo_root, write_json, write_text


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def artifact_record(path: Path, root: Path) -> dict:
    record = {
        "path": rel(path, root),
        "kind": path.suffix.lower().lstrip(".") or "file",
        "status": "unknown",
        "skill": None,
        "initiative_id": None,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
    }
    if path.suffix.lower() == ".md":
        fm, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        record.update(
            {
                "status": fm.get("status", "unknown"),
                "skill": fm.get("skill"),
                "initiative_id": fm.get("initiative_id"),
                "confidence": fm.get("confidence"),
            }
        )
    return record


def collect_ledger(root: Path) -> dict:
    base = engineering_root(root)
    base.mkdir(parents=True, exist_ok=True)
    artifacts = [
        artifact_record(path, root)
        for path in sorted(base.rglob("*"))
        if path.is_file()
        and "ledger" not in path.relative_to(base).parts
        and path.name not in {"dashboard-data.json", "project-dashboard.html"}
    ]
    action_items: list[dict] = []
    for path in sorted(base.rglob("*action-items*.json")):
        data = read_json(path, {})
        action_items.extend(data if isinstance(data, list) else data.get("action_items", []))
    hygiene = read_json(base / "hygiene" / "hygiene-report.json", {})
    council_runs = []
    council_root = base / "council"
    if council_root.exists():
        for run in sorted(p for p in council_root.iterdir() if p.is_dir()):
            council_runs.append(
                {
                    "run_id": run.name,
                    "input": rel(run / "input.json", root) if (run / "input.json").exists() else None,
                    "synthesis": rel(run / "synthesis.md", root) if (run / "synthesis.md").exists() else None,
                }
            )
    return {
        "generated_at": now_iso(),
        "workspace": rel(base, root),
        "artifacts": artifacts,
        "action_items": sorted(action_items, key=lambda item: item.get("id", "")),
        "hygiene": hygiene,
        "council_runs": council_runs,
        "summary": {
            "artifact_count": len(artifacts),
            "open_action_item_count": sum(1 for item in action_items if item.get("status") != "done"),
            "council_run_count": len(council_runs),
        },
    }


def dashboard_data(ledger: dict) -> dict:
    missing = []
    for required in ["profile", "lifecycle", "hygiene"]:
        if not any(f"/{required}/" in item["path"] or item["path"].endswith(f"/{required}.json") for item in ledger["artifacts"]):
            missing.append(required)
    return {
        "generated_at": ledger["generated_at"],
        "summary": ledger["summary"],
        "risks": ledger.get("hygiene", {}).get("risks", []),
        "missing_artifact_groups": missing,
        "open_action_items": [item for item in ledger["action_items"] if item.get("status") != "done"],
        "recent_artifacts": sorted(ledger["artifacts"], key=lambda item: item["path"])[:50],
    }


def render_dashboard(data: dict) -> str:
    rows = "\n".join(
        f"<li><code>{html.escape(item['path'])}</code> - {html.escape(str(item.get('status', 'unknown')))}</li>"
        for item in data["recent_artifacts"]
    )
    actions = "\n".join(
        f"<li>{html.escape(item.get('title', 'Untitled'))} <small>{html.escape(item.get('source', ''))}</small></li>"
        for item in data["open_action_items"]
    )
    missing = ", ".join(html.escape(x) for x in data["missing_artifact_groups"]) or "None detected"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Engineering Lifecycle Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #1f2937; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }}
    .panel {{ border: 1px solid #d1d5db; border-radius: 6px; padding: 1rem; }}
  </style>
</head>
<body>
  <h1>Engineering Lifecycle Dashboard</h1>
  <p>Generated at {html.escape(data['generated_at'])}</p>
  <div class="grid">
    <section class="panel"><h2>Artifacts</h2><p>{data['summary']['artifact_count']}</p></section>
    <section class="panel"><h2>Open Actions</h2><p>{data['summary']['open_action_item_count']}</p></section>
    <section class="panel"><h2>Council Runs</h2><p>{data['summary']['council_run_count']}</p></section>
  </div>
  <h2>Missing Groups</h2><p>{missing}</p>
  <h2>Open Action Items</h2><ul>{actions or '<li>None</li>'}</ul>
  <h2>Recent Artifacts</h2><ul>{rows or '<li>None</li>'}</ul>
</body>
</html>
"""


def sync(root: Path) -> dict:
    base = engineering_root(root)
    ledger = collect_ledger(root)
    write_json(base / "ledger" / "ledger.json", ledger)
    log_path = base / "ledger" / "ledger-log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"event": "ledger_synced", "at": ledger["generated_at"], "summary": ledger["summary"]}, sort_keys=True) + "\n")
    data = dashboard_data(ledger)
    write_json(base / "dashboards" / "dashboard-data.json", data)
    write_text(base / "dashboards" / "project-dashboard.html", render_dashboard(data))
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    ledger = sync(root)
    print(f"synced ledger with {ledger['summary']['artifact_count']} artifact(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
