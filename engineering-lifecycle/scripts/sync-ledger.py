#!/usr/bin/env python3
"""Build the normalized Engineering Lifecycle ledger and dashboard data."""

from __future__ import annotations

import argparse
import html
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from eng_common import (
    docs_root,
    engineering_root,
    now_iso,
    parse_front_matter,
    read_json,
    repo_root,
    write_json,
    write_text,
)


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


# Artifacts older than this are flagged "stale" so the dashboard can surface
# state that may no longer reflect reality.
STALE_AFTER_DAYS = 14
_UNREADABLE = object()


def _validation_status(path: Path) -> str:
    """Derive valid/invalid/error from a generated validation report's contents."""
    data = read_json(path, _UNREADABLE)
    if data is _UNREADABLE:
        return "error"
    if isinstance(data, dict):
        if data.get("valid") is True or data.get("ok") is True:
            return "valid"
        if data.get("valid") is False or data.get("ok") is False:
            return "invalid"
        for key in ("errors", "issues", "violations"):
            value = data.get(key)
            if isinstance(value, list):
                return "invalid" if value else "valid"
        status = data.get("status")
        if isinstance(status, str) and status.strip():
            return status.strip()
    return "generated"


def classify_status(path: Path, root: Path) -> str:
    """Role/content-aware status for non-Markdown artifacts (never 'unknown' unless unreadable)."""
    suffix = path.suffix.lower()
    lower = "/" + rel(path, root).lower()
    if suffix == ".jsonl":
        return "log"
    if suffix == ".json":
        if "/reports/validation/" in lower or "/validation/" in lower:
            return _validation_status(path)
        if "/council/" in lower:
            return "council"
        if "/reports/" in lower:
            return "generated"
        if any(seg in lower for seg in ("/context/", "/profile/", "/lifecycle/", "/decisions/", "/handoffs/")):
            return "current"
        return "generated"
    return "generated"


def freshness(mtime: float, now: float | None = None) -> str:
    now = time.time() if now is None else now
    return "stale" if (now - mtime) > STALE_AFTER_DAYS * 86400 else "current"


def artifact_record(path: Path, root: Path) -> dict:
    stat = path.stat()
    record = {
        "path": rel(path, root),
        "kind": path.suffix.lower().lstrip(".") or "file",
        "status": "unknown",
        "freshness": freshness(stat.st_mtime),
        "skill": None,
        "initiative_id": None,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, UTC).replace(microsecond=0).isoformat(),
    }
    if path.suffix.lower() == ".md":
        fm, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        record.update(
            {
                "status": fm.get("status") or "draft",
                "skill": fm.get("skill"),
                "initiative_id": fm.get("initiative_id"),
                "confidence": fm.get("confidence"),
            }
        )
    else:
        record["status"] = classify_status(path, root)
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
    # The narrative deliverables live in a second tree. Index them too, or the
    # dashboard shows only machine state and none of the documents anyone reads.
    docs = docs_root(root)
    if docs.is_dir():
        artifacts.extend(artifact_record(path, root) for path in sorted(docs.rglob("*")) if path.is_file())
    action_items: list[dict] = []
    for path in sorted(base.rglob("*action-items*.json")):
        data = read_json(path, {})
        action_items.extend(data if isinstance(data, list) else data.get("action_items", []))
    # Human tasks are the "human" half of AI + human tracking. The schema/template
    # existed but nothing collected them until now.
    human_tasks: list[dict] = []
    for path in sorted(base.rglob("*human-tasks*.json")):
        data = read_json(path, {})
        human_tasks.extend(data if isinstance(data, list) else data.get("human_tasks", []))
    # Questions the assistant needs a human to answer. Collected here so they
    # appear on the dashboard instead of only in the file that raised them.
    questions = read_json(base / "questions" / "open-questions.json", {})
    open_questions = questions.get("open_questions", []) if isinstance(questions, dict) else []
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
        "human_tasks": sorted(human_tasks, key=lambda item: item.get("id", "")),
        "open_questions": open_questions,
        "hygiene": hygiene,
        "council_runs": council_runs,
        "summary": {
            "artifact_count": len(artifacts),
            "open_action_item_count": sum(1 for item in action_items if item.get("status") != "done"),
            "open_human_task_count": sum(1 for item in human_tasks if item.get("status") != "done"),
            "open_question_count": sum(1 for item in open_questions if item.get("status") == "open"),
            "council_run_count": len(council_runs),
        },
    }


def dashboard_data(ledger: dict) -> dict:
    missing = []
    for required in ["profile", "lifecycle", "hygiene"]:
        if not any(
            f"/{required}/" in item["path"] or item["path"].endswith(f"/{required}.json")
            for item in ledger["artifacts"]
        ):
            missing.append(required)
    hygiene = ledger.get("hygiene") or {}
    risks = hygiene.get("risks", []) if isinstance(hygiene, dict) else []
    return {
        "generated_at": ledger["generated_at"],
        "summary": ledger["summary"],
        "risks": risks,
        "hygiene": {
            "status": hygiene.get("status") if isinstance(hygiene, dict) else None,
            "risk_count": len(risks),
            "new_env_vars": len(hygiene.get("new_env_vars", []) or []) if isinstance(hygiene, dict) else 0,
            "gitignore_candidates": len(hygiene.get("gitignore_candidates", []) or [])
            if isinstance(hygiene, dict)
            else 0,
        },
        "missing_artifact_groups": missing,
        "open_action_items": [item for item in ledger["action_items"] if item.get("status") != "done"],
        "open_human_tasks": [item for item in ledger.get("human_tasks", []) if item.get("status") != "done"],
        "open_questions": [item for item in ledger.get("open_questions", []) if item.get("status") == "open"],
        "council_runs": ledger.get("council_runs", []),
        "recent_artifacts": sorted(ledger["artifacts"], key=lambda item: item["path"])[:50],
    }


# Map a status keyword to a visual tone (CSS badge class suffix).
_STATUS_TONE = {
    "valid": "ok",
    "current": "ok",
    "done": "ok",
    "complete": "ok",
    "completed": "ok",
    "approved": "ok",
    "invalid": "bad",
    "error": "bad",
    "failed": "bad",
    "blocked": "bad",
    "stale": "warn",
    "warning": "warn",
    "pending": "warn",
    "draft": "info",
    "in-progress": "info",
    "in_progress": "info",
    "council": "info",
    "review": "info",
    "generated": "muted",
    "log": "muted",
    "unknown": "muted",
}

# Guidance shown next to each missing artifact group.
_GROUP_HELP = {
    "profile": ("No product/system profile captured.", "profile-product-system"),
    "lifecycle": ("Lifecycle position not mapped.", "map-product-lifecycle"),
    "hygiene": ("No repository hygiene report.", "update-repo-hygiene"),
}


def _tone(status) -> str:
    return _STATUS_TONE.get(str(status or "").lower(), "muted")


def _rel_link(path: str) -> str:
    """Convert a repo-relative artifact path to one relative to the dashboards/ dir.

    The dashboard sits at `.project/.engineering/dashboards/`, so workspace paths
    climb one level and docs paths climb three.
    """
    p = str(path).replace("\\", "/")
    if p.startswith(".project/.engineering/"):
        return "../" + p[len(".project/.engineering/") :]
    if p.startswith(".project/"):
        return "../../" + p[len(".project/") :]
    return p


def _chip(label, value, tone: str = "muted") -> str:
    e = html.escape
    return (
        '<div class="chip chip-'
        + tone
        + '"><div class="chip-val">'
        + e(str(value))
        + '</div><div class="chip-lbl">'
        + e(str(label))
        + "</div></div>"
    )


def _risk_item(risk) -> str:
    e = html.escape
    if isinstance(risk, dict):
        sev = str(risk.get("severity") or risk.get("level") or "")
        title = str(risk.get("title") or risk.get("risk") or risk.get("description") or risk.get("summary") or "")
        if not title:
            title = json.dumps(risk, sort_keys=True)
        tone = {"high": "bad", "critical": "bad", "medium": "warn", "low": "info"}.get(sev.lower(), "muted")
        badge = ('<span class="badge badge-' + tone + '">' + e(sev) + "</span> ") if sev else ""
        return "<li>" + badge + e(title) + "</li>"
    return "<li>" + e(str(risk)) + "</li>"


def _missing_item(group) -> str:
    e = html.escape
    help_text, skill = _GROUP_HELP.get(group, ("Expected artifact group not found.", None))
    tip = (" Run the <code>" + e(skill) + "</code> skill.") if skill else ""
    return "<li><strong>" + e(str(group)) + "</strong> &mdash; " + e(help_text) + tip + "</li>"


def _action_item(item) -> str:
    e = html.escape
    title = e(str(item.get("title", "Untitled")))
    source = str(item.get("source", ""))
    src = (' <small class="sub">' + e(source) + "</small>") if source else ""
    status = item.get("status")
    badge = ('<span class="badge badge-' + _tone(status) + '">' + e(str(status)) + "</span> ") if status else ""
    return "<li>" + badge + title + src + "</li>"


def _human_task_item(item) -> str:
    e = html.escape
    title = e(str(item.get("task") or item.get("title", "Untitled")))
    reason = str(item.get("reason", ""))
    sub = (' <small class="sub">' + e(reason) + "</small>") if reason else ""
    status = item.get("status")
    badge = ('<span class="badge badge-' + _tone(status) + '">' + e(str(status)) + "</span> ") if status else ""
    return "<li>" + badge + title + sub + "</li>"


def _question_item(item) -> str:
    e = html.escape
    question = e(str(item.get("question", "Untitled")))
    kind = str(item.get("kind", ""))
    source = str(item.get("source_artifact") or "")
    meta = " &middot; ".join(part for part in (e(kind) if kind else "", e(source) if source else "") if part)
    sub = (' <small class="sub">' + meta + "</small>") if meta else ""
    options = item.get("options") or []
    choices = (' <small class="sub">options: ' + e(", ".join(str(o) for o in options)) + "</small>") if options else ""
    return "<li>" + question + sub + choices + "</li>"


def _council_item(run) -> str:
    e = html.escape
    rid = e(str(run.get("run_id", "")))
    links = []
    if run.get("input"):
        links.append('<a href="' + e(_rel_link(run["input"])) + '">input</a>')
    if run.get("synthesis"):
        links.append('<a href="' + e(_rel_link(run["synthesis"])) + '">synthesis</a>')
    tail = (" &middot; " + " &middot; ".join(links)) if links else ""
    return "<li><strong>" + rid + "</strong>" + tail + "</li>"


def _artifact_row(item) -> str:
    e = html.escape
    path = str(item.get("path", ""))
    kind = str(item.get("kind", ""))
    status = str(item.get("status", "unknown"))
    fresh = str(item.get("freshness", ""))
    skill = str(item.get("skill") or "")
    initiative = str(item.get("initiative_id") or "")
    updated = str(item.get("updated_at", ""))
    fresh_tone = "warn" if fresh == "stale" else "muted"
    return (
        '<tr data-path="'
        + e(path)
        + '" data-kind="'
        + e(kind)
        + '" data-status="'
        + e(status)
        + '" data-fresh="'
        + e(fresh)
        + '">'
        '<td><a href="' + e(_rel_link(path)) + '"><code>' + e(path) + "</code></a></td>"
        "<td>" + e(kind) + "</td>"
        '<td><span class="badge badge-' + _tone(status) + '">' + e(status) + "</span></td>"
        '<td><span class="badge badge-' + fresh_tone + '">' + e(fresh) + "</span></td>"
        "<td>" + e(skill) + "</td>"
        "<td>" + e(initiative) + "</td>"
        "<td>" + e(updated) + "</td>"
        "</tr>"
    )


_CSS = """
:root{--bg:#fff;--fg:#1f2937;--muted:#6b7280;--border:#e5e7eb;--card:#f9fafb;--accent:#2563eb;
--ok:#16a34a;--okbg:#dcfce7;--bad:#dc2626;--badbg:#fee2e2;--warn:#b45309;--warnbg:#fef3c7;
--info:#1d4ed8;--infobg:#dbeafe;--mutedbg:#f3f4f6}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--fg:#e2e8f0;--muted:#94a3b8;--border:#1e293b;
--card:#111827;--okbg:#064e3b;--badbg:#7f1d1d;--warnbg:#78350f;--infobg:#1e3a8a;--mutedbg:#1e293b}}
*{box-sizing:border-box}
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:var(--bg);color:var(--fg)}
.wrap{max-width:1100px;margin:0 auto;padding:1.5rem}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:.75rem;margin-bottom:.5rem}
h1{font-size:1.4rem;margin:0}
.sub{color:var(--muted);font-size:.85rem}
.chips{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.75rem;margin:1rem 0}
.chip{border:1px solid var(--border);border-radius:10px;padding:.75rem;background:var(--card)}
.chip-val{font-size:1.6rem;font-weight:700}
.chip-lbl{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.chip-warn .chip-val{color:var(--warn)}.chip-bad .chip-val{color:var(--bad)}.chip-ok .chip-val{color:var(--ok)}
section.panel{border:1px solid var(--border);border-radius:10px;padding:1rem 1.25rem;margin:1rem 0;background:var(--card)}
section.panel h2{font-size:1rem;margin:0 0 .5rem}
ul.clean{list-style:none;padding:0;margin:0}
ul.clean li{padding:.3rem 0;border-bottom:1px solid var(--border)}
ul.clean li:last-child{border-bottom:0}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:999px;font-size:.72rem;font-weight:600}
.badge-ok{background:var(--okbg);color:var(--ok)}.badge-bad{background:var(--badbg);color:var(--bad)}
.badge-warn{background:var(--warnbg);color:var(--warn)}.badge-info{background:var(--infobg);color:var(--info)}
.badge-muted{background:var(--mutedbg);color:var(--muted)}
.toolbar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-bottom:.75rem}
.fgroup{display:flex;gap:.35rem;flex-wrap:wrap}
input#search{flex:1;min-width:180px;padding:.45rem .6rem;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--fg)}
.filter{border:1px solid var(--border);background:var(--bg);color:var(--fg);border-radius:999px;padding:.2rem .6rem;font-size:.72rem;cursor:pointer}
.filter.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:.45rem .5rem;border-bottom:1px solid var(--border);vertical-align:top}
th{position:sticky;top:0;background:var(--card);cursor:pointer;user-select:none;white-space:nowrap}
td code{background:var(--mutedbg);padding:.05rem .3rem;border-radius:4px;word-break:break-all}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.empty{color:var(--muted);font-style:italic}
@media(max-width:640px){.wrap{padding:1rem}th:nth-child(5),td:nth-child(5),th:nth-child(6),td:nth-child(6){display:none}}
"""

_JS = """
(function(){
  var table=document.getElementById('artifacts');
  if(!table||!table.tBodies.length)return;
  var tbody=table.tBodies[0];
  var rows=Array.prototype.slice.call(tbody.rows);
  var search=document.getElementById('search');
  var active={status:null,kind:null};
  function apply(){
    var q=(search&&search.value||'').toLowerCase();
    rows.forEach(function(r){
      if(!r.getAttribute('data-path'))return;
      var okText=!q||r.getAttribute('data-path').toLowerCase().indexOf(q)!==-1;
      var okStatus=!active.status||r.getAttribute('data-status')===active.status;
      var okKind=!active.kind||r.getAttribute('data-kind')===active.kind;
      r.style.display=(okText&&okStatus&&okKind)?'':'none';
    });
  }
  if(search)search.addEventListener('input',apply);
  Array.prototype.forEach.call(document.querySelectorAll('.filter'),function(btn){
    btn.addEventListener('click',function(){
      var dim=btn.getAttribute('data-dim'),val=btn.getAttribute('data-val');
      active[dim]=(active[dim]===val)?null:val;
      Array.prototype.forEach.call(document.querySelectorAll('.filter[data-dim="'+dim+'"]'),function(b){
        b.classList.toggle('on',b.getAttribute('data-val')===active[dim]);
      });
      apply();
    });
  });
  var dir={};
  Array.prototype.forEach.call(table.tHead.rows[0].cells,function(th,i){
    th.addEventListener('click',function(){
      dir[i]=!dir[i];
      rows.slice().sort(function(a,b){
        var x=(a.cells[i]?a.cells[i].innerText:'').trim().toLowerCase();
        var y=(b.cells[i]?b.cells[i].innerText:'').trim().toLowerCase();
        return (x<y?-1:x>y?1:0)*(dir[i]?1:-1);
      }).forEach(function(r){tbody.appendChild(r);});
    });
  });
})();
"""


def render_dashboard(data: dict) -> str:
    e = html.escape
    arts = data.get("recent_artifacts", [])
    risks = data.get("risks", [])
    missing = data.get("missing_artifact_groups", [])
    actions = data.get("open_action_items", [])
    human = data.get("open_human_tasks", [])
    questions = data.get("open_questions", [])
    councils = data.get("council_runs", [])
    summary = data.get("summary", {})
    stale_count = sum(1 for a in arts if a.get("freshness") == "stale")
    statuses = sorted({str(a.get("status", "unknown")) for a in arts})
    kinds = sorted({str(a.get("kind", "")) for a in arts if a.get("kind")})

    chips = "".join(
        [
            _chip("Artifacts", summary.get("artifact_count", len(arts))),
            _chip("Open actions", summary.get("open_action_item_count", len(actions)), "warn" if actions else "muted"),
            _chip("Human tasks", summary.get("open_human_task_count", len(human)), "warn" if human else "muted"),
            _chip(
                "Open questions",
                summary.get("open_question_count", len(questions)),
                "warn" if questions else "muted",
            ),
            _chip("Council runs", summary.get("council_run_count", len(councils))),
            _chip("Risks", len(risks), "bad" if risks else "muted"),
            _chip("Missing groups", len(missing), "warn" if missing else "muted"),
            _chip("Stale", stale_count, "warn" if stale_count else "muted"),
        ]
    )
    risks_html = "".join(_risk_item(r) for r in risks) or '<li class="empty">No risks recorded.</li>'
    missing_html = (
        "".join(_missing_item(g) for g in missing) or '<li class="empty">All expected artifact groups present.</li>'
    )
    actions_html = "".join(_action_item(a) for a in actions) or '<li class="empty">No open action items.</li>'
    human_html = "".join(_human_task_item(h) for h in human) or '<li class="empty">No open human tasks.</li>'
    questions_html = (
        "".join(_question_item(q) for q in questions) or '<li class="empty">No questions awaiting an answer.</li>'
    )
    council_html = "".join(_council_item(c) for c in councils) or '<li class="empty">No council runs.</li>'
    rows = "".join(_artifact_row(a) for a in arts) or '<tr><td colspan="7" class="empty">No artifacts.</td></tr>'
    status_filters = "".join(
        '<button class="filter" data-dim="status" data-val="' + e(s) + '">' + e(s) + "</button>" for s in statuses
    )
    kind_filters = "".join(
        '<button class="filter" data-dim="kind" data-val="' + e(k) + '">' + e(k) + "</button>" for k in kinds
    )
    stale_badge = (
        ' &middot; <span class="badge badge-warn">' + str(stale_count) + " stale</span>" if stale_count else ""
    )

    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Engineering Lifecycle Dashboard</title>\n<style>" + _CSS + "</style>\n</head>\n<body>\n"
        '<div class="wrap">\n'
        "<header><h1>Engineering Lifecycle Dashboard</h1>"
        '<span class="sub">Generated ' + e(str(data.get("generated_at", ""))) + stale_badge + "</span></header>\n"
        '<div class="chips">' + chips + "</div>\n"
        '<section class="panel"><h2>Risks</h2><ul class="clean">' + risks_html + "</ul></section>\n"
        '<section class="panel"><h2>Missing artifact groups</h2><ul class="clean">' + missing_html + "</ul></section>\n"
        '<section class="panel"><h2>Open action items</h2><ul class="clean">' + actions_html + "</ul></section>\n"
        '<section class="panel"><h2>Open human tasks</h2><ul class="clean">' + human_html + "</ul></section>\n"
        '<section class="panel"><h2>Open questions</h2><ul class="clean">' + questions_html + "</ul></section>\n"
        '<section class="panel"><h2>Council runs</h2><ul class="clean">' + council_html + "</ul></section>\n"
        '<section class="panel"><h2>Recent artifacts</h2>'
        '<div class="toolbar"><input id="search" type="search" placeholder="Filter by path…" aria-label="Filter artifacts by path">'
        '<span class="fgroup">' + status_filters + '</span><span class="fgroup">' + kind_filters + "</span></div>"
        '<div class="tablewrap"><table id="artifacts"><thead><tr>'
        "<th>Path</th><th>Kind</th><th>Status</th><th>Freshness</th><th>Skill</th><th>Initiative</th><th>Updated</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table></div></section>\n"
        "</div>\n<script>" + _JS + "</script>\n</body>\n</html>\n"
    )


def sync(root: Path) -> dict:
    base = engineering_root(root)
    ledger = collect_ledger(root)
    write_json(base / "ledger" / "ledger.json", ledger)
    log_path = base / "ledger" / "ledger-log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            json.dumps(
                {"event": "ledger_synced", "at": ledger["generated_at"], "summary": ledger["summary"]}, sort_keys=True
            )
            + "\n"
        )
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
