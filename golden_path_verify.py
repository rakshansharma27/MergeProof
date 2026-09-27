"""golden_path_verify.py — runs the complete MergeProof golden demo path
and prints structured output for each step."""

import os
import sys
import io
from collections import Counter

# Force UTF-8 output so emojis don't fail on Windows cp1252 console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.environ["DEMO_MODE"] = "true"

SEP = "=" * 70

# ── Step 1: Load Demo PR ──────────────────────────────────────────────────────
diff = open("demo/sample.diff", encoding="utf-8").read()
calc = open("demo/repo/calculator.py", encoding="utf-8").read()
repo_files = {"calculator.py": calc}
print(SEP)
print("STEP 1 — LOAD DEMO PULL REQUEST")
print(SEP)
print(f"Diff loaded : {len(diff.splitlines())} lines")
print(f"Repo file   : calculator.py  ({len(calc.splitlines())} lines)")
print()

# ── Step 2: Analyse ───────────────────────────────────────────────────────────
from mergeproof.reviewer    import run_all_reviewers
from mergeproof.coordinator import coordinate

outputs = run_all_reviewers(diff, repo_files)
report  = coordinate(outputs)

print(SEP)
print("STEP 2 — ANALYSE  (DEMO_MODE)")
print(SEP)
print(f"Reviewers  : {[o.reviewer_name for o in outputs]}")
print(f"is_demo    : {report.is_demo}")
print(f"Overall risk: {report.overall_risk.upper()}")
print(f"Total findings: {len(report.findings)}")
counts = Counter(f.severity for f in report.findings)
for sev in ("critical", "high", "medium", "low", "info"):
    if counts[sev]:
        print(f"  {sev:10s}: {counts[sev]}")
print(f"\nSummary:\n{report.summary[:300]}")
print()

# ── Step 3: Findings ──────────────────────────────────────────────────────────
from mergeproof.ui_helpers import findings_to_rows

print(SEP)
print("STEP 3 — FINDINGS TABLE  (first 4 shown)")
print(SEP)
rows = findings_to_rows(report.findings)
for r in rows[:4]:
    print(f"  [{r['Severity']}] {r['Category']:20s}  {r['File']}:{r['Line']}")
    print(f"    Evidence: {r['Evidence'][:70]}")
    print(f"    Rec:      {r['Recommendation'][:80]}")
    print()

# ── Step 4: Generate Fix ──────────────────────────────────────────────────────
from mergeproof.patch_generator import generate_patch

patch = generate_patch(report, diff, repo_files)
print(SEP)
print("STEP 4 — GENERATE FIX  (DEMO_MODE)")
print(SEP)
print(f"is_demo    : {patch.is_demo}")
print(f"patch_diff : starts with {repr(patch.patch_diff[:50])}")
print(f"Explanation: {patch.explanation[:250]}")
print()

# ── Step 5: Run Tests BEFORE ──────────────────────────────────────────────────
from mergeproof.test_runner import run_tests

before = run_tests("demo/tests")
print(SEP)
print("STEP 5 — RUN TESTS  (Before patch)  demo/tests/")
print(SEP)
print(f"passed={before.passed}  failed={before.failed}  errors={before.errors}")
last = before.output.strip().splitlines()[-1] if before.output.strip() else "(empty)"
print(f"pytest: {last}")
print()

# ── Step 6: View Patched Code ─────────────────────────────────────────────────
fixed = open("demo/repo/calculator_fixed.py", encoding="utf-8").read()
print(SEP)
print("STEP 6 — PATCHED CODE  (calculator_fixed.py — original untouched)")
print(SEP)
print(f"Lines: {len(fixed.splitlines())}   (demo/repo/calculator.py NOT modified)")
print(fixed[:500])
print("...")
print()

# ── Step 7: Run Tests AFTER ───────────────────────────────────────────────────
after = run_tests("demo/tests_fixed")
print(SEP)
print("STEP 7 — RUN TESTS  (After patch)  demo/tests_fixed/")
print(SEP)
print(f"passed={after.passed}  failed={after.failed}  errors={after.errors}")
last = after.output.strip().splitlines()[-1] if after.output.strip() else "(empty)"
print(f"pytest: {last}")
print()

# ── Step 8: Re-Review ────────────────────────────────────────────────────────
from mergeproof.coordinator import rerun_review

rr = rerun_review(patch.patch_diff, {"calculator_fixed.py": fixed}, report)
print(SEP)
print("STEP 8 — RE-REVIEW  (DEMO_MODE)")
print(SEP)
print(f"previous_risk : {rr.previous_risk}")
print(f"new_risk      : {rr.new_risk}")
print(f"risk_decreased: {rr.risk_decreased}")
print(f"Summary:\n{rr.summary[:300]}")
print()

# ── Step 9: Risk Comparison ───────────────────────────────────────────────────
from mergeproof.demo_mode   import DEMO_AFTER_COORDINATOR_REPORT
from mergeproof.ui_helpers  import resolved_findings, risk_delta_text

resolved, remaining = resolved_findings(report, DEMO_AFTER_COORDINATOR_REPORT)
print(SEP)
print("STEP 9 — RISK COMPARISON")
print(SEP)
print(f"Delta   : {risk_delta_text(rr.previous_risk, rr.new_risk, rr.risk_decreased)}")
print(f"Resolved: {len(resolved)} findings")
print(f"Remaining: {len(remaining)} findings")
for f in remaining:
    print(f"  [{f.severity}] {f.category}: {f.explanation[:90]}")

print()
print(SEP)
print("ALL STEPS COMPLETE — golden path verified ✅")
print(SEP)
