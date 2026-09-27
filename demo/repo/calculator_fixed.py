"""
calculator_fixed.py — the PATCHED version of calculator.py.

This file is the "after" state produced by applying DEMO_PATCH_RESULT
to the original demo/repo/calculator.py.  It exists solely as a test
fixture for demo/tests_fixed/ — it must NEVER replace the intentionally
flawed calculator.py in demo/repo/.

Changes from the original:
  1. divide()   — raises ValueError("divisor cannot be zero") when b == 0
  2. evaluate() — uses ast.literal_eval() instead of eval()
  3. sum_range() — uses O(1) arithmetic formula n*(n+1)//2
"""

import ast


def add(a: float, b: float) -> float:
    """Return a + b."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return a - b."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return a * b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return a / b.

    Raises ValueError when b == 0 (fixed: was ZeroDivisionError).
    """
    if b == 0:
        raise ValueError("divisor cannot be zero")
    return a / b


def evaluate(expression: str) -> float:
    """Evaluate an arithmetic expression string and return the result.

    Uses ast.literal_eval() — safe against arbitrary code execution.
    Only Python numeric literals are supported (e.g. '42', '3.14').
    Raises ValueError for non-literal or invalid input.
    """
    try:
        return float(ast.literal_eval(expression))
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"Invalid expression: {expression!r}") from exc


def sum_range(n: int) -> int:
    """Return the sum of integers from 1 to n (inclusive).

    Uses O(1) arithmetic formula (fixed: was O(n) two-loop implementation).
    Returns 0 for n < 1.
    """
    if n < 1:
        return 0
    return n * (n + 1) // 2
