"""
test_rereview.py — tests for the re-review additions to coordinator.py
                   and the DEMO_REREVIEW_RESULT / DEMO_AFTER_COORDINATOR_REPORT
                   in demo_mode.py.

Covers:
 1. _risk_rank: correct integer mapping for all four RiskLevels
 2. compare_risk: risk_decreased logic (strict less-than)
    - same risk → not decreased
    - higher after → not decreased
    - lower after → decreased
    - resolved / remaining finding counts in summary
 3. rerun_review: demo-mode shortcut, is_demo report triggers demo path
 4. Demo fixtures: DEMO_REREVIEW_RESULT and DEMO_AFTER_COORDINATOR_REPORT
    - schema validity, is_demo flags, risk_decreased=True
 5. rerun_review live path (mocked coordinator + reviewer)
"""

import json
import os

import pytest

os.environ.setdefault("DEMO_MODE", "false")

import importlib
import mergeproof.coordinator as coord_mod
importlib.reload(coord_mod)

from mergeproof.coordinator import _risk_rank, compare_risk, rerun_review
from mergeproof.demo_mode import (
    DEMO_AFTER_COORDINATOR_REPORT,
    DEMO_COORDINATOR_REPORT,
    DEMO_REREVIEW_RESULT,
)
from mergeproof.schemas import CoordinatorReport, Finding, ReReviewResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_finding(severity="high", category="correctness", file="f.py", line=1) -> Finding:
    return Finding(
        severity=severity, category=category, file=file, line=line,
        evidence="x = 1", explanation="test", recommendation="fix it",
    )


def make_report(
    overall_risk: str = "high",
    findings=None,
    is_demo: bool = False,
) -> CoordinatorReport:
    return CoordinatorReport(
        findings=findings or [make_finding()],
        overall_risk=overall_risk,  # type: ignore[arg-type]
        summary="test summary",
        is_demo=is_demo,
    )


PATCHED_DIFF = "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,1 +1,1 @@\n-x\n+y"
REPO_FILES = {"calculator.py": "def divide(a, b):\n    if b == 0: raise ValueError\n    return a/b\n"}


# ---------------------------------------------------------------------------
# _risk_rank
# ---------------------------------------------------------------------------

class TestRiskRank:
    def test_critical_is_4(self):
        assert _risk_rank("critical") == 4

    def test_high_is_3(self):
        assert _risk_rank("high") == 3

    def test_medium_is_2(self):
        assert _risk_rank("medium") == 2

    def test_low_is_1(self):
        assert _risk_rank("low") == 1

    def test_unknown_defaults_to_1(self):
        assert _risk_rank("info") == 1
        assert _risk_rank("unknown") == 1

    def test_ordering_preserved(self):
        levels = ["critical", "high", "medium", "low"]
        ranks = [_risk_rank(l) for l in levels]
        assert ranks == sorted(ranks, reverse=True)


# ---------------------------------------------------------------------------
# compare_risk
# ---------------------------------------------------------------------------

class TestCompareRisk:
    def test_risk_decreased_when_after_lower(self):
        before = make_report("critical")
        after  = make_report("low")
        result = compare_risk(before, after)
        assert result.risk_decreased is True

    def test_risk_not_decreased_when_equal(self):
        before = make_report("high")
        after  = make_report("high")
        result = compare_risk(before, after)
        assert result.risk_decreased is False

    def test_risk_not_decreased_when_after_higher(self):
        before = make_report("low")
        after  = make_report("high")
        result = compare_risk(before, after)
        assert result.risk_decreased is False

    def test_previous_risk_field(self):
        result = compare_risk(make_report("critical"), make_report("medium"))
        assert result.previous_risk == "critical"

    def test_new_risk_field(self):
        result = compare_risk(make_report("critical"), make_report("medium"))
        assert result.new_risk == "medium"

    def test_returns_rereview_result_type(self):
        result = compare_risk(make_report("high"), make_report("low"))
        assert isinstance(result, ReReviewResult)

    def test_schema_valid(self):
        result = compare_risk(make_report("critical"), make_report("low"))
        reconstructed = ReReviewResult.model_validate(
            json.loads(result.model_dump_json())
        )
        assert reconstructed == result

    def test_summary_mentions_risk_levels(self):
        result = compare_risk(make_report("high"), make_report("low"))
        assert "high" in result.summary
        assert "low" in result.summary

    def test_resolved_count_in_summary(self):
        """Findings in before but not in after should appear as resolved."""
        f1 = make_finding(file="a.py", line=1, category="correctness")
        f2 = make_finding(file="a.py", line=2, category="security")
        before = make_report("high", findings=[f1, f2])
        # after has only f2 → f1 is resolved
        after = make_report("low", findings=[f2])
        result = compare_risk(before, after)
        assert "1" in result.summary  # 1 finding resolved
        assert result.risk_decreased is True

    def test_no_findings_after_maximum_improvement(self):
        """All findings resolved → remaining_count = 0."""
        f = make_finding()
        before = make_report("high", findings=[f])
        after  = make_report("low", findings=[])
        result = compare_risk(before, after)
        assert result.risk_decreased is True
        assert "0" in result.summary or "remain" in result.summary

    def test_risk_decreased_critical_to_high(self):
        result = compare_risk(make_report("critical"), make_report("high"))
        assert result.risk_decreased is True

    def test_risk_decreased_medium_to_low(self):
        result = compare_risk(make_report("medium"), make_report("low"))
        assert result.risk_decreased is True

    def test_risk_not_decreased_high_to_medium_then_stays(self):
        result = compare_risk(make_report("medium"), make_report("medium"))
        assert result.risk_decreased is False


# ---------------------------------------------------------------------------
# rerun_review — demo path
# ---------------------------------------------------------------------------

class TestRerunReview:
    def test_demo_mode_returns_demo_rereview(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", True)
        result = rerun_review(PATCHED_DIFF, REPO_FILES, make_report("critical"))
        assert result is DEMO_REREVIEW_RESULT

    def test_demo_report_triggers_demo_path(self, monkeypatch):
        """Even with DEMO_MODE=False, is_demo report returns DEMO_REREVIEW_RESULT."""
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        before = make_report("critical", is_demo=True)
        result = rerun_review(PATCHED_DIFF, REPO_FILES, before)
        assert result is DEMO_REREVIEW_RESULT

    def test_demo_result_risk_decreased(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", True)
        result = rerun_review(PATCHED_DIFF, REPO_FILES, make_report())
        assert result.risk_decreased is True

    def test_demo_result_new_risk_is_low(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", True)
        result = rerun_review(PATCHED_DIFF, REPO_FILES, make_report())
        assert result.new_risk == "low"

    def test_rerun_review_returns_rereview_result_type(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", True)
        result = rerun_review(PATCHED_DIFF, REPO_FILES, make_report())
        assert isinstance(result, ReReviewResult)

    def test_live_mode_calls_run_all_reviewers(self, monkeypatch):
        """Live mode must call run_all_reviewers and coordinate, then compare_risk."""
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)

        # Stub run_all_reviewers to return a minimal live ReviewerOutput
        from mergeproof.schemas import ReviewerOutput
        stub_output = ReviewerOutput(
            reviewer_name="correctness",
            findings=[make_finding(severity="low")],
            is_demo=False,
        )

        def fake_run_all(_diff, _files):
            return [stub_output]

        monkeypatch.setattr(
            "mergeproof.reviewer.run_all_reviewers", fake_run_all
        )
        # Also stub _llm_summary to avoid real LLM call inside coordinate()
        monkeypatch.setattr(coord_mod, "_llm_summary", lambda f, r: "stub")

        before = make_report("critical", is_demo=False)
        result = rerun_review(PATCHED_DIFF, REPO_FILES, before)
        assert isinstance(result, ReReviewResult)
        assert result.previous_risk == "critical"
        assert result.risk_decreased is True  # low < critical


# ---------------------------------------------------------------------------
# Demo fixture validity
# ---------------------------------------------------------------------------

class TestDemoFixtures:
    def test_demo_rereview_result_schema(self):
        validated = ReReviewResult.model_validate(DEMO_REREVIEW_RESULT.model_dump())
        assert validated == DEMO_REREVIEW_RESULT

    def test_demo_rereview_risk_decreased(self):
        assert DEMO_REREVIEW_RESULT.risk_decreased is True

    def test_demo_rereview_new_risk_is_low(self):
        assert DEMO_REREVIEW_RESULT.new_risk == "low"

    def test_demo_rereview_previous_risk_is_critical(self):
        assert DEMO_REREVIEW_RESULT.previous_risk == "critical"

    def test_demo_rereview_summary_nonempty(self):
        assert DEMO_REREVIEW_RESULT.summary.strip()

    def test_demo_rereview_roundtrip(self):
        reconstructed = ReReviewResult.model_validate(
            json.loads(DEMO_REREVIEW_RESULT.model_dump_json())
        )
        assert reconstructed == DEMO_REREVIEW_RESULT

    def test_demo_after_report_schema(self):
        validated = CoordinatorReport.model_validate(
            DEMO_AFTER_COORDINATOR_REPORT.model_dump()
        )
        assert validated == DEMO_AFTER_COORDINATOR_REPORT

    def test_demo_after_report_overall_risk_is_low(self):
        assert DEMO_AFTER_COORDINATOR_REPORT.overall_risk == "low"

    def test_demo_after_report_is_demo_true(self):
        assert DEMO_AFTER_COORDINATOR_REPORT.is_demo is True

    def test_demo_risk_decreased_from_critical_to_low(self):
        """Sanity: critical(4) → low(1) is a strict decrease."""
        assert _risk_rank(DEMO_REREVIEW_RESULT.previous_risk) > _risk_rank(
            DEMO_REREVIEW_RESULT.new_risk
        )
