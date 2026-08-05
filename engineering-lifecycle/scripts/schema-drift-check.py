#!/usr/bin/env python3
"""Compare the designed data model against the migrations that actually shipped.

A data model is only worth referring back to while it still describes reality.
This reports tables that exist in one place and not the other, at name level
only, so every finding is something that can be established rather than inferred.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_model import drift_report, find_live_schema_sources
from eng_common import (
    docs_root,
    emit_json,
    engineering_root,
    read_json,
    relpath,
    repo_root,
    workspace_exists,
    write_json,
)


def find_models(root: Path) -> list[Path]:
    base = docs_root(root)
    if not base.is_dir():
        return []
    return sorted(base.glob("*/data/data-model.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--hook", action="store_true", help="Stay silent when there is nothing to report")
    args = parser.parse_args()
    root = repo_root(Path(args.root))

    # Each model records the dialect it was built in, so the migration directories
    # searched follow that model rather than a fixed Postgres/Supabase list.
    reports = []
    for path in find_models(root):
        model = read_json(path) or {}
        sources = find_live_schema_sources(root, model.get("dialect"))
        report = drift_report(model, sources, root)
        report["model"] = relpath(path, root)
        report["dialect"] = model.get("dialect", "postgresql")
        reports.append(report)

    drifted = [report for report in reports if report["checked"] and not report["in_sync"]]
    result = {"models": len(reports), "drifted": len(drifted), "reports": reports}
    if workspace_exists(root) and reports:
        write_json(engineering_root(root) / "reports" / "validation" / "schema-drift.json", result)
    if args.hook and not drifted:
        return 0
    emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
