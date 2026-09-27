# MergeProof — 60–90 Second Demo Script

> **Setup before presenting:**
> ```
> DEMO_MODE=true streamlit run app.py
> ```
> Open http://localhost:8501 in a browser.  Zoom to 90%.

---

## The Setup  *(10 seconds)*

> *"Every PR review today is a black box — you get a pass/fail and maybe a comment.
> MergeProof is an evidence-first AI reviewer.
> Every finding has a severity, a file, a line, and verbatim evidence from the diff.
> Nothing is invented. Let me show you."*

---

## Step 1 — Load Demo Pull Request  *(5 seconds)*

Click **📂 Load Demo Pull Request**.

> *"Here's a Python calculator that just had three bugs introduced:
> a division-by-zero crash, an `eval()` security hole, and an O(n) performance issue."*

*(Point to the diff viewer — the red lines clearly show the introduced flaws.)*

---

## Step 2 — Analyse  *(15 seconds)*

Click **🚀 Analyse Pull Request**.  *(spinner appears for ~1 second in DEMO_MODE)*

> *"MergeProof runs four specialised reviewers in parallel —
> correctness, security, performance, and test coverage —
> each with a focused prompt.
> They can't invent file names or line numbers.
> Everything in this table comes directly from the diff."*

*(Point to the findings table.)*

> *"9 findings. Overall risk: CRITICAL.
> The top finding: `eval(expression)` — arbitrary code execution.
> Line 55, exact evidence right there."*

---

## Step 3 — Generate Fix  *(10 seconds)*

Click **🔧 Generate Suggested Fix**.

> *"The coordinator passes all findings to a second LLM call to generate a patch.
> It fixes the zero-divisor bug, replaces `eval` with `ast.literal_eval`,
> and replaces the two-loop O(n) with the O(1) formula.
> Read-only — we never touch the original file."*

*(Show the unified diff in the code block.)*

---

## Step 4 — Run Tests Before  *(10 seconds)*

Click **🧪 Run Tests (Before)**.

> *"9 passed, 1 failed.
> The failing test is `test_divide_by_zero` — it expected a `ValueError`
> but got `ZeroDivisionError`.  That's the real bug, right there in CI."*

---

## Step 5 — Run Tests After  *(10 seconds)*

Click **🧪 Run Tests (After)**.

> *"After the patch: 18 passed, zero failures.
> The test suite grew — the patch added coverage for `evaluate()` and `sum_range()`
> that didn't exist before."*

---

## Step 6 — Re-Review  *(10 seconds)*

Click **🔄 Re-Review After Fix**.

> *"MergeProof re-reviews the patched diff.
> Risk dropped from CRITICAL to LOW.
> 8 findings resolved.
> 1 remains — a minor documentation gap.
> The PR is now safe to merge."*

*(Point to the green success banner and the risk delta metric.)*

---

## The Punchline  *(5 seconds)*

> *"Evidence-first. Every finding has a file, a line, verbatim evidence, and a fix.
> No hallucinations — if it's not in the diff, it's not in the report.
> That's MergeProof."*

---

## Fallback Points (if something goes wrong)

- If the spinner takes too long → explain "in live mode this calls `gpt-4o-mini` four times in parallel; in the demo we use pre-computed fixtures so it's instant"
- If asked about GitHub integration → "not in scope for the hackathon, but the diff input is a plain string — any source works"
- If asked about false positives → "the LLM is instructed to quote evidence verbatim from the diff; any finding without a line number or evidence string was rejected by our Pydantic schema"
