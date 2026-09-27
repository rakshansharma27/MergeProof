"""
ui_helpers.py — pure helper functions for the MergeProof Streamlit UI.

These functions contain no Streamlit imports so they can be unit-tested
without a running Streamlit server.
"""

from __future__ import annotations

from mergeproof.schemas import CoordinatorReport, Finding

# ---------------------------------------------------------------------------
# Severity → colour / emoji mapping
# ---------------------------------------------------------------------------

SEVERITY_EMOJI: dict[str, str] = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🔵",
    "info":     "⚪",
}

SEVERITY_COLOR: dict[str, str] = {
    "critical": "#ff4b4b",
    "high":     "#ff8c00",
    "medium":   "#ffd700",
    "low":      "#4fc3f7",
    "info":     "#aaaaaa",
}

# Sort order for display (most severe first)
SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high":     1,
    "medium":   2,
    "low":      3,
    "info":     4,
}

RISK_EMOJI: dict[str, str] = {
    "critical": "🔴 CRITICAL",
    "high":     "🟠 HIGH",
    "medium":   "🟡 MEDIUM",
    "low":      "🔵 LOW",
}


def severity_badge(severity: str) -> str:
    """Return an emoji + uppercased severity label for display."""
    emoji = SEVERITY_EMOJI.get(severity, "⚪")
    return f"{emoji} {severity.upper()}"


def risk_badge(risk: str) -> str:
    """Return an emoji + uppercased risk label for display."""
    return RISK_EMOJI.get(risk, f"❓ {risk.upper()}")


def findings_to_rows(findings: list[Finding]) -> list[dict]:
    """Convert a list of Finding objects to a list of display dicts.

    Sorted by severity (most severe first), then by file + line.
    Each row has the following keys:
        Severity, Category, File, Line, Evidence, Explanation, Recommendation
    """
    sorted_findings = sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.file, f.line or 0),
    )
    rows = []
    for f in sorted_findings:
        rows.append({
            "Severity":       severity_badge(f.severity),
            "Category":       f.category.replace("_", " ").title(),
            "File":           f.file,
            "Line":           str(f.line) if f.line is not None else "—",
            "Evidence":       f.evidence,
            "Explanation":    f.explanation,
            "Recommendation": f.recommendation,
        })
    return rows


def risk_delta_text(before: str, after: str, decreased: bool) -> str:
    """Return a human-readable risk delta string for display."""
    arrow = "⬇️ decreased" if decreased else ("➡️ unchanged" if before == after else "⬆️ increased")
    return f"{risk_badge(before)}  →  {risk_badge(after)}  {arrow}"


def count_by_severity(findings: list[Finding]) -> dict[str, int]:
    """Return a dict of severity → count for all findings."""
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def resolved_findings(
    before: CoordinatorReport,
    after: CoordinatorReport,
) -> tuple[list[Finding], list[Finding]]:
    """Return (resolved, remaining) finding lists.

    A finding is resolved if its (file, line, category) key is present in
    before but absent in after.
    """
    after_keys = {(f.file, f.line, f.category) for f in after.findings}
    resolved = [f for f in before.findings if (f.file, f.line, f.category) not in after_keys]
    remaining = list(after.findings)
    return resolved, remaining
