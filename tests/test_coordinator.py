"""
test_coordinator.py — unit tests for mergeproof/coordinator.py.

Covers:
 - _deduplicate: basic dedup, highest-severity wins, no-overlap passthrough
 - _derive_overall_risk: empty → low, each severity level, all-critical
 - coordinate: empty input, all-critical input, demo-mode shortcut,
               is_demo propagation, deduplication integration
"""

import os

import pytest

# Force DEMO_MODE off so we can test the pure logic paths without LLM calls.
# Individual tests that want DEMO_MODE use monkeypatch.
os.environ.setdefault("DEMO_MODE", "false")

import importlib

import mergeproof.coordinator as coord_mod
importlib.reload(coord_mod)

from mergeproof.coordinator import _deduplicate, _derive_overall_risk, coordinate
from mergeproof.schemas import CoordinatorReport, Finding, ReviewerOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_finding(
    severity="low",
    category="correctness",
    file="calc.py",
    line=10,
    evidence="x = 1",
    explanation="test explanation",
    recommendation="fix it",
) -> Finding:
    return Finding(
        severity=severity,
        category=category,
        file=file,
        line=line,
        evidence=evidence,
        explanation=explanation,
        recommendation=recommendation,
    )


def make_reviewer_output(
    findings: list[Finding],
    reviewer_name: str = "correctness",
    is_demo: bool = False,
) -> ReviewerOutput:
    return ReviewerOutput(
        reviewer_name=reviewer_name,
        findings=findings,
        is_demo=is_demo,
    )


# ---------------------------------------------------------------------------
# _deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_empty_list(self):
        assert _deduplicate([]) == []

    def test_no_overlap_passthrough(self):
        f1 = make_finding(file="a.py", line=1, category="correctness")
        f2 = make_finding(file="a.py", line=2, category="correctness")
        result = _deduplicate([f1, f2])
        assert len(result) == 2

    def test_exact_duplicate_keeps_first(self):
        f1 = make_finding(severity="low", file="a.py", line=5, category="security")
        f2 = make_finding(severity="low", file="a.py", line=5, category="security")
        result = _deduplicate([f1, f2])
        assert len(result) == 1

    def test_same_key_keeps_highest_severity(self):
        f_low = make_finding(severity="low", file="a.py", line=5, category="security")
        f_high = make_finding(severity="high", file="a.py", line=5, category="security")
        result = _deduplicate([f_low, f_high])
        assert len(result) == 1
        assert result[0].severity == "high"

    def test_same_key_keeps_highest_severity_reverse_order(self):
        """Order of input should not matter — highest severity always wins."""
        f_critical = make_finding(severity="critical", file="b.py", line=1, category="correctness")
        f_medium = make_finding(severity="medium", file="b.py", line=1, category="correctness")
        result = _deduplicate([f_critical, f_medium])
        assert len(result) == 1
        assert result[0].severity == "critical"

    def test_different_category_same_file_line_not_merged(self):
        f1 = make_finding(category="correctness", file="a.py", line=10)
        f2 = make_finding(category="security", file="a.py", line=10)
        result = _deduplicate([f1, f2])
        assert len(result) == 2

    def test_line_none_treated_as_key(self):
        f1 = make_finding(line=None, file="a.py", category="performance", severity="low")
        f2 = make_finding(line=None, file="a.py", category="performance", severity="high")
        result = _deduplicate([f1, f2])
        assert len(result) == 1
        assert result[0].severity == "high"

    def test_multiple_reviewers_deduped(self):
        """Same issue reported by two different reviewers → one finding."""
        f1 = make_finding(severity="medium", file="x.py", line=7, category="security")
        f2 = make_finding(severity="critical", file="x.py", line=7, category="security")
        f3 = make_finding(file="x.py", line=8, category="security")  # different line
        result = _deduplicate([f1, f2, f3])
        assert len(result) == 2
        severities = {f.line: f.severity for f in result}
        assert severities[7] == "critical"


# ---------------------------------------------------------------------------
# _derive_overall_risk
# ---------------------------------------------------------------------------

class TestDeriveOverallRisk:
    def test_empty_returns_low(self):
        assert _derive_overall_risk([]) == "low"

    def test_info_only_returns_low(self):
        # "info" is not a valid RiskLevel — must be mapped to "low"
        f = make_finding(severity="info")
        assert _derive_overall_risk([f]) == "low"

    def test_low_finding_returns_low(self):
        assert _derive_overall_risk([make_finding(severity="low")]) == "low"

    def test_medium_finding_returns_medium(self):
        assert _derive_overall_risk([make_finding(severity="medium")]) == "medium"

    def test_high_finding_returns_high(self):
        assert _derive_overall_risk([make_finding(severity="high")]) == "high"

    def test_critical_finding_returns_critical(self):
        assert _derive_overall_risk([make_finding(severity="critical")]) == "critical"

    def test_mixed_returns_highest(self):
        findings = [
            make_finding(severity="low"),
            make_finding(severity="critical", file="a.py", line=2),
            make_finding(severity="medium", file="a.py", line=3),
        ]
        assert _derive_overall_risk(findings) == "critical"

    def test_all_critical_returns_critical(self):
        findings = [make_finding(severity="critical", line=i) for i in range(5)]
        assert _derive_overall_risk(findings) == "critical"


# ---------------------------------------------------------------------------
# coordinate — integration tests (no LLM calls; all DEMO_MODE or pure-logic)
# ---------------------------------------------------------------------------

class TestCoordinate:
    def test_empty_input_returns_low_risk(self, monkeypatch):
        """No reviewer outputs → no findings → overall_risk must be 'low'."""
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        # Stub out _llm_summary to avoid real LLM call
        monkeypatch.setattr(coord_mod, "_llm_summary", lambda findings, risk: "stub summary")
        report = coordinate([])
        assert isinstance(report, CoordinatorReport)
        assert report.overall_risk == "low"
        assert report.findings == []
        assert report.is_demo is False

    def test_all_critical_findings_returns_critical_risk(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        monkeypatch.setattr(coord_mod, "_llm_summary", lambda f, r: "stub")
        findings = [make_finding(severity="critical", line=i, file=f"f{i}.py") for i in range(3)]
        ro = make_reviewer_output(findings, reviewer_name="security")
        report = coordinate([ro])
        assert report.overall_risk == "critical"
        assert report.is_demo is False

    def test_deduplication_integrated(self, monkeypatch):
        """Two reviewers report the same (file, line, category) — only one finding survives."""
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        monkeypatch.setattr(coord_mod, "_llm_summary", lambda f, r: "stub")
        f_low = make_finding(severity="low", file="dup.py", line=1, category="correctness")
        f_high = make_finding(severity="high", file="dup.py", line=1, category="correctness")
        ro1 = make_reviewer_output([f_low], reviewer_name="correctness")
        ro2 = make_reviewer_output([f_high], reviewer_name="security")
        report = coordinate([ro1, ro2])
        assert len(report.findings) == 1
        assert report.findings[0].severity == "high"
        assert report.overall_risk == "high"

    def test_is_demo_propagates_from_any_reviewer(self, monkeypatch):
        """If any ReviewerOutput.is_demo is True → CoordinatorReport.is_demo must be True."""
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        ro_live = make_reviewer_output([make_finding()], is_demo=False)
        ro_demo = make_reviewer_output([make_finding(file="b.py", line=2)], is_demo=True)
        report = coordinate([ro_live, ro_demo])
        assert report.is_demo is True

    def test_demo_mode_returns_demo_coordinator_report(self, monkeypatch):
        from mergeproof.demo_mode import DEMO_COORDINATOR_REPORT
        monkeypatch.setattr(coord_mod, "DEMO_MODE", True)
        ro = make_reviewer_output([make_finding()], is_demo=False)
        report = coordinate([ro])
        assert report is DEMO_COORDINATOR_REPORT
        assert report.is_demo is True

    def test_returns_coordinator_report_schema(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        monkeypatch.setattr(coord_mod, "_llm_summary", lambda f, r: "summary text")
        ro = make_reviewer_output([make_finding(severity="medium")])
        report = coordinate([ro])
        # Validate the full schema round-trip
        import json
        reconstructed = CoordinatorReport.model_validate(
            json.loads(report.model_dump_json())
        )
        assert reconstructed == report

    def test_summary_set_from_stub(self, monkeypatch):
        monkeypatch.setattr(coord_mod, "DEMO_MODE", False)
        monkeypatch.setattr(coord_mod, "_llm_summary", lambda f, r: "expected summary text")
        ro = make_reviewer_output([make_finding()])
        report = coordinate([ro])
        assert report.summary == "expected summary text"

    def test_demo_coordinator_report_valid_schema(self):
        """DEMO_COORDINATOR_REPORT must itself be schema-valid."""
        from mergeproof.demo_mode import DEMO_COORDINATOR_REPORT
        import json
        reconstructed = CoordinatorReport.model_validate(
            json.loads(DEMO_COORDINATOR_REPORT.model_dump_json())
        )
        assert reconstructed == DEMO_COORDINATOR_REPORT

    def test_demo_coordinator_report_overall_risk_is_critical(self):
        from mergeproof.demo_mode import DEMO_COORDINATOR_REPORT
        assert DEMO_COORDINATOR_REPORT.overall_risk == "critical"

    def test_demo_coordinator_report_has_findings(self):
        from mergeproof.demo_mode import DEMO_COORDINATOR_REPORT
        assert len(DEMO_COORDINATOR_REPORT.findings) >= 4
