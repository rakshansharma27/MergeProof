"""
test_test_runner.py — tests for mergeproof/test_runner.py.

Covers:
 1. run_tests("demo/tests")  → TestRunResult with passed >= 1, failed >= 1
    (the intentional demo bug means 1 test always fails before the patch)
 2. run_tests("demo/tests_fixed") → TestRunResult with passed >= 1, failed == 0
    (after the patch every test should pass)
 3. run_tests with a nonexistent directory → TestRunResult returned, never raises
 4. TestRunResult fields are correct types
 5. Output string is non-empty and contains pytest summary text
 6. Subprocess timeout / launch failure path returns TestRunResult (mocked)
"""

import os
import sys

import pytest

from mergeproof.schemas import TestRunResult
from mergeproof.test_runner import run_tests


# ---------------------------------------------------------------------------
# Live runs against the demo fixture directories
# ---------------------------------------------------------------------------

def test_run_tests_pre_patch_passes_some():
    """Before the patch: at least 1 test passes in demo/tests/."""
    result = run_tests("demo/tests")
    assert isinstance(result, TestRunResult)
    assert result.passed >= 1, f"Expected >=1 passed, got {result.passed}"


def test_run_tests_pre_patch_fails_some():
    """Before the patch: at least 1 test fails (the intentional demo bug)."""
    result = run_tests("demo/tests")
    assert result.failed >= 1, (
        f"Expected >=1 failed (intentional bug), got {result.failed}. "
        f"Output:\n{result.output}"
    )


def test_run_tests_post_patch_all_pass():
    """After the patch: all tests in demo/tests_fixed/ pass."""
    result = run_tests("demo/tests_fixed")
    assert isinstance(result, TestRunResult)
    assert result.failed == 0, (
        f"Expected 0 failures after patch, got {result.failed}. "
        f"Output:\n{result.output}"
    )
    assert result.passed >= 1, f"Expected >=1 passed after patch, got {result.passed}"


def test_run_tests_output_nonempty():
    result = run_tests("demo/tests")
    assert result.output.strip(), "Output should contain pytest summary text"


def test_run_tests_output_contains_passed():
    result = run_tests("demo/tests")
    assert "passed" in result.output.lower()


def test_run_tests_counts_are_ints():
    result = run_tests("demo/tests")
    assert isinstance(result.passed, int)
    assert isinstance(result.failed, int)
    assert isinstance(result.errors, int)


# ---------------------------------------------------------------------------
# Edge case: nonexistent directory — must return TestRunResult, never raise
# ---------------------------------------------------------------------------

def test_run_tests_nonexistent_dir_does_not_raise():
    result = run_tests("nonexistent/path/to/tests")
    assert isinstance(result, TestRunResult)


def test_run_tests_nonexistent_dir_output_nonempty():
    result = run_tests("nonexistent/path/to/tests")
    assert result.output.strip(), "Should capture pytest error output"


# ---------------------------------------------------------------------------
# Subprocess failure path (mocked — no real subprocess)
# ---------------------------------------------------------------------------

def test_run_tests_timeout_returns_testrunresult(monkeypatch):
    """A subprocess.TimeoutExpired must be caught and returned as TestRunResult."""
    import subprocess
    import unittest.mock as mock
    from mergeproof import test_runner as tr_mod

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=120)

    monkeypatch.setattr(tr_mod.subprocess, "run", fake_run)
    result = run_tests("demo/tests")
    assert isinstance(result, TestRunResult)
    assert result.errors >= 1
    assert "timed out" in result.output.lower()


def test_run_tests_launch_failure_returns_testrunresult(monkeypatch):
    """Any other subprocess exception must also be caught."""
    import unittest.mock as mock
    from mergeproof import test_runner as tr_mod

    def fake_run(*args, **kwargs):
        raise OSError("executable not found")

    monkeypatch.setattr(tr_mod.subprocess, "run", fake_run)
    result = run_tests("demo/tests")
    assert isinstance(result, TestRunResult)
    assert result.errors >= 1
    assert "executable not found" in result.output or "Failed to launch" in result.output


# ---------------------------------------------------------------------------
# Schema round-trip for TestRunResult returned by run_tests
# ---------------------------------------------------------------------------

def test_run_tests_result_schema_roundtrip():
    import json
    result = run_tests("demo/tests")
    reconstructed = TestRunResult.model_validate(
        json.loads(result.model_dump_json())
    )
    assert reconstructed == result
