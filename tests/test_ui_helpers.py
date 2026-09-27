"""
test_ui_helpers.py — unit tests for mergeproof/ui_helpers.py.

All functions are pure (no Streamlit) so they can be tested normally.
"""

import pytest

from mergeproof.schemas import CoordinatorReport, Finding
from mergeproof.ui_helpers import (
    SEVERITY_ORDER,
    count_by_severity,
    findings_to_rows,
    resolved_findings,
    risk_badge,
    risk_delta_text,
    severity_badge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_finding(
    severity="high",
    category="correctness",
    file="calc.py",
    line=10,
    evidence="x = 1",
    explanation="bad",
    recommendation="fix",
) -> Finding:
    return Finding(
        severity=severity, category=category, file=file, line=line,
        evidence=evidence, explanation=explanation, recommendation=recommendation,
    )


_SENTINEL = object()

def make_report(findings=_SENTINEL, overall_risk="high", is_demo=False) -> CoordinatorReport:
    return CoordinatorReport(
        findings=[make_finding()] if findings is _SENTINEL else findings,
        overall_risk=overall_risk,  # type: ignore[arg-type]
        summary="test",
        is_demo=is_demo,
    )


# ---------------------------------------------------------------------------
# severity_badge
# ---------------------------------------------------------------------------

def test_severity_badge_critical():
    assert "🔴" in severity_badge("critical")
    assert "CRITICAL" in severity_badge("critical")

def test_severity_badge_high():
    assert "🟠" in severity_badge("high")

def test_severity_badge_medium():
    assert "🟡" in severity_badge("medium")

def test_severity_badge_low():
    assert "🔵" in severity_badge("low")

def test_severity_badge_info():
    assert "⚪" in severity_badge("info")

def test_severity_badge_unknown_defaults_to_white():
    badge = severity_badge("unknown")
    assert "⚪" in badge


# ---------------------------------------------------------------------------
# risk_badge
# ---------------------------------------------------------------------------

def test_risk_badge_critical():
    assert "🔴" in risk_badge("critical")
    assert "CRITICAL" in risk_badge("critical")

def test_risk_badge_low():
    assert "🔵" in risk_badge("low")

def test_risk_badge_unknown():
    badge = risk_badge("something")
    assert "something".upper() in badge


# ---------------------------------------------------------------------------
# findings_to_rows
# ---------------------------------------------------------------------------

def test_findings_to_rows_empty():
    assert findings_to_rows([]) == []

def test_findings_to_rows_returns_list_of_dicts():
    rows = findings_to_rows([make_finding()])
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)

def test_findings_to_rows_has_required_columns():
    rows = findings_to_rows([make_finding()])
    required = {"Severity", "Category", "File", "Line", "Evidence", "Explanation", "Recommendation"}
    assert required.issubset(rows[0].keys())

def test_findings_to_rows_sorted_most_severe_first():
    f_low    = make_finding(severity="low",      file="a.py", line=1)
    f_crit   = make_finding(severity="critical",  file="b.py", line=2)
    f_medium = make_finding(severity="medium",    file="c.py", line=3)
    rows = findings_to_rows([f_low, f_crit, f_medium])
    assert "CRITICAL" in rows[0]["Severity"]
    assert "MEDIUM"   in rows[1]["Severity"]
    assert "LOW"      in rows[2]["Severity"]

def test_findings_to_rows_line_none_shown_as_dash():
    f = make_finding(line=None)
    rows = findings_to_rows([f])
    assert rows[0]["Line"] == "—"

def test_findings_to_rows_line_integer_shown_as_string():
    f = make_finding(line=42)
    rows = findings_to_rows([f])
    assert rows[0]["Line"] == "42"

def test_findings_to_rows_category_formatted():
    f = make_finding(category="test_coverage")
    rows = findings_to_rows([f])
    assert rows[0]["Category"] == "Test Coverage"

def test_findings_to_rows_evidence_preserved():
    f = make_finding(evidence="    return a / b")
    rows = findings_to_rows([f])
    assert rows[0]["Evidence"] == "    return a / b"


# ---------------------------------------------------------------------------
# risk_delta_text
# ---------------------------------------------------------------------------

def test_risk_delta_text_decreased():
    text = risk_delta_text("critical", "low", True)
    assert "⬇️" in text or "decreased" in text

def test_risk_delta_text_not_decreased_equal():
    text = risk_delta_text("high", "high", False)
    assert "unchanged" in text or "➡️" in text

def test_risk_delta_text_increased():
    text = risk_delta_text("low", "high", False)
    assert "⬆️" in text or "increased" in text

def test_risk_delta_text_contains_both_risks():
    text = risk_delta_text("critical", "low", True)
    assert "critical" in text.lower() or "CRITICAL" in text
    assert "low" in text.lower() or "LOW" in text


# ---------------------------------------------------------------------------
# count_by_severity
# ---------------------------------------------------------------------------

def test_count_by_severity_empty():
    counts = count_by_severity([])
    assert counts["critical"] == 0
    assert counts["high"] == 0

def test_count_by_severity_single():
    counts = count_by_severity([make_finding(severity="critical")])
    assert counts["critical"] == 1
    assert counts["high"] == 0

def test_count_by_severity_multiple():
    findings = [
        make_finding(severity="critical", file="a.py", line=1),
        make_finding(severity="critical", file="b.py", line=2),
        make_finding(severity="high",     file="c.py", line=3),
    ]
    counts = count_by_severity(findings)
    assert counts["critical"] == 2
    assert counts["high"] == 1
    assert counts["medium"] == 0


# ---------------------------------------------------------------------------
# resolved_findings
# ---------------------------------------------------------------------------

def test_resolved_findings_all_resolved():
    f = make_finding()
    before = make_report(findings=[f])
    after  = make_report(findings=[])
    resolved, remaining = resolved_findings(before, after)
    assert len(resolved) == 1
    assert len(remaining) == 0

def test_resolved_findings_none_resolved():
    f = make_finding()
    before = make_report(findings=[f])
    after  = make_report(findings=[f])
    resolved, remaining = resolved_findings(before, after)
    assert len(resolved) == 0
    assert len(remaining) == 1

def test_resolved_findings_partial():
    f1 = make_finding(file="a.py", line=1, category="correctness")
    f2 = make_finding(file="a.py", line=2, category="security")
    before = make_report(findings=[f1, f2])
    after  = make_report(findings=[f2])   # f1 resolved
    resolved, remaining = resolved_findings(before, after)
    assert len(resolved) == 1
    assert resolved[0].file == "a.py"
    assert resolved[0].line == 1
    assert len(remaining) == 1

def test_resolved_findings_empty_inputs():
    before = make_report(findings=[])
    after  = make_report(findings=[])
    resolved, remaining = resolved_findings(before, after)
    assert resolved == []
    assert remaining == []
