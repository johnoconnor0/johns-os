"""Tests for the ai-utilities audit scripts.

This plugin had no tests at all, and `scripts/validate-repo.py` named its two test
directories explicitly, so it could not have run them if it had. Both are fixed:
the validator discovers `*/tests` now, and this file is what it finds here.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import audit_common  # noqa: E402
import families  # noqa: E402
import findings as findings_mod  # noqa: E402
import plan_parse  # noqa: E402
import render_report  # noqa: E402
import resolver  # noqa: E402
import stack_probe  # noqa: E402
import verify as verify_mod  # noqa: E402


class AuditCommonTests(unittest.TestCase):
    def test_front_matter_parses_scalars_and_lists(self) -> None:
        text = '---\ninitiative_id: alpha\nstatus: draft\nsource_artifacts:\n  - "docs/a.md"\n  - docs/b.md\n---\n\n# Body\n'
        front, body = audit_common.parse_front_matter(text)
        self.assertEqual(front["initiative_id"], "alpha")
        self.assertEqual(front["source_artifacts"], ["docs/a.md", "docs/b.md"])
        self.assertTrue(body.startswith("\n# Body") or body.startswith("# Body"))

    def test_front_matter_absent_returns_the_whole_text(self) -> None:
        front, body = audit_common.parse_front_matter("# Just a heading\n")
        self.assertEqual(front, {})
        self.assertEqual(body, "# Just a heading\n")

    def test_audit_dir_is_one_directory_per_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = audit_common.audit_dir(root, "2026-08-06_101530")
            second = audit_common.audit_dir(root, "2026-08-06_101531")
            self.assertNotEqual(first, second)
            # Names still sort chronologically, so audit-resolver's newest-by-name
            # discovery keeps working against a directory instead of a bare file.
            self.assertLess(first.name, second.name)

    def test_scan_files_prunes_generated_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (root / "node_modules" / "pkg").mkdir(parents=True)
            (root / "node_modules" / "pkg" / "skip.py").write_text("y = 2\n", encoding="utf-8")
            found = {path.name for path in audit_common.scan_files(root, frozenset({".py"}))}
            self.assertIn("keep.py", found)
            self.assertNotIn("skip.py", found)


class StackProbeTests(unittest.TestCase):
    def test_workspace_rung_wins_and_is_labelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".project" / ".engineering" / "context"
            target.mkdir(parents=True)
            audit_common.write_json(
                target / "stack.json",
                {"backend": ["Elixir"], "database": ["CouchDB"], "package_manager": "mix", "test_commands": {}},
            )
            stack = stack_probe.resolve_stack(root)
            self.assertEqual(stack["detector"], "workspace")
            self.assertEqual(stack["backend"], ["Elixir"])

    def test_vendored_rung_detects_a_python_repo_without_any_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
            (root / "tests").mkdir()
            stack = stack_probe.resolve_stack(root, prefer="vendored")
            self.assertEqual(stack["detector"], "vendored")
            self.assertEqual(stack["backend"], ["Python"])
            self.assertEqual(stack["package_manager"], "python")
            self.assertIn("unit", stack["test_commands"])

    def test_every_rung_answers_the_same_shape(self) -> None:
        # Callers gate whole check families on these keys. A rung that omitted one
        # would silently switch a family off rather than fail, which is precisely
        # the not-applicable / not-checked conflation the rebuild exists to end.
        required = {"detector", "frameworks", "backend", "database", "testing", "package_manager", "test_commands"}
        for rung in ("workspace", "imported", "vendored"):
            with self.subTest(rung=rung):
                stack = stack_probe.resolve_stack(ROOT.parent, prefer=rung)
                self.assertTrue(required.issubset(stack), sorted(required - set(stack)))

    def test_a_repo_with_no_markers_still_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stack = stack_probe.resolve_stack(Path(tmp), prefer="vendored")
            self.assertEqual(stack["backend"], [])
            self.assertEqual(stack["database"], [])
            self.assertIsNone(stack["package_manager"])


class FixtureTests(unittest.TestCase):
    def test_the_tiny_repo_fixture_is_intact(self) -> None:
        # The functional eval and the audit's own tests both point at this fixture.
        # Its eval suite used to carry a `<replace-with-real-path>` placeholder, so
        # the functional case had never once been runnable.
        fixture = FIXTURES / "tiny-python-repo"
        self.assertTrue((fixture / "PLAN.md").is_file())
        self.assertTrue((fixture / "src" / "a.py").is_file())
        plan = (fixture / "PLAN.md").read_text(encoding="utf-8")
        self.assertIn("### 1.1", plan, "the fixture must exercise the numbered-headings extractor")
        self.assertNotIn("- [ ]", plan, "a checkbox would let a checkbox-only parser pass by accident")


class PlanParseTests(unittest.TestCase):
    def _parse(self, text: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "PLAN.md"
            plan.write_text(text, encoding="utf-8")
            return plan_parse.parse_plan(plan, root)

    def test_checkboxes_win_outright(self) -> None:
        result = self._parse("# P\n\n- [x] One\n- [ ] Two\n")
        self.assertEqual(result["parsed_by"], "action-items")
        self.assertEqual([item.status for item in result["items"]], ["complete", "not-started"])

    def test_numbered_headings_are_read_when_there_are_no_checkboxes(self) -> None:
        # The one real plan on record stated its items this way. A checkbox-only
        # parser would have found zero items in it and audited nothing, confidently.
        result = self._parse("# P\n\n## 1. Group\n\n### 1.1 First\n\ntext\n\n### 1.2 Second\n\ntext\n")
        self.assertEqual(result["parsed_by"], "numbered-headings")
        self.assertEqual([item.id for item in result["items"]], ["1.1", "1.2"])

    def test_group_headings_are_not_counted_as_items(self) -> None:
        # `## 1. Group` above `### 1.1` is a table of contents entry, not work.
        # Counting it inflates the denominator with an item nothing can satisfy.
        result = self._parse("# P\n\n## 1. Group\n\n### 1.1 A\n\n### 1.2 B\n\n## 2. Other\n\n### 2.1 C\n")
        self.assertEqual({item.id for item in result["items"]}, {"1.1", "1.2", "2.1"})

    def test_the_finer_heading_extractor_wins_over_the_coarser_one(self) -> None:
        # Regression: phase-sections matched three `## Wave N` headings and won by
        # cascade order, so a nineteen-item plan was read as three items.
        text = "# P\n\n## Wave 1 - Blockers\n\n### 1.1 A\n\n### 1.2 B\n\n## Wave 2 - Rest\n\n### 2.1 C\n"
        result = self._parse(text)
        self.assertEqual(result["parsed_by"], "numbered-headings")
        self.assertEqual(result["item_count"], 3)

    def test_an_unparseable_plan_reports_nothing_rather_than_guessing(self) -> None:
        result = self._parse("# Plan\n\nSome prose with no structure at all.\n")
        self.assertIsNone(result["parsed_by"])
        self.assertEqual(result["items"], [])

    def test_mentions_are_collected_for_the_drift_join(self) -> None:
        result = self._parse("# P\n\n### 1.1 A\n\nImplement `scripts/foo.py`.\n\n### 1.2 B\n\nNothing.\n")
        self.assertIn("scripts/foo.py", result["items"][0].mentions)
        plan_parse.mark_unverifiable(result["items"], {"scripts/foo.py"})
        self.assertEqual(result["items"][0].status, "unverifiable")
        self.assertEqual(result["items"][1].status, "not-started")


class FindingsTests(unittest.TestCase):
    def _finding(self, line: int, title: str = "Unused import `json`") -> findings_mod.Finding:
        return findings_mod.Finding(
            family="static-analysis",
            rule="ruff/F401",
            severity="warning",
            title=title,
            evidence=[findings_mod.Evidence("scripts/foo.py", line, "import json")],
        )

    def test_identity_survives_a_line_move_but_content_hash_does_not(self) -> None:
        # The whole reason there are two hashes. One hash over fields including the
        # line means adding an import above a finding gives it a new identity, and
        # the tracker files a second issue for the same problem.
        first, moved = self._finding(12), self._finding(48)
        self.assertEqual(first.identity, moved.identity)
        self.assertNotEqual(first.content_hash, moved.content_hash)

    def test_identity_differs_when_the_finding_differs(self) -> None:
        self.assertNotEqual(self._finding(12).identity, self._finding(12, "Unused import `os`").identity)

    def test_a_non_verdict_outcome_must_state_a_reason(self) -> None:
        for outcome in findings_mod.OUTCOMES_NEEDING_REASON:
            with self.subTest(outcome=outcome):
                bare = findings_mod.FamilyResult(id="x", title="X", outcome=outcome)
                self.assertTrue(bare.validate(), f"{outcome} with no reason must not validate")
                explained = findings_mod.FamilyResult(id="x", title="X", outcome=outcome, reason="because")
                self.assertEqual(explained.validate(), [])

    def test_passed_with_findings_and_failed_without_are_both_rejected(self) -> None:
        self.assertTrue(findings_mod.FamilyResult(id="x", title="X", outcome="failed").validate())
        with_finding = findings_mod.FamilyResult(id="x", title="X", outcome="passed", findings=[self._finding(1)])
        self.assertTrue(with_finding.validate())

    def test_every_registered_family_appears_in_output(self) -> None:
        # This is the replacement for "never skip a phase". That was prose, and the
        # single real run on record routed straight around it. This is a condition
        # the run fails on.
        document = findings_mod.build_document(
            run_id="T",
            generated_at="2026-01-01T00:00:00+00:00",
            root=".",
            plan={"path": None, "parsed_by": None, "item_count": 0},
            stack={},
            results=[findings_mod.FamilyResult(id="secrets", title="Secrets", outcome="passed")],
            plan_items=[],
        )
        problems = findings_mod.validate_document(document, families.registered_ids())
        self.assertTrue(any("registered but absent" in problem for problem in problems))


class FamilyRegistryTests(unittest.TestCase):
    def _ctx(self, **stack) -> families.Ctx:
        base = {"frameworks": [], "backend": [], "database": [], "testing": [], "test_commands": {}}
        return families.Ctx(root=Path("."), stack={**base, **stack}, plan={"parsed_by": None}, files=[])

    def test_a_family_that_does_not_apply_says_why(self) -> None:
        for family in families.REGISTRY:
            relevant, reason = family.applies_when(self._ctx())
            if not relevant:
                self.assertTrue(reason.strip(), f"{family.id} returned not-applicable with no reason")

    def test_no_database_makes_the_data_layer_not_applicable(self) -> None:
        relevant, reason = families.BY_ID["data-layer"].applies_when(self._ctx())
        self.assertFalse(relevant)
        self.assertIn("no database", reason)

    def test_a_detected_database_makes_it_apply(self) -> None:
        relevant, reason = families.BY_ID["data-layer"].applies_when(self._ctx(database=["PostgreSQL"]))
        self.assertTrue(relevant)
        self.assertIn("PostgreSQL", reason)

    def test_registry_ids_are_unique(self) -> None:
        ids = families.registered_ids()
        self.assertEqual(len(ids), len(set(ids)))


class RenderTests(unittest.TestCase):
    def _document(self, inventory_outcome: str, reason: str = "") -> dict:
        return {
            "run_id": "T",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "root": ".",
            "plan": {"path": "PLAN.md", "parsed_by": "numbered-headings", "item_count": 2},
            "stack": {
                "frameworks": [],
                "backend": ["Python"],
                "database": [],
                "package_manager": "python",
                "detector": "vendored",
            },
            "families": [
                {
                    "id": "plan-inventory",
                    "title": "Plan completion",
                    "outcome": inventory_outcome,
                    "reason": reason,
                    "applies_because": "",
                    "commands": [],
                    "finding_ids": [],
                }
            ],
            "findings": [],
            "plan_items": [
                {
                    "id": "1.1",
                    "title": "A",
                    "source": "PLAN.md:3",
                    "status": "not-started",
                    "reason": "",
                    "mentions": [],
                    "extractor": "numbered-headings",
                    "verified_by": [],
                },
                {
                    "id": "1.2",
                    "title": "B",
                    "source": "PLAN.md:5",
                    "status": "not-started",
                    "reason": "",
                    "mentions": [],
                    "extractor": "numbered-headings",
                    "verified_by": [],
                },
            ],
            "totals": {"critical": 0, "warning": 0, "suggestion": 0},
        }

    def test_no_percentage_is_printed_when_nothing_assessed_completion(self) -> None:
        # "0 of 2 complete (0%)" reads as a measurement and is the absence of one.
        # This is the same defect class as a checker hardcoding a clean verdict.
        text = render_report.render(self._document("not-checked", "assessed by the skill, not by a command"))
        self.assertNotIn("(0%)", text)
        self.assertIn("None have been assessed yet", text)
        self.assertIn("not a verdict", text)

    def test_a_percentage_is_printed_once_completion_was_assessed(self) -> None:
        text = render_report.render(self._document("failed"))
        self.assertIn("0 of 2 plan items complete (0%)", text)

    def test_families_that_did_not_run_are_listed_with_their_reasons(self) -> None:
        text = render_report.render(self._document("not-checked", "needs judgement"))
        self.assertIn("## Not run (1)", text)
        self.assertIn("needs judgement", text)


class ResolverTests(unittest.TestCase):
    def _run_dir(self, root: Path, stamp: str, findings: list[dict]) -> Path:
        target = root / audit_common.AUDIT_DIR / stamp
        audit_common.write_json(
            target / "findings.json",
            {
                "schema": findings_mod.SCHEMA,
                "run_id": stamp,
                "findings": findings,
                "families": [
                    {"id": "secrets", "title": "S", "outcome": "passed", "reason": "", "finding_ids": []},
                    {
                        "id": "data-layer",
                        "title": "D",
                        "outcome": "not-applicable",
                        "reason": "no database",
                        "finding_ids": [],
                    },
                ],
                "plan_items": [],
                "totals": {},
            },
        )
        return target

    def _finding(self, fid: str, severity: str, family: str = "secrets") -> dict:
        return {
            "id": fid,
            "severity": severity,
            "family": family,
            "rule": "x",
            "title": f"finding {fid}",
            "evidence": [{"path": "a.py", "line": 1, "excerpt": ""}],
        }

    def test_discovery_prefers_the_newest_run_and_ignores_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run_dir(root, "2026-01-01_000000", [])
            newest = self._run_dir(root, "2026-06-01_000000", [])
            # A resolver ledger sitting in the audits tree must never be picked up:
            # globbing `**/*audit*.md` for the report is what caused that before.
            ledger = root / ".project" / "audits" / "audit-resolver" / "2026-07-01"
            ledger.mkdir(parents=True)
            (ledger / "audit-resolver-ledger.md").write_text("# Ledger\n", encoding="utf-8")
            self.assertEqual(resolver.discover(root), newest / "findings.json")

    def test_discovery_returns_none_when_there_is_no_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(resolver.discover(Path(tmp)))

    def test_a_legacy_markdown_report_is_converted_and_labelled_as_such(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / audit_common.AUDIT_DIR / "2026-05-01_120000.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                "# Old report\n\n"
                "| 1 | CRITICAL | `src/a.ts:42` | Something is badly wrong here |\n"
                "| 2 | WARNING | no location given at all in this row |\n",
                encoding="utf-8",
            )
            document = resolver.load(report)
            self.assertEqual(document["source"], "markdown-fallback")
            self.assertEqual(len(document["findings"]), 1)
            # The row it could not convert is counted, not dropped in silence.
            self.assertEqual(document["unconverted_rows"], 1)
            self.assertIn("could not be converted", document["families"][0]["reason"])

    def test_summary_surfaces_families_that_never_ran(self) -> None:
        # A resolution that closes every finding while a family never ran has not
        # finished the audit. The count has to be visible for that to be sayable.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run_dir(root, "2026-06-01_000000", [self._finding("F001", "critical")])
            summary = resolver.summarise(resolver.load(resolver.discover(root)))
            self.assertEqual(summary["total"], 1)
            self.assertEqual([item["id"] for item in summary["families_not_run"]], ["data-layer"])
            self.assertEqual(summary["families_not_run"][0]["reason"], "no database")

    def test_selection_filters_and_orders_by_severity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run_dir(
                root,
                "2026-06-01_000000",
                [
                    self._finding("F001", "suggestion"),
                    self._finding("F002", "critical"),
                    self._finding("F003", "warning", family="dead-code"),
                ],
            )
            document = resolver.load(resolver.discover(root))
            self.assertEqual([item["id"] for item in resolver.select(document)], ["F002", "F003", "F001"])
            only_critical = resolver.select(document, severities=("critical",))
            self.assertEqual([item["id"] for item in only_critical], ["F002"])
            by_family = resolver.select(document, families=("dead-code",))
            self.assertEqual([item["id"] for item in by_family], ["F003"])


class VerifyTests(unittest.TestCase):
    def test_a_repo_wide_entrypoint_wins_over_stack_detection(self) -> None:
        # Regression (H5): verify-stack.sh re-derived commands from file presence,
        # probed for two files belonging to a different repository, and never knew
        # about this one's single validation entrypoint.
        chosen = verify_mod.plan(ROOT.parent)
        self.assertEqual(chosen["source"], "entrypoint")
        self.assertEqual(chosen["commands"], ["python scripts/validate-repo.py"])

    def test_declared_commands_are_used_when_there_is_no_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / ".project" / ".engineering" / "context"
            context.mkdir(parents=True)
            audit_common.write_json(
                context / "stack.json",
                {"test_commands": {"unit": "pytest -q", "lint": "ruff check ."}, "package_manager": "python"},
            )
            chosen = verify_mod.plan(root)
            self.assertEqual(chosen["source"], "declared")
            self.assertEqual(chosen["commands"], ["ruff check .", "pytest -q"])

    def test_nothing_detected_reports_unverified_not_passed(self) -> None:
        # verify-stack.sh exited 0 here, which reads as a pass to anything checking
        # the exit code. An absence of verification is not a verification.
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_mod.verify(Path(tmp))
            self.assertEqual(result["status"], "unverified")
            self.assertFalse(result["verified"])
            self.assertEqual(result["commands"], [])


if __name__ == "__main__":
    unittest.main()
