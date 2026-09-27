"""
test_schemas.py — validation tests for mergeproof/schemas.py.

Each test:
  1. Constructs a model with valid data.
  2. Asserts every field is accessible with the expected type.
  3. Round-trips through JSON (model → JSON string → model) and asserts equality.
  4. Asserts that extra fields and invalid literals are rejected.
"""

import json

import pytest
from pydantic import ValidationError

from mergeproof.schemas import (
    CoordinatorReport,
    Finding,
    PatchResult,
    ReReviewResult,
    ReviewerOutput,
    TestRunResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roundtrip(model_instance):
    """Serialise to JSON string then re-parse; return the reconstructed model."""
    cls = type(model_instance)
    return cls.model_validate(json.loads(model_instance.model_dump_json()))


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

VALID_FINDING = dict(
    severity="high",
    category="correctness",
    file="demo/repo/calculator.py",
    line=36,
    evidence="    return a / b",
    explanation="Division by zero is not guarded.",
    recommendation="Add `if b == 0: raise ValueError('divisor cannot be zero')`.",
)


def test_finding_valid():
    f = Finding(**VALID_FINDING)
    assert f.severity == "high"
    assert f.category == "correctness"
    assert f.file == "demo/repo/calculator.py"
    assert f.line == 36
    assert "return a / b" in f.evidence


def test_finding_line_optional():
    data = {**VALID_FINDING, "line": None}
    f = Finding(**data)
    assert f.line is None


def test_finding_roundtrip():
    f = Finding(**VALID_FINDING)
    assert _roundtrip(f) == f


def test_finding_invalid_severity():
    with pytest.raises(ValidationError):
        Finding(**{**VALID_FINDING, "severity": "blocker"})


def test_finding_invalid_category():
    with pytest.raises(ValidationError):
        Finding(**{**VALID_FINDING, "category": "style"})


def test_finding_extra_field_rejected():
    with pytest.raises(ValidationError):
        Finding(**{**VALID_FINDING, "invented_field": "oops"})


def test_finding_missing_required_field():
    data = {k: v for k, v in VALID_FINDING.items() if k != "recommendation"}
    with pytest.raises(ValidationError):
        Finding(**data)


# ---------------------------------------------------------------------------
# ReviewerOutput
# ---------------------------------------------------------------------------

VALID_REVIEWER_OUTPUT = dict(
    reviewer_name="correctness",
    findings=[VALID_FINDING],
    is_demo=False,
)


def test_reviewer_output_valid():
    ro = ReviewerOutput(**VALID_REVIEWER_OUTPUT)
    assert ro.reviewer_name == "correctness"
    assert len(ro.findings) == 1
    assert isinstance(ro.findings[0], Finding)
    assert ro.is_demo is False


def test_reviewer_output_empty_findings():
    ro = ReviewerOutput(reviewer_name="security", findings=[], is_demo=True)
    assert ro.findings == []
    assert ro.is_demo is True


def test_reviewer_output_roundtrip():
    ro = ReviewerOutput(**VALID_REVIEWER_OUTPUT)
    assert _roundtrip(ro) == ro


def test_reviewer_output_extra_field_rejected():
    with pytest.raises(ValidationError):
        ReviewerOutput(**{**VALID_REVIEWER_OUTPUT, "model": "gpt-4o"})


# ---------------------------------------------------------------------------
# CoordinatorReport
# ---------------------------------------------------------------------------

VALID_COORDINATOR_REPORT = dict(
    findings=[VALID_FINDING],
    overall_risk="high",
    summary="The PR introduces a division-by-zero bug and uses eval().",
    is_demo=False,
)


def test_coordinator_report_valid():
    cr = CoordinatorReport(**VALID_COORDINATOR_REPORT)
    assert cr.overall_risk == "high"
    assert cr.is_demo is False
    assert len(cr.findings) == 1


def test_coordinator_report_all_risk_levels():
    for level in ("critical", "high", "medium", "low"):
        cr = CoordinatorReport(**{**VALID_COORDINATOR_REPORT, "overall_risk": level})
        assert cr.overall_risk == level


def test_coordinator_report_roundtrip():
    cr = CoordinatorReport(**VALID_COORDINATOR_REPORT)
    assert _roundtrip(cr) == cr


def test_coordinator_report_invalid_risk():
    with pytest.raises(ValidationError):
        CoordinatorReport(**{**VALID_COORDINATOR_REPORT, "overall_risk": "info"})


def test_coordinator_report_extra_field_rejected():
    with pytest.raises(ValidationError):
        CoordinatorReport(**{**VALID_COORDINATOR_REPORT, "score": 42})


# ---------------------------------------------------------------------------
# PatchResult
# ---------------------------------------------------------------------------

VALID_PATCH_RESULT = dict(
    patch_diff="--- a/calculator.py\n+++ b/calculator.py\n@@ -33,7 +33,8 @@\n",
    explanation="Added zero-divisor guard and replaced eval() with ast.literal_eval().",
    is_demo=False,
)


def test_patch_result_valid():
    pr = PatchResult(**VALID_PATCH_RESULT)
    assert pr.patch_diff.startswith("---")
    assert pr.is_demo is False


def test_patch_result_empty_diff():
    pr = PatchResult(patch_diff="", explanation="No changes.", is_demo=True)
    assert pr.patch_diff == ""


def test_patch_result_roundtrip():
    pr = PatchResult(**VALID_PATCH_RESULT)
    assert _roundtrip(pr) == pr


def test_patch_result_extra_field_rejected():
    with pytest.raises(ValidationError):
        PatchResult(**{**VALID_PATCH_RESULT, "author": "bot"})


# ---------------------------------------------------------------------------
# TestRunResult
# ---------------------------------------------------------------------------

VALID_TEST_RUN_RESULT = dict(
    passed=9,
    failed=1,
    errors=0,
    output="9 passed, 1 failed in 0.22s",
)


def test_test_run_result_valid():
    tr = TestRunResult(**VALID_TEST_RUN_RESULT)
    assert tr.passed == 9
    assert tr.failed == 1
    assert tr.errors == 0


def test_test_run_result_roundtrip():
    tr = TestRunResult(**VALID_TEST_RUN_RESULT)
    assert _roundtrip(tr) == tr


def test_test_run_result_extra_field_rejected():
    with pytest.raises(ValidationError):
        TestRunResult(**{**VALID_TEST_RUN_RESULT, "duration": 0.22})


# ---------------------------------------------------------------------------
# ReReviewResult
# ---------------------------------------------------------------------------

VALID_REREVIEW_RESULT = dict(
    previous_risk="high",
    new_risk="low",
    risk_decreased=True,
    summary="After the patch, no critical or high-severity findings remain.",
)


def test_rereview_result_valid():
    rr = ReReviewResult(**VALID_REREVIEW_RESULT)
    assert rr.previous_risk == "high"
    assert rr.new_risk == "low"
    assert rr.risk_decreased is True


def test_rereview_result_risk_not_decreased():
    rr = ReReviewResult(**{**VALID_REREVIEW_RESULT, "new_risk": "high", "risk_decreased": False})
    assert rr.risk_decreased is False


def test_rereview_result_roundtrip():
    rr = ReReviewResult(**VALID_REREVIEW_RESULT)
    assert _roundtrip(rr) == rr


def test_rereview_result_invalid_risk_level():
    with pytest.raises(ValidationError):
        ReReviewResult(**{**VALID_REREVIEW_RESULT, "new_risk": "none"})


def test_rereview_result_extra_field_rejected():
    with pytest.raises(ValidationError):
        ReReviewResult(**{**VALID_REREVIEW_RESULT, "reviewed_by": "gpt-4o"})
