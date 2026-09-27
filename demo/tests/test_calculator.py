"""
test_calculator.py — partial test suite for the calculator module.

Coverage is intentionally incomplete for the MergeProof demo:
  - add, subtract, multiply: happy-path only ✓
  - divide: only tests the happy path — MISSING zero-divisor test ✗
  - evaluate: NOT tested at all ✗
  - sum_range: NOT tested at all ✗
"""

import sys
import os

# Make demo/repo importable when pytest is run from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "repo"))

from calculator import add, subtract, multiply, divide  # noqa: E402


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, -1) == -2


def test_add_floats():
    import pytest
    assert add(0.1, 0.2) == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# subtract
# ---------------------------------------------------------------------------

def test_subtract_basic():
    assert subtract(10, 4) == 6


def test_subtract_negative_result():
    assert subtract(3, 7) == -4


# ---------------------------------------------------------------------------
# multiply
# ---------------------------------------------------------------------------

def test_multiply_positive():
    assert multiply(3, 4) == 12


def test_multiply_by_zero():
    assert multiply(99, 0) == 0


# ---------------------------------------------------------------------------
# divide — happy path only (missing zero-divisor coverage)
# ---------------------------------------------------------------------------

def test_divide_basic():
    assert divide(10, 2) == 5.0


def test_divide_float_result():
    assert divide(7, 2) == 3.5


def test_divide_by_zero():
    """This test INTENTIONALLY FAILS to demonstrate the correctness gap.

    divide() currently raises ZeroDivisionError instead of the expected
    ValueError.  The MergeProof reviewer should catch this and recommend
    adding a guard in divide().
    """
    # Expect a ValueError — but the current implementation raises ZeroDivisionError,
    # so this test fails, proving the bug is real.
    import pytest
    with pytest.raises(ValueError, match="divisor cannot be zero"):
        divide(10, 0)
