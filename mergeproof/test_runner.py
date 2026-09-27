"""
test_runner.py — run pytest on a target directory and return structured results.

Public API
----------
run_tests(test_dir) -> TestRunResult

Uses subprocess so pytest never interferes with Streamlit's own process.
Always returns a TestRunResult — never raises an unhandled exception.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from mergeproof.schemas import TestRunResult

# ---------------------------------------------------------------------------
# Regex patterns for the pytest summary line
# ---------------------------------------------------------------------------

_RE_PASSED = re.compile(r"(\d+) passed")
_RE_FAILED = re.compile(r"(\d+) failed")
_RE_ERROR  = re.compile(r"(\d+) error")


def run_tests(test_dir: str = "demo/tests") -> TestRunResult:
    """Run pytest on *test_dir* and return a TestRunResult.

    Parameters
    ----------
    test_dir:
        Path to the directory containing the tests to run.
        Relative paths are resolved from the current working directory
        (i.e. the project root when called from Streamlit or the CLI).

    Returns
    -------
    TestRunResult
        Always returned — never raises.  On subprocess failure the raw
        stderr/stdout is captured in the ``output`` field.
    """
    # Use sys.executable so the subprocess inherits the same virtual-env Python
    # as the main process.  This avoids "pytest not found" errors when pytest
    # is installed in a venv but not on PATH.
    cmd = [sys.executable, "-m", "pytest", test_dir, "--tb=short", "-q"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            # Never let a hung test suite block the UI indefinitely.
            timeout=120,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        return TestRunResult(
            passed=0,
            failed=0,
            errors=1,
            output=f"pytest timed out after 120 s: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return TestRunResult(
            passed=0,
            failed=0,
            errors=1,
            output=f"Failed to launch pytest: {exc}",
        )

    # Parse the summary counts from the last few lines of output
    passed = int(m.group(1)) if (m := _RE_PASSED.search(output)) else 0
    failed = int(m.group(1)) if (m := _RE_FAILED.search(output)) else 0
    errors = int(m.group(1)) if (m := _RE_ERROR.search(output))  else 0

    return TestRunResult(
        passed=passed,
        failed=failed,
        errors=errors,
        output=output,
    )
