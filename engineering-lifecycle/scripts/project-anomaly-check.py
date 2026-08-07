#!/usr/bin/env python3
"""Find the mechanically detectable things wrong inside a `.project` workspace.

The ask behind this was "force the AI to surface every time something in a .project
folder happens that shouldn't, looks funny, or isn't functioning optimally". The
first third of that is achievable and this is it; the rest is judgement, and
`references/issue-surfacing-policy.md` is honest about the difference.

The point of moving it into a script is not speed. It is that a rule here runs
whether or not anyone remembered to look, so the model's diligence stops being
load-bearing for the half of the problem that never needed it.

Shaped like `anti-slop-check.py`: a rules table, findings carrying paths, `--hook`
silence when clean, and a report under `reports/validation/`. Same trade, too -
only what can be established by inspection. A rule that guesses produces noise, and
noise gets ignored.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from eng_common import (
    REQUIRED_FRONT_MATTER,
    docs_root,
    emit_json,
    engineering_root,
    now_iso,
    parse_front_matter,
    read_json_safe,
    relpath,
    repo_root,
    resolve_cli_root,
    workspace_exists,
    write_json,
)

STALE_DAYS = 45
UNANSWERED_QUESTION_DAYS = 14

_SECRETISH = re.compile(r"(?i)(token|secret|password|api[_-]?key|credential|bearer|private[_-]?key)")
_CHECKBOX_OPEN = re.compile(r"^\s*[-*]\s+\[\s\]\s+(.+)$", re.M)


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    path: str = ""
    evidence: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    title: str
    check: Callable[[Path], list[Finding]] = field(repr=False)


def _iter_json(root: Path) -> Iterable[Path]:
    base = engineering_root(root)
    if base.is_dir():
        yield from sorted(base.rglob("*.json"))


def _iter_markdown(root: Path) -> Iterable[Path]:
    for base in (engineering_root(root), docs_root(root)):
        if base.is_dir():
            yield from sorted(base.rglob("*.md"))


def _age_days(path: Path) -> float:
    try:
        return (datetime.now(UTC) - datetime.fromtimestamp(path.stat().st_mtime, UTC)).total_seconds() / 86400
    except OSError:
        return 0.0


def _parse_iso(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


# --- readability -----------------------------------------------------------


def check_unreadable(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    base = engineering_root(root)
    if not base.is_dir():
        return findings
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = relpath(path, root)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size == 0:
            findings.append(Finding("empty-artifact", "medium", "Generated artifact is empty.", rel))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(Finding("non-utf8-artifact", "medium", "Artifact is not valid UTF-8.", rel))
            continue
        except OSError:
            continue
        if path.suffix == ".json":
            try:
                json.loads(text)
            except ValueError as exc:
                findings.append(
                    Finding("malformed-json", "high", "Generated JSON cannot be parsed.", rel, str(exc)[:160])
                )
    return findings


# --- workspace shape -------------------------------------------------------


def check_workspace_dir_drift(root: Path) -> list[Finding]:
    """`workspace.json` and the directories on disk, compared both ways."""
    base = engineering_root(root)
    manifest = read_json_safe(base / "workspace.json")
    declared = {str(name) for name in manifest.get("directories", []) if isinstance(name, str)}
    if not declared:
        return []
    actual = {entry.name for entry in base.iterdir() if entry.is_dir()}
    findings = [
        Finding(
            "workspace-dir-drift",
            "medium",
            f"workspace.json declares `{name}` but the directory does not exist.",
            relpath(base / "workspace.json", root),
        )
        for name in sorted(declared - actual)
    ]
    findings += [
        Finding(
            "workspace-dir-drift",
            "medium",
            f"`{name}` exists but workspace.json does not declare it, so nothing treats it as part of the contract.",
            relpath(base / "workspace.json", root),
        )
        for name in sorted(actual - declared)
    ]
    return findings


def check_initiative_registry(root: Path) -> list[Finding]:
    """Initiative folders and registry entries, compared against the raw file.

    Deliberately reads `registry.json` directly rather than going through
    `load_initiative_registry`, which adopts unknown directories into its reconciled
    view by design. A rule built on the reconciled view can never fire.
    """
    base = engineering_root(root) / "initiatives"
    if not base.is_dir():
        return []
    raw = read_json_safe(base / "registry.json")
    registered = {
        str(entry.get("id")) for entry in raw.get("initiatives", []) if isinstance(entry, dict) and entry.get("id")
    }
    on_disk = {entry.name for entry in base.iterdir() if entry.is_dir()}
    findings: list[Finding] = []
    if not raw and on_disk:
        return [
            Finding(
                "orphan-initiative-folder",
                "medium",
                f"{len(on_disk)} initiative folder(s) exist but initiatives/registry.json does not. "
                "Run `/initiative list` to create it.",
                relpath(base, root),
            )
        ]
    findings += [
        Finding("orphan-initiative-folder", "medium", f"`{name}` has no registry entry.", relpath(base / name, root))
        for name in sorted(on_disk - registered)
    ]
    findings += [
        Finding(
            "orphan-registry-entry",
            "high",
            f"registry.json lists `{name}` but its folder no longer exists.",
            relpath(base / "registry.json", root),
        )
        for name in sorted(registered - on_disk)
    ]
    docs = docs_root(root)
    if docs.is_dir():
        findings += [
            Finding(
                "orphan-docs-tree",
                "low",
                f"`docs/engineering/{entry.name}` has no matching initiative.",
                relpath(entry, root),
            )
            for entry in sorted(docs.iterdir())
            if entry.is_dir() and entry.name not in on_disk
        ]
    return findings


def check_front_matter(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_markdown(root):
        parts = set(path.parts)
        if not ({"initiatives"} & parts) and docs_root(root) not in path.parents:
            continue
        try:
            front, _ = parse_front_matter(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        missing = [key for key in REQUIRED_FRONT_MATTER if key not in front]
        if missing:
            findings.append(
                Finding(
                    "missing-front-matter",
                    "medium",
                    "Artifact is missing required front matter: " + ", ".join(missing),
                    relpath(path, root),
                )
            )
    return findings


def check_dangling_sources(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_markdown(root):
        try:
            front, _ = parse_front_matter(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        for source in front.get("source_artifacts") or []:
            value = str(source).strip()
            if not value or value.startswith("<"):
                continue
            if (root / value).exists() or (path.parent / value).exists():
                continue
            findings.append(
                Finding(
                    "dangling-source-reference",
                    "medium",
                    f"source_artifacts names `{value}`, which does not exist.",
                    relpath(path, root),
                )
            )
    return findings


# --- ledger ----------------------------------------------------------------


def _action_item_files(root: Path) -> list[Path]:
    base = engineering_root(root)
    return sorted(base.rglob("*action-items*.json")) if base.is_dir() else []


def check_ledger(root: Path) -> list[Finding]:
    base = engineering_root(root)
    if not base.is_dir():
        return []
    findings: list[Finding] = []
    canonical = base / "ledger" / "action-items.json"
    seen_ids: dict[str, str] = {}

    for path in _action_item_files(root):
        rel = relpath(path, root)
        data = read_json_safe(path)
        items = data.get("action_items", []) if isinstance(data, dict) else []
        # Pins H4: linear-sync.py once read only the canonical file while
        # sync-ledger.py aggregated from everywhere, so these were invisible to
        # tracker sync while appearing on the dashboard.
        if path != canonical and items:
            findings.append(
                Finding(
                    "unreachable-action-items",
                    "high",
                    f"{len(items)} action item(s) live outside ledger/action-items.json. "
                    "Confirm tracker sync collects them.",
                    rel,
                )
            )
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            identifier = str(item["id"])
            if identifier in seen_ids and seen_ids[identifier] != rel:
                findings.append(
                    Finding(
                        "duplicate-item-id",
                        "medium",
                        f"Action item id `{identifier}` appears in two files ({seen_ids[identifier]} and {rel}).",
                        rel,
                    )
                )
            seen_ids[identifier] = rel

            source = item.get("source")
            if item.get("status") == "done" and isinstance(source, str) and (root / source).is_file():
                text = (root / source).read_text(encoding="utf-8", errors="ignore")
                title = str(item.get("title", "")).strip()
                if title and any(title in match for match in _CHECKBOX_OPEN.findall(text)):
                    findings.append(
                        Finding(
                            "contradictory-ledger",
                            "high",
                            f"`{identifier}` is marked done but `{source}` still shows it unchecked.",
                            rel,
                            title[:120],
                        )
                    )

    # Pins C3: emit-action-items.py used to overwrite the file wholesale, dropping
    # every id the tracker had written back.
    state = read_json_safe(base / "ledger" / "linear-state.json").get("tasks", {})
    known_ids = {f"action:{identifier}" for identifier in seen_ids}
    for key in sorted(state):
        if not key.startswith("action:") or key in known_ids:
            continue
        findings.append(
            Finding(
                "clobbered-external-id",
                "high",
                f"linear-state.json has `{key}` filed, but no action item carries that id any more.",
                relpath(base / "ledger" / "linear-state.json", root),
            )
        )

    ledger = base / "ledger" / "ledger.json"
    if ledger.is_file():
        newest = max((path.stat().st_mtime for path in base.rglob("*.md") if path.is_file()), default=0)
        if newest and ledger.stat().st_mtime < newest - 60:
            findings.append(
                Finding(
                    "stale-ledger",
                    "medium",
                    "ledger.json is older than the newest artifact; run `eng-life sync-ledger`.",
                    relpath(ledger, root),
                )
            )
    return findings


def check_stale_artifacts(root: Path) -> list[Finding]:
    base = engineering_root(root) / "initiatives"
    raw = read_json_safe(engineering_root(root) / "initiatives" / "registry.json")
    active = raw.get("active")
    if not active or not (base / str(active)).is_dir():
        return []
    return [
        Finding(
            "stale-artifact",
            "low",
            f"Artifact in the active initiative has not changed in {int(_age_days(path))} days.",
            relpath(path, root),
        )
        for path in sorted((base / str(active)).rglob("*.md"))
        if _age_days(path) > STALE_DAYS
    ]


def check_open_questions(root: Path) -> list[Finding]:
    store = read_json_safe(engineering_root(root) / "questions" / "open-questions.json")
    cutoff = datetime.now(UTC) - timedelta(days=UNANSWERED_QUESTION_DAYS)
    findings: list[Finding] = []
    for entry in store.get("open_questions", []):
        if not isinstance(entry, dict) or entry.get("status") != "open":
            continue
        asked = _parse_iso(entry.get("asked_at"))
        if asked and asked < cutoff:
            findings.append(
                Finding(
                    "unanswered-question-age",
                    "low",
                    f"Open for {(datetime.now(UTC) - asked).days} days: {str(entry.get('question', ''))[:110]}",
                    relpath(engineering_root(root) / "questions" / "open-questions.json", root),
                )
            )
    return findings


# --- tracker configuration -------------------------------------------------


def check_tracker_config(root: Path) -> list[Finding]:
    base = engineering_root(root)
    settings_file = base / "settings.json"
    findings: list[Finding] = []
    if not settings_file.is_file():
        return findings
    data = read_json_safe(settings_file)
    rel = relpath(settings_file, root)
    filing = data.get("issue_filing")
    if not isinstance(filing, dict):
        return [Finding("tracker-config-invalid", "high", "settings.json has no issue_filing object.", rel)]

    try:
        import trackers

        known = set(trackers.all_trackers(root))
    except Exception:
        known = set()
    provider = filing.get("provider")
    if provider and known and provider not in known:
        findings.append(
            Finding(
                "tracker-config-invalid",
                "high",
                f"provider `{provider}` is not a known tracker. Known: {', '.join(sorted(known))}.",
                rel,
            )
        )

    # A credential in a committed file is the one thing here that is always urgent.
    for key, value in _walk(filing):
        if _SECRETISH.search(key) and isinstance(value, str) and value.strip():
            findings.append(
                Finding(
                    "tracker-secret-in-settings",
                    "critical",
                    f"`{key}` holds a non-empty value in a committed settings file. "
                    "Credentials belong in the MCP connector, never here.",
                    rel,
                    "<redacted>",
                )
            )

    legacy = base / "ledger" / "linear-config.json"
    if legacy.is_file():
        legacy_team = read_json_safe(legacy).get("team")
        settings_team = (filing.get("scope") or {}).get("team")
        if legacy_team and settings_team and legacy_team != settings_team:
            findings.append(
                Finding(
                    "tracker-config-split",
                    "medium",
                    f"settings.json says team `{settings_team}` and linear-config.json says `{legacy_team}`.",
                    rel,
                )
            )
    return findings


def _walk(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, inner in value.items():
            yield from _walk(inner, f"{prefix}.{key}" if prefix else str(key))
    else:
        yield prefix, value


def check_declared_checks(root: Path) -> list[Finding]:
    """Reports that say, in their own content, that they did not really run.

    This replaces a rule that tried to match a report file back to the script that
    produced it. There is no naming convention connecting the two - `anti-slop.json`
    comes from `anti-slop-check.py`, `changed-files.json` from
    `changed-files-classifier.py` - and on its first run that rule was two findings
    for two false positives. Guessing at a convention that does not exist is exactly
    the noise this module refuses to produce.

    What IS establishable is what a report says about itself. Since every checker
    now carries `checked`, a report claiming a verdict without it, or admitting a
    rule crashed, is a real finding.
    """
    base = engineering_root(root) / "reports" / "validation"
    if not base.is_dir():
        return []
    findings: list[Finding] = []
    verdicts = {"valid", "in_sync", "complete", "complete_enough"}
    for path in sorted(base.glob("*.json")):
        data = read_json_safe(path)
        if not data:
            continue
        rel = relpath(path, root)
        if verdicts & set(data) and "checked" not in data:
            findings.append(
                Finding(
                    "unqualified-verdict",
                    "high",
                    f"`{path.name}` asserts a verdict without saying whether the check actually ran.",
                    rel,
                )
            )
        for errored in data.get("rules_errored", []) or []:
            findings.append(
                Finding(
                    "checker-errored",
                    "high",
                    f"A rule in `{path.name}` crashed: {errored.get('rule')} - {errored.get('error', '')[:100]}",
                    rel,
                )
            )
    return findings


def check_schema_violations(root: Path) -> list[Finding]:
    """Delegate to the schema validator rather than reimplementing it."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_vs", Path(__file__).resolve().parent / "validate-schemas.py")
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return []
    findings: list[Finding] = []
    for path in _iter_json(root):
        key = module.schema_key_for(path)
        if not key:
            continue
        schema = module.load_schema(key) if hasattr(module, "load_schema") else None
        if not schema:
            continue
        for error in module.validate_value(read_json_safe(path), schema, path.name):
            findings.append(Finding("schema-violation", "high", str(error)[:200], relpath(path, root)))
    return findings


RULES: tuple[Rule, ...] = (
    Rule("readability", "high", "Artifacts that cannot be read", check_unreadable),
    Rule("workspace-dir-drift", "medium", "Declared directories versus disk", check_workspace_dir_drift),
    Rule("initiative-registry", "high", "Initiative folders versus the registry", check_initiative_registry),
    Rule("front-matter", "medium", "Required artifact front matter", check_front_matter),
    Rule("dangling-sources", "medium", "source_artifacts that do not resolve", check_dangling_sources),
    Rule("ledger", "high", "Ledger consistency and reachability", check_ledger),
    Rule("stale-artifacts", "low", "Untouched artifacts in the active initiative", check_stale_artifacts),
    Rule("open-questions", "low", "Questions nobody has answered", check_open_questions),
    Rule("tracker-config", "critical", "Issue-tracking configuration", check_tracker_config),
    Rule("declared-checks", "high", "Reports that admit they did not really run", check_declared_checks),
    Rule("schema-violations", "high", "Generated JSON against its schema", check_schema_violations),
)

SEVERITY_ORDER = ("critical", "high", "medium", "low")


def scan(root: Path, minimum: str = "low") -> dict[str, Any]:
    threshold = SEVERITY_ORDER.index(minimum) if minimum in SEVERITY_ORDER else len(SEVERITY_ORDER) - 1
    findings: list[Finding] = []
    errored: list[dict[str, str]] = []
    for rule in RULES:
        try:
            findings.extend(rule.check(root))
        except Exception as exc:
            # A rule that throws must say so. Swallowing it would turn a broken
            # detector into a clean report, which is the failure mode this whole
            # subsystem exists to prevent.
            errored.append({"rule": rule.id, "error": f"{type(exc).__name__}: {exc}"[:200]})
    kept = [item for item in findings if SEVERITY_ORDER.index(item.severity) <= threshold]
    counts = {severity: sum(1 for item in kept if item.severity == severity) for severity in SEVERITY_ORDER}
    return {
        "checked": True,
        "generated_at": now_iso(),
        "rules_run": len(RULES) - len(errored),
        "rules_errored": errored,
        "finding_count": len(kept),
        "counts": counts,
        "findings": [item.as_dict() for item in kept],
        "reference": "references/issue-surfacing-policy.md",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--hook", action="store_true", help="Stay silent when nothing is found")
    parser.add_argument("--severity", default="low", choices=list(SEVERITY_ORDER))
    parser.add_argument("--emit-queue", action="store_true", help="Push findings into the surfaced-issues queue")
    args = parser.parse_args()
    root = resolve_cli_root(args.root).root

    if not workspace_exists(root):
        if args.hook:
            return 0
        emit_json({"checked": False, "reason": "no lifecycle workspace"})
        return 0

    result = scan(root, args.severity)
    write_json(engineering_root(root) / "reports" / "validation" / "project-anomalies.json", result)

    if args.emit_queue and result["findings"]:
        from tracker import record_issues

        record_issues(
            root,
            [
                {
                    "title": finding["message"][:160],
                    "body": finding.get("evidence", ""),
                    "severity": finding["severity"],
                    "kind": "anomaly",
                    "origin": "detector",
                    "rule": finding["rule"],
                    "paths": [finding["path"]] if finding["path"] else [],
                }
                for finding in result["findings"]
            ],
        )
        result["queued"] = len(result["findings"])

    if args.hook and not result["findings"] and not result["rules_errored"]:
        return 0
    emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
