"""
test_patch_generator.py — tests for mergeproof/patch_generator.py and
                          the DEMO_PATCH_RESULT in demo_mode.py.

Covers:
 1. DEMO_PATCH_RESULT: schema validity, is_demo flag, patch_diff invariant
 2. generate_patch in DEMO_MODE: returns DEMO_PATCH_RESULT, is_demo=True
 3. generate_patch with is_demo report: also returns demo result
 4. _build_patch_prompt: structure, required rules in system prompt
 5. _error_result: schema validity, patch_diff is always "", is_demo=False
 6. Live-mode parse-error fallback (no real LLM call — client stubbed)
"""

import json
import os

import pytest

os.environ["DEMO_MODE"] = "true"

import importlib

import mergeproof.patch_generator as pg_mod
importlib.reload(pg_mod)

from mergeproof.demo_mode import DEMO_PATCH_RESULT
from mergeproof.patch_generator import (
    _build_patch_prompt,
    _error_result,
    generate_patch,
)
from mergeproof.schemas import CoordinatorReport, Finding, PatchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_finding(**kwargs) -> Finding:
    defaults = dict(
        severity="high",
        category="correctness",
        file="calculator.py",
        line=36,
        evidence="    return a / b",
        explanation="div by zero",
        recommendation="add guard",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def make_report(findings=None, overall_risk="high", is_demo=False) -> CoordinatorReport:
    return CoordinatorReport(
        findings=findings or [make_finding()],
        overall_risk=overall_risk,
        summary="test summary",
        is_demo=is_demo,
    )


SAMPLE_DIFF = "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,1 +1,1 @@\n-x\n+y"
SAMPLE_FILES = {"calculator.py": "def divide(a, b):\n    return a / b\n"}


# ---------------------------------------------------------------------------
# DEMO_PATCH_RESULT schema and invariants
# ---------------------------------------------------------------------------

def test_demo_patch_result_is_valid_schema():
    validated = PatchResult.model_validate(DEMO_PATCH_RESULT.model_dump())
    assert validated == DEMO_PATCH_RESULT


def test_demo_patch_result_is_demo_true():
    assert DEMO_PATCH_RESULT.is_demo is True


def test_demo_patch_result_patch_diff_starts_with_dashes():
    assert DEMO_PATCH_RESULT.patch_diff.startswith("---"), (
        "patch_diff must start with '---'"
    )


def test_demo_patch_result_explanation_nonempty():
    assert DEMO_PATCH_RESULT.explanation.strip()


def test_demo_patch_result_roundtrip():
    reconstructed = PatchResult.model_validate(
        json.loads(DEMO_PATCH_RESULT.model_dump_json())
    )
    assert reconstructed == DEMO_PATCH_RESULT


def test_demo_patch_result_explanation_mentions_all_three_fixes():
    exp = DEMO_PATCH_RESULT.explanation.lower()
    assert "divide" in exp or "zero" in exp, "Should mention divide/zero fix"
    assert "eval" in exp, "Should mention eval fix"
    assert "sum_range" in exp or "o(1)" in exp or "formula" in exp, (
        "Should mention sum_range / O(1) fix"
    )


# ---------------------------------------------------------------------------
# generate_patch — DEMO_MODE
# ---------------------------------------------------------------------------

def test_generate_patch_demo_mode_returns_demo_result(monkeypatch):
    monkeypatch.setattr(pg_mod, "DEMO_MODE", True)
    result = generate_patch(make_report(), SAMPLE_DIFF, SAMPLE_FILES)
    assert result is DEMO_PATCH_RESULT


def test_generate_patch_demo_mode_is_demo_true(monkeypatch):
    monkeypatch.setattr(pg_mod, "DEMO_MODE", True)
    result = generate_patch(make_report(), SAMPLE_DIFF, SAMPLE_FILES)
    assert result.is_demo is True


def test_generate_patch_demo_report_triggers_demo_path(monkeypatch):
    """Even with DEMO_MODE=False, a report with is_demo=True returns demo result."""
    monkeypatch.setattr(pg_mod, "DEMO_MODE", False)
    report = make_report(is_demo=True)
    result = generate_patch(report, SAMPLE_DIFF, SAMPLE_FILES)
    assert result is DEMO_PATCH_RESULT


def test_generate_patch_returns_patch_result_type(monkeypatch):
    monkeypatch.setattr(pg_mod, "DEMO_MODE", True)
    result = generate_patch(make_report(), SAMPLE_DIFF, {})
    assert isinstance(result, PatchResult)


# ---------------------------------------------------------------------------
# generate_patch — live-mode error fallback (no real LLM calls)
# ---------------------------------------------------------------------------

def test_generate_patch_llm_failure_returns_error_result(monkeypatch):
    """If the LLM call raises, generate_patch returns a PatchResult with patch_diff=''."""
    monkeypatch.setattr(pg_mod, "DEMO_MODE", False)

    def fake_create(**kwargs):
        raise RuntimeError("network error")

    # Stub the openai import chain
    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("network error")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    import unittest.mock as mock
    monkeypatch.setattr(pg_mod, "_MODEL", "stub-model")
    with mock.patch("mergeproof.patch_generator.OpenAI", return_value=FakeClient()):
        # Need to un-mock the DEMO_MODE branch guard too
        result = generate_patch(make_report(is_demo=False), SAMPLE_DIFF, {})

    assert isinstance(result, PatchResult)
    assert result.patch_diff == ""
    assert "network error" in result.explanation or "LLM call failed" in result.explanation


def test_generate_patch_bad_json_returns_error_result(monkeypatch):
    """If the LLM returns non-JSON, generate_patch returns PatchResult with patch_diff=''."""
    monkeypatch.setattr(pg_mod, "DEMO_MODE", False)

    class FakeChoice:
        message = type("M", (), {"content": "not valid json }{{"})()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    import unittest.mock as mock
    with mock.patch("mergeproof.patch_generator.OpenAI", return_value=FakeClient()):
        result = generate_patch(make_report(is_demo=False), SAMPLE_DIFF, {})

    assert result.patch_diff == ""
    assert result.is_demo is False


def test_generate_patch_valid_json_normalised(monkeypatch):
    """Valid JSON from LLM with correct patch_diff is returned as PatchResult."""
    monkeypatch.setattr(pg_mod, "DEMO_MODE", False)

    good_payload = json.dumps({
        "patch_diff": "--- a/calculator.py\n+++ b/calculator.py\n@@ -1 +1 @@\n-x\n+y",
        "explanation": "Fixed the bug.",
    })

    class FakeChoice:
        message = type("M", (), {"content": good_payload})()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    import unittest.mock as mock
    with mock.patch("mergeproof.patch_generator.OpenAI", return_value=FakeClient()):
        result = generate_patch(make_report(is_demo=False), SAMPLE_DIFF, {})

    assert isinstance(result, PatchResult)
    assert result.patch_diff.startswith("---")
    assert result.is_demo is False


# ---------------------------------------------------------------------------
# _error_result
# ---------------------------------------------------------------------------

def test_error_result_valid_schema():
    r = _error_result("something went wrong")
    PatchResult.model_validate(r.model_dump())


def test_error_result_patch_diff_is_empty_string():
    r = _error_result("boom")
    assert r.patch_diff == ""


def test_error_result_is_demo_false():
    r = _error_result("boom")
    assert r.is_demo is False


def test_error_result_message_in_explanation():
    r = _error_result("LLM call failed: timeout")
    assert "LLM call failed: timeout" in r.explanation


# ---------------------------------------------------------------------------
# _build_patch_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_returns_two_messages():
    msgs = _build_patch_prompt(make_report(), SAMPLE_DIFF, {})
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_build_prompt_system_no_markdown_fences_rule():
    msgs = _build_patch_prompt(make_report(), SAMPLE_DIFF, {})
    assert "markdown" in msgs[0]["content"].lower() or "fences" in msgs[0]["content"].lower()


def test_build_prompt_system_no_invented_files_rule():
    msgs = _build_patch_prompt(make_report(), SAMPLE_DIFF, {})
    assert "invent" in msgs[0]["content"].lower() or "not present" in msgs[0]["content"].lower()


def test_build_prompt_user_contains_diff():
    msgs = _build_patch_prompt(make_report(), SAMPLE_DIFF, {})
    assert SAMPLE_DIFF in msgs[1]["content"]


def test_build_prompt_user_contains_findings():
    report = make_report(findings=[make_finding(evidence="return a / b")])
    msgs = _build_patch_prompt(report, SAMPLE_DIFF, {})
    assert "return a / b" in msgs[1]["content"]


def test_build_prompt_user_contains_repo_files():
    msgs = _build_patch_prompt(make_report(), SAMPLE_DIFF, SAMPLE_FILES)
    assert "calculator.py" in msgs[1]["content"]
    assert "def divide" in msgs[1]["content"]


def test_build_prompt_no_repo_files_no_snapshot():
    msgs = _build_patch_prompt(make_report(), SAMPLE_DIFF, {})
    assert "repository snapshot" not in msgs[1]["content"]
