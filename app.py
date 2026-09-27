"""
app.py — MergeProof Streamlit UI.

Golden demo path:
  1.  Load Demo Pull Request       — display diff viewer
  2.  Analyse Pull Request         — run 4 reviewers in parallel
  3.  Display Findings             — colour-coded severity table
  4.  Generate Suggested Fix       — AI-generated patch diff
  5.  Run Tests (Before)           — pytest on demo/tests/  (bugs present)
  6.  Display Patched Code         — read-only view of the fix
  7.  Run Tests (After)            — pytest on demo/tests_fixed/ (bugs fixed)
  8.  Re-Review                    — re-run reviewers on patched diff
  9.  Risk Comparison              — before vs after risk + resolved findings

All expensive calls are gated by st.session_state so re-runs never re-fire them.
DEMO_MODE is detected from env vars at startup and shown as a persistent banner.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MergeProof",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Dark-theme CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Dark background */
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .block-container { padding-top: 1.5rem; }

    /* Section dividers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #c9d1d9;
        border-bottom: 1px solid #30363d;
        padding-bottom: 4px;
        margin-top: 1.4rem;
        margin-bottom: 0.6rem;
    }

    /* Demo-mode banner override */
    div[data-testid="stAlert"] p { font-weight: 600; }

    /* Finding row evidence monospace */
    .evidence-cell { font-family: monospace; font-size: 0.82rem; color: #a8d8ea; }

    /* Risk pill */
    .risk-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 700;
        margin-right: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# DEMO_MODE detection
# ---------------------------------------------------------------------------

_FORCE_DEMO = os.getenv("DEMO_MODE", "false").lower() == "true"
_HAS_KEY    = bool(os.getenv("OPENAI_API_KEY", "").strip())
DEMO_MODE   = _FORCE_DEMO or not _HAS_KEY

# ---------------------------------------------------------------------------
# Load static demo assets (once — not on every rerun)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent
_DIFF_PATH = _REPO_ROOT / "demo" / "sample.diff"
_CALC_PATH = _REPO_ROOT / "demo" / "repo" / "calculator.py"
_CALC_FIXED_PATH = _REPO_ROOT / "demo" / "repo" / "calculator_fixed.py"

@st.cache_data
def _load_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        return f"[Error loading file: {exc}]"

DIFF_TEXT         = _load_file(str(_DIFF_PATH))
CALC_TEXT         = _load_file(str(_CALC_PATH))
CALC_FIXED_TEXT   = _load_file(str(_CALC_FIXED_PATH))
REPO_FILES        = {"calculator.py": CALC_TEXT}

# ---------------------------------------------------------------------------
# Lazy imports of backend modules (avoids importing openai at module level)
# ---------------------------------------------------------------------------

def _import_backend():
    from mergeproof.coordinator     import coordinate, rerun_review
    from mergeproof.patch_generator import generate_patch
    from mergeproof.reviewer        import run_all_reviewers
    from mergeproof.test_runner     import run_tests
    from mergeproof.ui_helpers      import (
        count_by_severity, findings_to_rows, resolved_findings, risk_badge,
        risk_delta_text,
    )
    return (
        run_all_reviewers, coordinate, generate_patch,
        run_tests, rerun_review,
        findings_to_rows, count_by_severity, resolved_findings,
        risk_badge, risk_delta_text,
    )

(
    run_all_reviewers, coordinate, generate_patch,
    run_tests, rerun_review,
    findings_to_rows, count_by_severity, resolved_findings,
    risk_badge, risk_delta_text,
) = _import_backend()

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "diff_loaded":       False,
        "review_done":       False,
        "reviewer_outputs":  None,
        "coord_report":      None,
        "patch_done":        False,
        "patch_result":      None,
        "tests_before_done": False,
        "tests_before":      None,
        "tests_after_done":  False,
        "tests_after":       None,
        "rereview_done":     False,
        "rereview_result":   None,
        "after_report":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _findings_table(findings):
    """Render a colour-coded findings table."""
    if not findings:
        st.info("No findings.")
        return
    rows = findings_to_rows(findings)
    # Use st.dataframe with column config for a clean display
    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Evidence":       st.column_config.TextColumn(width="medium"),
            "Explanation":    st.column_config.TextColumn(width="large"),
            "Recommendation": st.column_config.TextColumn(width="large"),
        },
    )


def _severity_summary(findings):
    counts = count_by_severity(findings)
    cols = st.columns(5)
    labels = [
        ("🔴 Critical", counts["critical"], "#ff4b4b"),
        ("🟠 High",     counts["high"],     "#ff8c00"),
        ("🟡 Medium",   counts["medium"],   "#ffd700"),
        ("🔵 Low",      counts["low"],      "#4fc3f7"),
        ("⚪ Info",     counts["info"],     "#aaaaaa"),
    ]
    for col, (label, count, _colour) in zip(cols, labels):
        col.metric(label=label, value=count)


def _test_result_display(result, label: str):
    c1, c2, c3 = st.columns(3)
    c1.metric(f"✅ Passed ({label})", result.passed)
    c2.metric(f"❌ Failed ({label})", result.failed, delta=None if result.failed == 0 else f"-{result.failed}", delta_color="inverse")
    c3.metric(f"⚠️ Errors ({label})", result.errors)
    with st.expander("Raw pytest output", expanded=False):
        st.code(result.output, language="text")


# ---------------------------------------------------------------------------
# ── HEADER ──────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

st.title("🔍 MergeProof")
st.caption("Evidence-first AI pull-request reviewer")

if DEMO_MODE:
    st.warning(
        "⚠️ **DEMO MODE** — findings are synthetic, not live AI output.  "
        "Set `OPENAI_API_KEY` in your `.env` file to enable live analysis.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# ── STEP 1: LOAD DEMO PULL REQUEST ──────────────────────────────────────────
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">① Pull Request Diff</div>', unsafe_allow_html=True)

with st.expander("View full diff", expanded=not st.session_state.diff_loaded):
    st.code(DIFF_TEXT, language="diff")

if not st.session_state.diff_loaded:
    if st.button("📂 Load Demo Pull Request", type="primary"):
        st.session_state.diff_loaded = True
        st.rerun()
else:
    st.success("✅ Demo pull request loaded — `demo/sample.diff` (calculator.py with 3 intentional issues)")

# ---------------------------------------------------------------------------
# ── STEP 2: ANALYSE PULL REQUEST ────────────────────────────────────────────
# ---------------------------------------------------------------------------

if st.session_state.diff_loaded:
    st.markdown('<div class="section-header">② Analysis — Parallel Review</div>', unsafe_allow_html=True)

    if not st.session_state.review_done:
        if st.button("🚀 Analyse Pull Request", type="primary"):
            with st.spinner("Running 4 reviewers in parallel…"):
                try:
                    outputs = run_all_reviewers(DIFF_TEXT, REPO_FILES)
                    report  = coordinate(outputs)
                    st.session_state.reviewer_outputs = outputs
                    st.session_state.coord_report     = report
                    st.session_state.review_done      = True
                except Exception as exc:
                    st.error(f"❌ Review failed: {exc}")
            if st.session_state.review_done:
                st.rerun()
    else:
        report = st.session_state.coord_report

        # ── Risk summary ──
        col_risk, col_demo = st.columns([3, 1])
        with col_risk:
            st.markdown(
                f"**Overall Risk:** {risk_badge(report.overall_risk)}",
                unsafe_allow_html=True,
            )
        with col_demo:
            if report.is_demo:
                st.caption("🔬 DEMO findings")

        st.markdown(f"*{report.summary}*")

        # ── Severity breakdown ──
        _severity_summary(report.findings)

        # ── Findings table ──
        st.markdown("**Findings**")
        _findings_table(report.findings)

# ---------------------------------------------------------------------------
# ── STEP 3: GENERATE SUGGESTED FIX ─────────────────────────────────────────
# ---------------------------------------------------------------------------

if st.session_state.review_done:
    st.markdown('<div class="section-header">③ Suggested Fix (Patch)</div>', unsafe_allow_html=True)

    if not st.session_state.patch_done:
        if st.button("🔧 Generate Suggested Fix", type="primary"):
            with st.spinner("Generating patch…"):
                try:
                    patch = generate_patch(
                        st.session_state.coord_report,
                        DIFF_TEXT,
                        REPO_FILES,
                    )
                    st.session_state.patch_result = patch
                    st.session_state.patch_done   = True
                except Exception as exc:
                    st.error(f"❌ Patch generation failed: {exc}")
            if st.session_state.patch_done:
                st.rerun()
    else:
        patch = st.session_state.patch_result
        if patch.is_demo:
            st.caption("🔬 DEMO patch")
        st.markdown(f"**Explanation:** {patch.explanation}")
        st.code(patch.patch_diff, language="diff")

# ---------------------------------------------------------------------------
# ── STEP 4: RUN TESTS (BEFORE PATCH) ────────────────────────────────────────
# ---------------------------------------------------------------------------

if st.session_state.patch_done:
    st.markdown('<div class="section-header">④ Tests — Before Applying Patch</div>', unsafe_allow_html=True)
    st.caption("Running against original flawed `demo/tests/` — expect failures.")

    if not st.session_state.tests_before_done:
        if st.button("🧪 Run Tests (Before)", type="primary"):
            with st.spinner("Running pytest on demo/tests/…"):
                try:
                    result = run_tests("demo/tests")
                    st.session_state.tests_before      = result
                    st.session_state.tests_before_done = True
                except Exception as exc:
                    st.error(f"❌ Test run failed: {exc}")
            if st.session_state.tests_before_done:
                st.rerun()
    else:
        _test_result_display(st.session_state.tests_before, "Before")

# ---------------------------------------------------------------------------
# ── STEP 5: DISPLAY PATCHED CODE ────────────────────────────────────────────
# ---------------------------------------------------------------------------

if st.session_state.tests_before_done:
    st.markdown('<div class="section-header">⑤ Patched Code</div>', unsafe_allow_html=True)
    st.caption(
        "Read-only view of `demo/repo/calculator_fixed.py` — "
        "the original `calculator.py` is **never modified**."
    )
    with st.expander("View patched calculator_fixed.py", expanded=False):
        st.code(CALC_FIXED_TEXT, language="python")

# ---------------------------------------------------------------------------
# ── STEP 6: RUN TESTS (AFTER PATCH) ─────────────────────────────────────────
# ---------------------------------------------------------------------------

if st.session_state.tests_before_done:
    st.markdown('<div class="section-header">⑥ Tests — After Applying Patch</div>', unsafe_allow_html=True)
    st.caption("Running against fixed `demo/tests_fixed/` — all should pass.")

    if not st.session_state.tests_after_done:
        if st.button("🧪 Run Tests (After)", type="primary"):
            with st.spinner("Running pytest on demo/tests_fixed/…"):
                try:
                    result = run_tests("demo/tests_fixed")
                    st.session_state.tests_after      = result
                    st.session_state.tests_after_done = True
                except Exception as exc:
                    st.error(f"❌ Test run failed: {exc}")
            if st.session_state.tests_after_done:
                st.rerun()
    else:
        _test_result_display(st.session_state.tests_after, "After")

# ---------------------------------------------------------------------------
# ── STEP 7: RE-REVIEW ───────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

if st.session_state.tests_after_done:
    st.markdown('<div class="section-header">⑦ Re-Review — Post-Patch Risk Assessment</div>', unsafe_allow_html=True)

    if not st.session_state.rereview_done:
        if st.button("🔄 Re-Review After Fix", type="primary"):
            with st.spinner("Re-running reviewers on patched diff…"):
                try:
                    patch = st.session_state.patch_result
                    before_report = st.session_state.coord_report
                    rr_result = rerun_review(
                        patch.patch_diff,
                        {"calculator_fixed.py": CALC_FIXED_TEXT},
                        before_report,
                    )
                    # Build after-report for resolved-findings display
                    from mergeproof.demo_mode import DEMO_AFTER_COORDINATOR_REPORT
                    after_report = (
                        DEMO_AFTER_COORDINATOR_REPORT
                        if before_report.is_demo
                        else coordinate(
                            run_all_reviewers(patch.patch_diff, {"calculator_fixed.py": CALC_FIXED_TEXT})
                        )
                    )
                    st.session_state.rereview_result = rr_result
                    st.session_state.after_report    = after_report
                    st.session_state.rereview_done   = True
                except Exception as exc:
                    st.error(f"❌ Re-review failed: {exc}")
            if st.session_state.rereview_done:
                st.rerun()
    else:
        rr   = st.session_state.rereview_result
        before_report = st.session_state.coord_report
        after_report  = st.session_state.after_report

        # ── Risk comparison ──
        st.markdown("### Risk Comparison")
        delta_text = risk_delta_text(rr.previous_risk, rr.new_risk, rr.risk_decreased)
        if rr.risk_decreased:
            st.success(f"✅ {delta_text}")
        else:
            st.warning(f"⚠️ {delta_text}")

        col_before, col_after = st.columns(2)
        with col_before:
            st.metric("Risk Before", rr.previous_risk.upper())
        with col_after:
            st.metric("Risk After",  rr.new_risk.upper(),
                      delta="improved" if rr.risk_decreased else "unchanged",
                      delta_color="normal" if rr.risk_decreased else "off")

        st.markdown(f"*{rr.summary}*")

        # ── Resolved vs remaining findings ──
        resolved, remaining = resolved_findings(before_report, after_report)

        col_res, col_rem = st.columns(2)
        with col_res:
            st.markdown(f"**✅ Resolved Findings ({len(resolved)})**")
            if resolved:
                _findings_table(resolved)
            else:
                st.info("None resolved.")
        with col_rem:
            st.markdown(f"**⚠️ Remaining Findings ({len(remaining)})**")
            if remaining:
                _findings_table(remaining)
            else:
                st.success("All findings resolved! 🎉")

        if rr.is_demo:
            st.caption("🔬 DEMO re-review result")

# ---------------------------------------------------------------------------
# ── FOOTER ──────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption("MergeProof · IBM Bob 2.0 Hackathon · Evidence-first AI PR reviewer")
