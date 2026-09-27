"""
test_calculator_fixed.py — full test suite against the PATCHED calculator.

This file reflects the state of calculator.py AFTER applying the suggested
patch from demo/sample.diff fix.  It is used by Sub-Task 6 (test_runner) to
demonstrate that running tests after the patch shows a green suite.

The patched calculator (demo/repo/calculator_fixed.py) must exist alongside
this file.  It is NOT the original flawed calculator.py — that file is
intentionally preserved with bugs in demo/repo/calculator.py.
"""

import sys
import os

# Make demo/repo importable when pytest is run from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "repo"))

import pytest

from calculator_fixed import add, subtract, multiply, divide, evaluate, sum_range  # noqa: E402


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_positive():
    assert add(2, 3) == 5

def test_add_negative():
    assert add(-1, -1) == -2

def test_add_floats():
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
# divide — now includes the zero-divisor edge case (patch applied)
# ---------------------------------------------------------------------------

def test_divide_basic():
    assert divide(10, 2) == 5.0

def test_divide_float_result():
    assert divide(7, 2) == 3.5

def test_divide_by_zero_raises_value_error():
    """After the patch, divide() must raise ValueError, not ZeroDivisionError."""
    with pytest.raises(ValueError, match="divisor cannot be zero"):
        divide(10, 0)


# ---------------------------------------------------------------------------
# evaluate — now uses ast.literal_eval (safe, literals only)
# ---------------------------------------------------------------------------
# ast.literal_eval only parses Python literals: integers, floats, strings,
# etc.  It does NOT evaluate arithmetic expressions like "2+2".  The patched
# evaluate() therefore raises ValueError for any expression containing
# operators.  This is the intended safe behaviour.

def test_evaluate_integer_literal():
    assert evaluate("42") == pytest.approx(42.0)

def test_evaluate_float_literal():
    assert evaluate("3.14") == pytest.approx(3.14)

def test_evaluate_rejects_arithmetic():
    """"2+2" is not a literal — ast.literal_eval raises, evaluate wraps as ValueError."""
    with pytest.raises(ValueError):
        evaluate("2+2")

def test_evaluate_rejects_dangerous_input():
    """Dangerous eval payloads must raise ValueError, not execute code."""
    with pytest.raises(ValueError):
        evaluate("__import__('os').system('echo pwned')")


# ---------------------------------------------------------------------------
# sum_range — now uses O(1) formula
# ---------------------------------------------------------------------------

def test_sum_range_zero():
    assert sum_range(0) == 0

def test_sum_range_one():
    assert sum_range(1) == 1

def test_sum_range_small():
    assert sum_range(5) == 15   # 1+2+3+4+5

def test_sum_range_large():
    assert sum_range(100) == 5050
