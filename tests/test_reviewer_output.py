"""
test_reviewer_output.py — tests for mergeproof/reviewer.py and demo_mode.py.

These tests:
1. Validate every demo-mode ReviewerOutput through the schema (no invented fields).
2. Check that all four roles are present in demo mode output.
3. Verify evidence strings are non-empty and all findings have required fields.
4. Test the parse-error fallback path (_parse_error_output).
5. Test run_all_reviewers in DEMO_MODE via the module's public interface.
6. Test _build_prompt structure without making LLM calls.
"""

import os
import sys

import pytest
from pydantic import ValidationError

# Force DEMO_MODE for all tests in this file so no LLM calls are made.
os.environ["DEMO_MODE"] = "true"

# Re-import after setting env var (module may already be cached; reload it)
import importlib

import mergeproof.reviewer as reviewer_mod
importlib.reload(reviewer_mod)

from mergeproof.demo_mode import (
    CORRECTNESS_OUTPUT,
    DEMO_REVIEWER_OUTPUTS,
    PERFORMANCE_OUTPUT,
    SECURITY_OUTPUT,
    TEST_COVERAGE_OUTPUT,
)
from mergeproof.reviewer import _build_prompt, _parse_error_output, run_all_reviewers
from mergeproof.schemas import Finding, ReviewerOutput

# ---------------------------------------------------------------------------
# Demo-mode outputs: schema correctness
# ---------------------------------------------------------------------------

DEMO_DIFF = "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,1 +1,1 @@\n-pass\n+return 1"
DEMO_FILES = {"calculator.py": "def f(): return 1"}


@pytest.mark.parametrize("output", DEMO_REVIEWER_OUTPUTS)
def test_demo_output_is_valid_schema(output):
    """Each demo output must pass model_validate without error."""
    validated = ReviewerOutput.model_validate(output.model_dump())
    assert validated == output


@pytest.mark.parametrize("output", DEMO_REVIEWER_OUTPUTS)
def test_demo_output_is_demo_flag(output):
    assert output.is_demo is True


@pytest.mark.parametrize("output", DEMO_REVIEWER_OUTPUTS)
def test_demo_output_has_findings(output):
    assert len(output.findings) >= 2, (
        f"{output.reviewer_name} must have at least 2 findings"
    )


@pytest.mark.parametrize("output", DEMO_REVIEWER_OUTPUTS)
def test_demo_output_evidence_nonempty(output):
    for f in output.findings:
        assert f.evidence.strip(), (
            f"{output.reviewer_name}: finding at line {f.line} has empty evidence"
        )


@pytest.mark.parametrize("output", DEMO_REVIEWER_OUTPUTS)
def test_demo_output_roundtrip_json(output):
    import json
    reconstructed = ReviewerOutput.model_validate(
        json.loads(output.model_dump_json())
    )
    assert reconstructed == output


# ---------------------------------------------------------------------------
# Demo-mode outputs: four roles present
# ---------------------------------------------------------------------------

def test_all_four_roles_present():
    roles = {o.reviewer_name for o in DEMO_REVIEWER_OUTPUTS}
    assert roles == {"correctness", "security", "performance", "test_coverage"}


def test_correctness_role():
    assert CORRECTNESS_OUTPUT.reviewer_name == "correctness"


def test_security_role():
    assert SECURITY_OUTPUT.reviewer_name == "security"


def test_performance_role():
    assert PERFORMANCE_OUTPUT.reviewer_name == "performance"


def test_test_coverage_role():
    assert TEST_COVERAGE_OUTPUT.reviewer_name == "test_coverage"


# ---------------------------------------------------------------------------
# run_all_reviewers in DEMO_MODE
# ---------------------------------------------------------------------------

def test_run_all_reviewers_demo_returns_four(monkeypatch):
    """In DEMO_MODE run_all_reviewers must return exactly four outputs."""
    # Ensure DEMO_MODE is active (already set via env, but be explicit)
    monkeypatch.setattr(reviewer_mod, "DEMO_MODE", True)
    outputs = run_all_reviewers(DEMO_DIFF, DEMO_FILES)
    assert len(outputs) == 4


def test_run_all_reviewers_demo_all_valid(monkeypatch):
    monkeypatch.setattr(reviewer_mod, "DEMO_MODE", True)
    outputs = run_all_reviewers(DEMO_DIFF, DEMO_FILES)
    for o in outputs:
        ReviewerOutput.model_validate(o.model_dump())


def test_run_all_reviewers_demo_is_demo_flag(monkeypatch):
    monkeypatch.setattr(reviewer_mod, "DEMO_MODE", True)
    outputs = run_all_reviewers(DEMO_DIFF, DEMO_FILES)
    assert all(o.is_demo for o in outputs)


def test_run_all_reviewers_returns_list(monkeypatch):
    monkeypatch.setattr(reviewer_mod, "DEMO_MODE", True)
    result = run_all_reviewers(DEMO_DIFF, DEMO_FILES)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Parse-error fallback path
# ---------------------------------------------------------------------------

def test_parse_error_output_valid_schema():
    """_parse_error_output must itself produce a schema-valid ReviewerOutput."""
    out = _parse_error_output("security", "test error message")
    ReviewerOutput.model_validate(out.model_dump())


def test_parse_error_output_severity_is_info():
    out = _parse_error_output("performance", "boom")
    assert len(out.findings) == 1
    assert out.findings[0].severity == "info"


def test_parse_error_output_is_demo_false():
    out = _parse_error_output("correctness", "boom")
    assert out.is_demo is False


def test_parse_error_output_message_in_explanation():
    msg = "LLM returned non-JSON: Expecting value at line 1"
    out = _parse_error_output("test_coverage", msg)
    assert msg in out.findings[0].explanation


# ---------------------------------------------------------------------------
# _build_prompt structure
# ---------------------------------------------------------------------------

def test_build_prompt_returns_two_messages():
    msgs = _build_prompt("security", DEMO_DIFF, DEMO_FILES)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_build_prompt_system_contains_role():
    msgs = _build_prompt("security", DEMO_DIFF, {})
    assert "security" in msgs[0]["content"]


def test_build_prompt_system_contains_no_markdown_fence_rule():
    msgs = _build_prompt("correctness", DEMO_DIFF, {})
    assert "markdown fences" in msgs[0]["content"]


def test_build_prompt_system_contains_verbatim_rule():
    msgs = _build_prompt("performance", DEMO_DIFF, {})
    assert "verbatim" in msgs[0]["content"]


def test_build_prompt_user_contains_diff():
    msgs = _build_prompt("test_coverage", DEMO_DIFF, {})
    assert DEMO_DIFF in msgs[1]["content"]


def test_build_prompt_user_contains_repo_files():
    msgs = _build_prompt("correctness", DEMO_DIFF, {"myfile.py": "x = 1"})
    assert "myfile.py" in msgs[1]["content"]
    assert "x = 1" in msgs[1]["content"]


def test_build_prompt_no_repo_files_no_snapshot_section():
    msgs = _build_prompt("correctness", DEMO_DIFF, {})
    assert "repository snapshot" not in msgs[1]["content"]
