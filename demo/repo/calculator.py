"""
calculator.py — simple calculator module.

NOTE: This file intentionally contains three classes of issues for the
MergeProof demo:

  1. CORRECTNESS  — divide() does not guard against division by zero.
  2. SECURITY     — evaluate() uses eval() to parse user-supplied expressions.
  3. PERFORMANCE  — sum_range() rebuilds the list on every call instead of
                    using the O(1) arithmetic formula or the built-in sum().
"""


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

    BUG: raises ZeroDivisionError when b == 0 instead of returning a
    meaningful error or raising a domain-specific exception.
    """
    # Missing guard: if b == 0: raise ValueError("divisor cannot be zero")
    return a / b


def evaluate(expression: str) -> float:
    """Evaluate an arithmetic expression string and return the result.

    SECURITY: passes unsanitised user input directly to eval(), which
    allows arbitrary code execution (e.g. evaluate("__import__('os').system('rm -rf /')")).
    """
    return eval(expression)  # noqa: S307  (intentional security smell for demo)


def sum_range(n: int) -> int:
    """Return the sum of integers from 1 to n (inclusive).

    PERFORMANCE: builds a full list in memory on every call instead of
    using the O(1) formula n*(n+1)//2 or the built-in sum(range(1, n+1)).
    """
    numbers = []
    for i in range(1, n + 1):
        numbers.append(i)   # redundant list build — should just accumulate or use formula
    total = 0
    for num in numbers:     # second pass over the list — unnecessary
        total += num
    return total
