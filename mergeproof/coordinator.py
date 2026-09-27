"""
coordinator.py — merges all reviewer outputs into a single CoordinatorReport.

Public API
----------
coordinate(reviewer_outputs)                   -> CoordinatorReport
compare_risk(before, after)                    -> ReReviewResult
rerun_review(patched_diff, repo_files, before) -> ReReviewResult

Internal helpers (also exported for testing)
--------------------------------------------
_deduplicate(findings)         — group by (file, line, category); keep highest severity
_derive_overall_risk(findings) — map severity → RiskLevel
_risk_rank(risk_level)         — map RiskLevel string → int for comparison

DEMO_MODE: returns pre-built objects from demo_mode.py immediately.
Live mode: deduplicates, derives risk, calls LLM.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from mergeproof.schemas import CoordinatorReport, Finding, ReReviewResult, ReviewerOutput

load_dotenv()

# ---------------------------------------------------------------------------
# DEMO_MODE detection (mirrors reviewer.py — reads env at import time)
# ---------------------------------------------------------------------------

_FORCE_DEMO = os.getenv("DEMO_MODE", "false").lower() == "true"
_HAS_KEY = bool(os.getenv("OPENAI_API_KEY", "").strip())
DEMO_MODE: bool = _FORCE_DEMO or not _HAS_KEY

# ---------------------------------------------------------------------------
# Severity ordering (higher index = more severe)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

# Map the highest finding severity to a CoordinatorReport overall_risk.
# "info" findings alone produce "low" overall risk (info is not a valid RiskLevel).
_SEVERITY_TO_RISK: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "low",
}


# ---------------------------------------------------------------------------
# _deduplicate
# ---------------------------------------------------------------------------

def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """Merge findings with the same (file, line, category); keep highest severity.

    The order of the returned list is deterministic: grouped by (file, line,
    category) tuples in the order they were first seen.
    """
    # Use a dict keyed by (file, line, category) to preserve insertion order
    best: dict[tuple, Finding] = {}
    for f in findings:
        key = (f.file, f.line, f.category)
        if key not in best:
            best[key] = f
        else:
            # Keep the finding with the higher severity rank
            if _SEVERITY_ORDER[f.severity] > _SEVERITY_ORDER[best[key].severity]:
                best[key] = f
    return list(best.values())


# ---------------------------------------------------------------------------
# _derive_overall_risk
# ---------------------------------------------------------------------------

def _derive_overall_risk(findings: list[Finding]) -> str:
    """Return the overall risk level driven by the most severe finding.

    Returns "low" when findings is empty (no issues found).
    """
    if not findings:
        return "low"
    highest = max(findings, key=lambda f: _SEVERITY_ORDER[f.severity])
    return _SEVERITY_TO_RISK[highest.severity]


# ---------------------------------------------------------------------------
# LLM summary call (live mode only)
# ---------------------------------------------------------------------------

def _llm_summary(findings: list[Finding], overall_risk: str) -> str:
    """Ask the LLM for a 2-3 sentence executive summary of the findings.

    Returns a plain string.  Never raises — on any failure returns a
    fallback summary built from the finding count.
    """
    from openai import OpenAI  # deferred import; never called in DEMO_MODE

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    findings_json = json.dumps(
        [f.model_dump() for f in findings], indent=2
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior engineering lead reviewing a pull request. "
                "Given a JSON list of findings, write a concise 2-3 sentence "
                "executive summary suitable for a pull-request description. "
                "State the overall risk level, the most critical issue, and "
                "the recommended next action. Return ONLY the summary text — "
                "no JSON, no markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Overall risk: {overall_risk}\n\nFindings:\n{findings_json}"
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        count = len(findings)
        return (
            f"Review complete. {count} finding(s) identified with overall risk "
            f"'{overall_risk}'. LLM summary unavailable: {exc}. "
            "Please review the findings table for details."
        )


# ---------------------------------------------------------------------------
# coordinate — public entry point
# ---------------------------------------------------------------------------

def coordinate(reviewer_outputs: list[ReviewerOutput]) -> CoordinatorReport:
    """Merge all reviewer outputs into a single CoordinatorReport.

    DEMO_MODE: returns the pre-built DEMO_COORDINATOR_REPORT immediately.
    Live mode: deduplicates, derives risk, calls LLM once for summary.
    """
    is_demo_input = any(ro.is_demo for ro in reviewer_outputs)

    if DEMO_MODE or is_demo_input:
        from mergeproof.demo_mode import DEMO_COORDINATOR_REPORT
        return DEMO_COORDINATOR_REPORT

    # Collect and deduplicate all findings
    all_findings: list[Finding] = []
    for ro in reviewer_outputs:
        all_findings.extend(ro.findings)

    deduped = _deduplicate(all_findings)
    overall_risk = _derive_overall_risk(deduped)
    summary = _llm_summary(deduped, overall_risk)

    return CoordinatorReport(
        findings=deduped,
        overall_risk=overall_risk,  # type: ignore[arg-type]
        summary=summary,
        is_demo=False,
    )


# ---------------------------------------------------------------------------
# _risk_rank — integer ordering for RiskLevel comparison
# ---------------------------------------------------------------------------

# Plan spec: critical=4, high=3, medium=2, low=1
_RISK_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def _risk_rank(risk_level: str) -> int:
    """Return the integer rank of a RiskLevel string (critical=4 … low=1).

    Defaults to 1 (lowest) for any unrecognised value.
    """
    return _RISK_RANK.get(risk_level, 1)


# ---------------------------------------------------------------------------
# compare_risk — produce a ReReviewResult from two CoordinatorReports
# ---------------------------------------------------------------------------

def compare_risk(
    before: CoordinatorReport,
    after: CoordinatorReport,
) -> ReReviewResult:
    """Compare before/after risk levels and identify resolved vs remaining findings.

    risk_decreased is True only when the after risk rank is strictly lower than
    the before risk rank.
    """
    before_rank = _risk_rank(before.overall_risk)
    after_rank = _risk_rank(after.overall_risk)
    decreased = after_rank < before_rank

    # Identify resolved findings: keys present in before but absent in after.
    # A finding is keyed by (file, line, category) — same key used by _deduplicate.
    before_keys = {(f.file, f.line, f.category) for f in before.findings}
    after_keys  = {(f.file, f.line, f.category) for f in after.findings}
    resolved_count = len(before_keys - after_keys)
    remaining_count = len(after_keys)

    summary = (
        f"Re-review complete. "
        f"Risk changed from '{before.overall_risk}' to '{after.overall_risk}'. "
        f"{resolved_count} finding(s) resolved; {remaining_count} finding(s) remain."
        + (" Risk has decreased." if decreased else " Risk has not decreased.")
    )

    return ReReviewResult(
        previous_risk=before.overall_risk,   # type: ignore[arg-type]
        new_risk=after.overall_risk,          # type: ignore[arg-type]
        risk_decreased=decreased,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# rerun_review — full re-review pipeline on patched diff
# ---------------------------------------------------------------------------

def rerun_review(
    patched_diff: str,
    repo_files: dict[str, str],
    before_report: CoordinatorReport,
) -> ReReviewResult:
    """Run all reviewers on the patched diff and compare risk with the original.

    DEMO_MODE: returns DEMO_REREVIEW_RESULT immediately.
    Live mode: calls run_all_reviewers → coordinate → compare_risk.
    """
    if DEMO_MODE or before_report.is_demo:
        from mergeproof.demo_mode import DEMO_REREVIEW_RESULT
        return DEMO_REREVIEW_RESULT

    from mergeproof.reviewer import run_all_reviewers
    after_outputs = run_all_reviewers(patched_diff, repo_files)
    after_report = coordinate(after_outputs)
    return compare_risk(before_report, after_report)
