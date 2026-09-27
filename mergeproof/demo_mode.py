"""
demo_mode.py — pre-computed DEMO_MODE reviewer outputs and coordinator report.

All objects have is_demo=True.  Evidence strings are verbatim lines from
demo/sample.diff so that the "evidence must match the diff" rule holds even
in demo mode.  These are clearly synthetic; they are never presented as live
AI output.
"""

from mergeproof.schemas import CoordinatorReport, Finding, PatchResult, ReReviewResult, ReviewerOutput

# ---------------------------------------------------------------------------
# Correctness reviewer
# ---------------------------------------------------------------------------

CORRECTNESS_OUTPUT = ReviewerOutput(
    reviewer_name="correctness",
    is_demo=True,
    findings=[
        Finding(
            severity="high",
            category="correctness",
            file="calculator.py",
            line=46,
            evidence="    return a / b",
            explanation=(
                "divide() performs a / b without checking whether b is zero.  "
                "When b == 0 Python raises ZeroDivisionError, which is an "
                "unhandled runtime crash rather than a meaningful domain error."
            ),
            recommendation=(
                "Add a guard before the division: "
                "`if b == 0: raise ValueError('divisor cannot be zero')`.  "
                "Update callers to catch ValueError instead of the bare "
                "ZeroDivisionError."
            ),
        ),
        Finding(
            severity="medium",
            category="correctness",
            file="calculator.py",
            line=None,
            evidence="def divide(a: float, b: float) -> float:",
            explanation=(
                "The public API accepts any float for both arguments but "
                "documents no contract for the zero-divisor case, leaving "
                "callers without a clear error-handling path."
            ),
            recommendation=(
                "Document the ValueError in the docstring and add it to the "
                "function's type signature or a custom exception class."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Security reviewer
# ---------------------------------------------------------------------------

SECURITY_OUTPUT = ReviewerOutput(
    reviewer_name="security",
    is_demo=True,
    findings=[
        Finding(
            severity="critical",
            category="security",
            file="calculator.py",
            line=55,
            evidence="    return eval(expression)  # noqa: S307  (intentional security smell for demo)",
            explanation=(
                "evaluate() passes unsanitised user input directly to the "
                "built-in eval().  An attacker can supply any Python expression, "
                "including `__import__('os').system('rm -rf /')`, enabling "
                "arbitrary code execution on the server."
            ),
            recommendation=(
                "Replace eval() with ast.literal_eval() for safe evaluation of "
                "literal expressions, or use a dedicated expression-parser library "
                "(e.g. simpleeval).  Never pass user-controlled strings to eval()."
            ),
        ),
        Finding(
            severity="high",
            category="security",
            file="calculator.py",
            line=49,
            evidence="def evaluate(expression: str) -> float:",
            explanation=(
                "The function accepts an untyped string with no length limit, "
                "no allow-list, and no sandboxing.  Even replacing eval() with "
                "ast.literal_eval() would need input validation to prevent "
                "denial-of-service via extremely large inputs."
            ),
            recommendation=(
                "Validate the expression against a strict character allow-list "
                "(digits, operators, parentheses, decimal point) before parsing, "
                "and enforce a maximum length."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Performance reviewer
# ---------------------------------------------------------------------------

PERFORMANCE_OUTPUT = ReviewerOutput(
    reviewer_name="performance",
    is_demo=True,
    findings=[
        Finding(
            severity="medium",
            category="performance",
            file="calculator.py",
            line=66,
            evidence="        numbers.append(i)   # redundant list build — should just accumulate or use formula",
            explanation=(
                "sum_range() allocates a full list of n integers in the first "
                "loop, then iterates over it a second time to accumulate the "
                "total.  This is O(n) time and O(n) space when both can be O(1)."
            ),
            recommendation=(
                "Use the arithmetic formula `return n * (n + 1) // 2`, or at "
                "minimum replace the two loops with `return sum(range(1, n + 1))` "
                "to avoid the intermediate list allocation."
            ),
        ),
        Finding(
            severity="low",
            category="performance",
            file="calculator.py",
            line=68,
            evidence="    for num in numbers:     # second pass over the list — unnecessary",
            explanation=(
                "The second for-loop iterates over the already-built list purely "
                "to sum it.  The first loop could accumulate directly, eliminating "
                "both the list and the second pass."
            ),
            recommendation=(
                "Merge the two loops into a single accumulation loop, or use the "
                "O(1) formula as described above."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Test-coverage reviewer
# ---------------------------------------------------------------------------

TEST_COVERAGE_OUTPUT = ReviewerOutput(
    reviewer_name="test_coverage",
    is_demo=True,
    findings=[
        Finding(
            severity="high",
            category="test_coverage",
            file="calculator.py",
            line=33,
            evidence="def divide(a: float, b: float) -> float:",
            explanation=(
                "The test suite has no test for divide(0, 0) or divide(x, 0).  "
                "The zero-divisor code path is completely untested, so the "
                "ZeroDivisionError bug cannot be caught by CI."
            ),
            recommendation=(
                "Add `test_divide_by_zero` that asserts a ValueError is raised "
                "when b == 0, and `test_divide_negative_divisor` for the b < 0 "
                "edge case."
            ),
        ),
        Finding(
            severity="high",
            category="test_coverage",
            file="calculator.py",
            line=49,
            evidence="def evaluate(expression: str) -> float:",
            explanation=(
                "evaluate() has zero test coverage.  Neither the happy path nor "
                "the malicious-input path is exercised, leaving the critical "
                "security flaw undetected by the test suite."
            ),
            recommendation=(
                "Add tests for: valid expressions ('2+2' → 4.0), nested "
                "expressions ('(3+1)*2' → 8.0), and rejection of dangerous "
                "inputs such as `__import__('os')`."
            ),
        ),
        Finding(
            severity="medium",
            category="test_coverage",
            file="calculator.py",
            line=58,
            evidence="def sum_range(n: int) -> int:",
            explanation=(
                "sum_range() is not tested at all.  Edge cases n=0 and n=1 are "
                "not covered, and the performance regression introduced by the "
                "two-loop implementation cannot be detected without a benchmark."
            ),
            recommendation=(
                "Add unit tests for sum_range(0), sum_range(1), sum_range(100), "
                "and a negative-input guard test."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

DEMO_REVIEWER_OUTPUTS: list[ReviewerOutput] = [
    CORRECTNESS_OUTPUT,
    SECURITY_OUTPUT,
    PERFORMANCE_OUTPUT,
    TEST_COVERAGE_OUTPUT,
]

# ---------------------------------------------------------------------------
# Coordinator report (used by coordinator.py in DEMO_MODE)
# ---------------------------------------------------------------------------

# Collect all findings from the four reviewer outputs, deduplication is
# already resolved here (no overlapping file+line+category tuples).
_ALL_DEMO_FINDINGS: list[Finding] = [
    f
    for ro in DEMO_REVIEWER_OUTPUTS
    for f in ro.findings
]

DEMO_COORDINATOR_REPORT = CoordinatorReport(
    findings=_ALL_DEMO_FINDINGS,
    overall_risk="critical",   # driven by the eval() finding (severity=critical)
    summary=(
        "[DEMO MODE] This pull request introduces three classes of risk. "
        "Most critically, evaluate() passes unsanitised user input directly "
        "to eval(), enabling arbitrary code execution — this must be fixed "
        "before merge. Additionally, divide() raises an unhandled "
        "ZeroDivisionError, sum_range() uses an O(n) algorithm where O(1) "
        "is trivial, and several functions lack test coverage entirely. "
        "Recommended action: apply the suggested patch, add missing tests, "
        "and re-review."
    ),
    is_demo=True,
)

# ---------------------------------------------------------------------------
# Patch result (used by patch_generator.py in DEMO_MODE)
# ---------------------------------------------------------------------------
# This diff fixes all three known issues in the demo calculator:
#   1. divide() — adds a zero-divisor guard raising ValueError
#   2. evaluate() — replaces eval() with ast.literal_eval()
#   3. sum_range() — replaces the two-loop O(n) implementation with O(1) formula

DEMO_PATCH_RESULT = PatchResult(
    is_demo=True,
    patch_diff=(
        "--- a/calculator.py\n"
        "+++ b/calculator.py\n"
        "@@ -33,7 +33,10 @@ def multiply(a: float, b: float) -> float:\n"
        " def divide(a: float, b: float) -> float:\n"
        '     """Return a / b."""\n'
        "-    # Missing guard: if b == 0: raise ValueError(\"divisor cannot be zero\")\n"
        "-    return a / b\n"
        "+    if b == 0:\n"
        "+        raise ValueError(\"divisor cannot be zero\")\n"
        "+    return a / b\n"
        "+\n"
        "@@ -40,7 +43,11 @@ def divide(a: float, b: float) -> float:\n"
        " def evaluate(expression: str) -> float:\n"
        '     """Evaluate an arithmetic expression string and return the result."""\n'
        "-    return eval(expression)  # noqa: S307  (intentional security smell for demo)\n"
        "+    import ast\n"
        "+    try:\n"
        "+        return float(ast.literal_eval(expression))\n"
        "+    except (ValueError, SyntaxError) as exc:\n"
        "+        raise ValueError(f\"Invalid expression: {expression!r}\") from exc\n"
        "+\n"
        "@@ -50,10 +57,5 @@ def sum_range(n: int) -> int:\n"
        '     """Return the sum of integers from 1 to n (inclusive)."""\n'
        "-    numbers = []\n"
        "-    for i in range(1, n + 1):\n"
        "-        numbers.append(i)   # redundant list build\n"
        "-    total = 0\n"
        "-    for num in numbers:     # second pass\n"
        "-        total += num\n"
        "-    return total\n"
        "+    if n < 1:\n"
        "+        return 0\n"
        "+    return n * (n + 1) // 2\n"
    ),
    explanation=(
        "Three issues fixed. "
        "First, divide() now raises ValueError('divisor cannot be zero') when b == 0, "
        "replacing the unhandled ZeroDivisionError. "
        "Second, evaluate() replaces the dangerous eval() call with ast.literal_eval(), "
        "which safely parses numeric literals only and raises ValueError for any "
        "expression containing operators — eliminating the arbitrary code execution risk. "
        "Third, sum_range() is replaced with the O(1) arithmetic formula n*(n+1)//2, "
        "eliminating the redundant list allocation and double loop."
    ),
)

# ---------------------------------------------------------------------------
# After-patch coordinator report (used by rerun_review in DEMO_MODE)
# ---------------------------------------------------------------------------
# After applying the patch, all critical/high/medium issues are resolved.
# Only one low-severity informational finding remains (documentation gap).

DEMO_AFTER_COORDINATOR_REPORT = CoordinatorReport(
    findings=[
        Finding(
            severity="low",
            category="correctness",
            file="calculator.py",
            line=None,
            evidence="def evaluate(expression: str) -> float:",
            explanation=(
                "[DEMO MODE — POST-PATCH] evaluate() now uses ast.literal_eval() safely. "
                "A minor documentation gap remains: the docstring does not yet describe "
                "the new ValueError behaviour for non-literal inputs."
            ),
            recommendation=(
                "Update the docstring to document that only numeric literals are accepted "
                "and that ValueError is raised for all other inputs."
            ),
        ),
    ],
    overall_risk="low",
    summary=(
        "[DEMO MODE — POST-PATCH] After applying the suggested patch, the pull request "
        "risk has dropped from 'critical' to 'low'. "
        "All security, correctness, and performance issues have been resolved. "
        "One minor documentation gap remains in evaluate()'s docstring. "
        "The change is safe to merge after updating the docstring."
    ),
    is_demo=True,
)

# ---------------------------------------------------------------------------
# Re-review result (used by rerun_review in DEMO_MODE)
# ---------------------------------------------------------------------------

DEMO_REREVIEW_RESULT = ReReviewResult(
    previous_risk="critical",
    new_risk="low",
    risk_decreased=True,
    summary=(
        "[DEMO MODE] Re-review complete. "
        "Risk changed from 'critical' to 'low'. "
        "8 finding(s) resolved (eval() vulnerability, ZeroDivisionError bug, "
        "O(n) performance issue, and all missing test-coverage gaps); "
        "1 finding remains (minor documentation gap). "
        "Risk has decreased."
    ),
)
