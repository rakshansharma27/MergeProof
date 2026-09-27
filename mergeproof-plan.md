# MergeProof — Implementation Plan

## Overview

**Goal:** Build a demo-ready, evidence-first AI pull-request reviewer for the IBM Bob 2.0 hackathon.

**Stack:** Python 3.11 + Streamlit (UI), `openai` SDK (LLM calls), `concurrent.futures.ThreadPoolExecutor` (parallel reviewers), `python-dotenv` (env vars), `pytest` (tests).

**Approach:** A single-page Streamlit app that reads a local demo diff, fans out to four specialized AI reviewers in parallel, combines findings via a coordinator, then optionally generates a patch, runs tests, and re-reviews. All reviewer outputs are strict JSON. A `DEMO_MODE` fallback returns clearly labeled synthetic data when no API key is present.

**Non-goals (explicitly out of scope):** Auth, GitHub OAuth, webhooks, database, Docker, MCP, design system.

---

## File Structure

```
MergeProof/
├── app.py                        # Streamlit entry point
├── requirements.txt
├── .env.example
├── demo/
│   ├── sample.diff               # Pre-prepared diff for the demo
│   ├── repo/                     # Minimal local repo snapshot (the files touched by the diff)
│   │   └── calculator.py
│   └── tests/
│       └── test_calculator.py    # Existing tests (some intentionally missing)
├── mergeproof/
│   ├── __init__.py
│   ├── reviewer.py               # Base reviewer + four specialized reviewers
│   ├── coordinator.py            # Combines reviewer outputs into unified findings
│   ├── patch_generator.py        # Generates suggested patch from findings
│   ├── test_runner.py            # Runs pytest on demo/tests/ and captures results
│   ├── schemas.py                # Pydantic models for strict JSON contracts
│   └── demo_mode.py              # DEMO_MODE fallback data (clearly labeled)
├── tests/
│   ├── test_schemas.py           # Validates JSON schema round-trips
│   ├── test_coordinator.py       # Unit tests for coordinator merging logic
│   └── test_reviewer_output.py   # Smoke-tests reviewer JSON strictness
└── AGENTS.md
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | No | If absent, app runs in `DEMO_MODE` |
| `OPENAI_MODEL` | No | Defaults to `gpt-4o-mini` |
| `DEMO_MODE` | No | Force demo mode even if key is present (`"true"`) |

---

## Dependencies (`requirements.txt`)

```
streamlit>=1.35
openai>=1.30
pydantic>=2.7
python-dotenv>=1.0
pytest>=8.2
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold and Demo Fixture

**Status:** `[x] done`

**Intent:**
Create the directory structure, `requirements.txt`, `.env.example`, and the demo diff + repo snapshot. Everything else builds on this foundation. The demo fixture must be realistic enough to trigger all four reviewer categories.

**Expected Outcomes:**
- All directories and placeholder `__init__.py` files exist.
- `demo/sample.diff` contains a realistic Python diff with at least one bug, one insecure call, one performance issue, and missing tests.
- `demo/repo/calculator.py` is the "after" state of the diff (the file being reviewed).
- `demo/tests/test_calculator.py` has partial coverage (missing at least one edge case).
- `requirements.txt` and `.env.example` are present.

**Todo List:**
1. Create all directories: `mergeproof/`, `demo/repo/`, `demo/tests/`, `tests/`.
2. Write `requirements.txt` with pinned dependencies listed above.
3. Write `.env.example` documenting all env vars.
4. Write `demo/repo/calculator.py` — a simple calculator with an intentional bug (e.g., division by zero not handled), a security smell (e.g., `eval()` for expression parsing), and a performance smell (e.g., redundant loop).
5. Write `demo/sample.diff` as a unified diff introducing those flaws.
6. Write `demo/tests/test_calculator.py` with basic happy-path tests but missing edge-case coverage.
7. Create `mergeproof/__init__.py` (empty).

**Relevant Context:**
- The diff must be self-contained so the reviewer never needs to fetch from GitHub.
- Keep `calculator.py` short (≤60 lines) so LLM prompts stay within context limits.

---

### Sub-Task 2 — Schemas (Strict JSON Contracts)

**Status:** `[x] done`

**Intent:**
Define Pydantic models that every reviewer and the coordinator must produce. Strict schemas prevent reviewers from inventing data — if a field is absent or the wrong type, parsing fails loudly rather than silently.

**Expected Outcomes:**
- `mergeproof/schemas.py` defines `Finding`, `ReviewerOutput`, and `CoordinatorReport`.
- All fields are typed; optional fields are explicit `Optional[...]`.
- `Finding` has: `severity` (Literal["critical","high","medium","low","info"]), `category` (Literal["correctness","security","performance","test_coverage"]), `file`, `line` (int | None), `evidence` (verbatim code snippet), `explanation`, `recommendation`.
- `ReviewerOutput` has: `reviewer_name`, `findings: list[Finding]`, `is_demo: bool`.
- `CoordinatorReport` has: `findings: list[Finding]`, `overall_risk` (Literal["critical","high","medium","low"]), `summary`, `is_demo: bool`.
- `PatchResult` has: `patch_diff`, `explanation`, `is_demo: bool`.
- `TestRunResult` has: `passed: int`, `failed: int`, `errors: int`, `output: str`.
- `ReReviewResult` has: `previous_risk`, `new_risk`, `risk_decreased: bool`, `summary`.

**Todo List:**
1. Write `mergeproof/schemas.py` with all models above.
2. Ensure all Pydantic models use `model_config = ConfigDict(extra="forbid")` to reject unexpected fields.
3. Write `tests/test_schemas.py` that instantiates each model with valid data and asserts round-trip JSON serialization.

**Relevant Context:**
- `extra="forbid"` is the key guard against invented fields.
- `evidence` must be a direct verbatim quote from the diff — reviewers are instructed to copy-paste, not paraphrase.

---

### Sub-Task 3 — Reviewer Module (Parallel LLM Calls)

**Status:** `[x] done`

**Intent:**
Implement four specialized reviewers — correctness, security, performance, test_coverage — each as a callable that returns a validated `ReviewerOutput`. Run all four in parallel via `ThreadPoolExecutor`. Include a `DEMO_MODE` fallback in `demo_mode.py` that returns clearly labeled synthetic findings.

**Expected Outcomes:**
- `mergeproof/reviewer.py` exports `run_all_reviewers(diff: str, repo_files: dict[str, str]) -> list[ReviewerOutput]`.
- Each reviewer sends a focused system prompt + the diff to the LLM and parses the JSON response into `ReviewerOutput`.
- If parsing fails (malformed JSON or schema violation), the reviewer returns an empty `ReviewerOutput` with a single `info`-severity finding explaining the parse error — never raises an unhandled exception.
- `DEMO_MODE` returns `ReviewerOutput` objects with `is_demo=True` and realistic but clearly synthetic findings.
- `ThreadPoolExecutor(max_workers=4)` runs all four reviewers concurrently.
- `tests/test_reviewer_output.py` confirms that the JSON contract is never violated.

**Todo List:**
1. Write `mergeproof/demo_mode.py` with four hard-coded `ReviewerOutput` objects, each with `is_demo=True` and at least two findings covering the demo fixture's known issues.
2. Write `mergeproof/reviewer.py`:
   a. Define a `_build_prompt(role: str, diff: str, repo_files: dict) -> list[dict]` helper that builds the messages list.
   b. The system prompt must instruct the LLM to output ONLY a JSON object matching `ReviewerOutput`, quote evidence verbatim from the diff, never invent file names or line numbers not present in the diff.
   c. Implement `_call_reviewer(role, diff, repo_files) -> ReviewerOutput` with try/except around the LLM call and JSON parse.
   d. Implement `run_all_reviewers` using `ThreadPoolExecutor`.
3. Write `tests/test_reviewer_output.py` that feeds each demo-mode output through `ReviewerOutput.model_validate()`.

**Relevant Context:**
- System prompt strictness is the primary correctness guardrail — the schema is the secondary.
- Prompt template must include: "Return ONLY valid JSON. Do not include markdown fences. Do not invent file paths or line numbers not present in the diff."
- `openai` client is initialized once and shared (thread-safe for reads).

---

### Sub-Task 4 — Coordinator Module

**Status:** `[x] done`

**Intent:**
The coordinator merges findings from all four reviewers, deduplicates overlapping issues, assigns an `overall_risk` level, and writes a prose summary. It also calls the LLM once (or uses demo mode) to produce the final `CoordinatorReport`.

**Expected Outcomes:**
- `mergeproof/coordinator.py` exports `coordinate(reviewer_outputs: list[ReviewerOutput]) -> CoordinatorReport`.
- Deduplication: findings with the same `file` + `line` + `category` are merged (highest severity wins).
- `overall_risk` is derived from the highest-severity finding present.
- The coordinator calls the LLM with a synthesis prompt (or returns demo-mode data).
- `tests/test_coordinator.py` covers: empty input → low risk; all-critical input → critical risk; deduplication logic.

**Todo List:**
1. Write `mergeproof/coordinator.py`:
   a. `_deduplicate(findings: list[Finding]) -> list[Finding]` — group by (file, line, category), keep highest severity.
   b. `_derive_overall_risk(findings: list[Finding]) -> str` — map severity ordering to overall risk.
   c. `coordinate()` — deduplicate, then either call LLM for summary or use demo mode.
   d. LLM prompt: "Given these findings as JSON, write a 2-3 sentence executive summary and confirm the overall_risk field."
2. Write `tests/test_coordinator.py` with the three cases above.

**Relevant Context:**
- Severity ordering: critical > high > medium > low > info.
- `is_demo` on `CoordinatorReport` is `True` if ANY input `ReviewerOutput.is_demo` is `True`.

---

### Sub-Task 5 — Patch Generator

**Status:** `[x] done`

**Intent:**
Given the coordinator report and the original diff, ask the LLM to produce a corrected unified diff patch and a plain-English explanation. The patch generator never applies the patch — it only produces text. Demo mode returns a pre-written patch.

**Expected Outcomes:**
- `mergeproof/patch_generator.py` exports `generate_patch(report: CoordinatorReport, original_diff: str, repo_files: dict[str, str]) -> PatchResult`.
- LLM is asked to produce ONLY a unified diff (no markdown fences, no prose outside the `PatchResult` JSON envelope).
- `PatchResult.patch_diff` is a valid unified diff string.
- `PatchResult.explanation` is ≤5 sentences.
- Demo mode returns a hard-coded patch fixing the known demo issues.

**Todo List:**
1. Write `mergeproof/patch_generator.py` with `generate_patch()`.
2. Prompt instructs: "Return ONLY a JSON object with fields patch_diff (unified diff string) and explanation (≤5 sentences). Do not invent changes to files not in the diff."
3. Add demo-mode patch to `mergeproof/demo_mode.py`.

**Relevant Context:**
- The patch is displayed as read-only text in the UI — no file system writes happen during the demo.
- Validation: `patch_diff` must start with `---` or be empty string (never `None`).

---

### Sub-Task 6 — Test Runner

**Status:** `[x] done`

**Intent:**
Run `pytest` on `demo/tests/` and capture pass/fail/error counts and stdout. This gives the "tests after fix" step a concrete result rather than simulated output.

**Expected Outcomes:**
- `mergeproof/test_runner.py` exports `run_tests(test_dir: str = "demo/tests") -> TestRunResult`.
- Uses `subprocess.run(["pytest", test_dir, "--tb=short", "-q"])` with captured output.
- Parses the summary line (e.g., `2 passed, 1 failed`) into `TestRunResult` fields.
- Never raises — always returns a `TestRunResult` (with error output in `.output` on failure).
- Works correctly when called from the repo root.

**Todo List:**
1. Write `mergeproof/test_runner.py`.
2. Regex to parse pytest summary: `r"(\d+) passed"`, `r"(\d+) failed"`, `r"(\d+) error"`.
3. Add a test in `tests/` that calls `run_tests("demo/tests")` and asserts it returns a `TestRunResult` with `passed >= 1`.

**Relevant Context:**
- Demo tests are intentionally partial — expect some failures before the patch, and the demo shows improvement after.
- Must not `sys.exit` or call `pytest.main()` directly (interferes with Streamlit's process).

---

### Sub-Task 7 — Re-Review Module

**Status:** `[x] done`

**Intent:**
After the patch is displayed and tests run, re-review the patched diff to show risk reduction. Reuses `run_all_reviewers` and `coordinate` on the patched diff. Produces a `ReReviewResult` comparing before/after risk.

**Expected Outcomes:**
- `mergeproof/coordinator.py` gains `compare_risk(before: CoordinatorReport, after: CoordinatorReport) -> ReReviewResult`.
- `ReReviewResult.risk_decreased` is `True` if after risk is lower than before.
- Demo mode: after risk is always "low" (showing the demo works end-to-end).

**Todo List:**
1. Add `compare_risk()` to `mergeproof/coordinator.py`.
2. Add `ReReviewResult` usage in `demo_mode.py`.
3. The patched diff for demo mode is the same as the patch from Sub-Task 5 applied to `sample.diff` (pre-computed string, not live `patch` subprocess).

**Relevant Context:**
- Risk ordering for comparison: critical=4, high=3, medium=2, low=1, info=0.

---

### Sub-Task 8 — Streamlit UI (`app.py`)

**Status:** `[x] done`

**Intent:**
Wire everything together in a single-page Streamlit app with a clear linear flow. The UI must show DEMO_MODE prominently when active. Each step (review → coordinate → patch → test → re-review) is triggered by a button, and results are displayed with color-coded severity badges.

**Expected Outcomes:**
- `app.py` is the sole entry point (`streamlit run app.py`).
- Page layout:
  1. **Header** — "MergeProof" title + DEMO MODE warning banner if applicable.
  2. **Diff Viewer** — Shows `demo/sample.diff` in a code block.
  3. **"Run Review" button** — Triggers parallel reviewers, shows spinner, then displays findings table.
  4. **Findings Table** — Columns: Severity (color-coded), Category, File, Line, Evidence, Explanation, Recommendation. Severity uses `st.badge` or colored markdown.
  5. **"Generate Patch" button** — Shows patch diff and explanation.
  6. **"Run Tests" button** — Shows pass/fail/error counts and raw output.
  7. **"Re-Review" button** — Shows before/after risk comparison with a clear risk-decreased indicator.
- `st.session_state` stores results between button presses so the page doesn't reset.
- DEMO_MODE is detected at startup from env vars and shown as a persistent warning.

**Todo List:**
1. Write `app.py`.
2. Import `run_all_reviewers`, `coordinate`, `generate_patch`, `run_tests`, `compare_risk`.
3. Load `demo/sample.diff` and `demo/repo/calculator.py` at startup (not on each button press).
4. Use `st.spinner("Running 4 reviewers in parallel…")` during review.
5. Render findings using `st.dataframe` or `st.table` with severity color mapping: critical=🔴, high=🟠, medium=🟡, low=🔵, info=⚪.
6. Display DEMO_MODE banner: `st.warning("⚠️ DEMO MODE — findings are synthetic, not live AI output.")`.
7. Use `st.code(patch_diff, language="diff")` for the patch display.
8. Use `st.metric` for test pass/fail counts.

**Relevant Context:**
- Streamlit re-runs the entire script on each interaction — all expensive calls must be gated by `st.session_state` checks, not re-executed.
- Do not use `st.experimental_rerun()` — deprecated in Streamlit ≥1.27.

---

### Sub-Task 9 — AGENTS.md

**Status:** `[x] done`

**Intent:**
Document project-specific non-obvious facts for AI assistants working in this repo.

**Expected Outcomes:**
- `AGENTS.md` exists in the project root with commands, env var notes, and key non-obvious patterns.

**Todo List:**
1. Write `AGENTS.md` covering: run command, test command, env vars, schema strictness requirement, DEMO_MODE behavior, reviewer prompt constraints.

---

## Commands

```bash
# Install
pip install -r requirements.txt

# Run the app
streamlit run app.py

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_schemas.py -v

# Run a single test function
pytest tests/test_coordinator.py::test_deduplication -v
```

---

## Acceptance Criteria

1. `streamlit run app.py` starts without errors in both live and DEMO_MODE.
2. DEMO_MODE banner is visible and clearly labeled when `OPENAI_API_KEY` is absent.
3. "Run Review" completes in <15 seconds in DEMO_MODE; shows all four reviewer categories.
4. Every finding has all required fields (severity, category, file, line, evidence, explanation, recommendation).
5. `pytest tests/ -v` passes with zero failures.
6. `pytest demo/tests/ -v` shows at least one failure before the patch (proving the demo fixture is realistic).
7. Re-review shows `risk_decreased: True` in the demo path.
8. No unhandled exceptions on the happy demo path.
9. Reviewer module never invents data — all evidence strings are substring matches of `sample.diff`.

---

## Risk Log

| Risk | Mitigation |
|---|---|
| LLM returns non-JSON | `try/except` + fallback to parse-error finding; never crashes |
| LLM invents line numbers | Prompt instructs verbatim quoting; schema doesn't validate against diff, but UI shows evidence for human spot-check |
| `pytest` subprocess path issues | Always invoke from repo root; `test_runner.py` uses `Path(__file__).parent.parent / "demo/tests"` as default |
| Streamlit re-run clears state | All results stored in `st.session_state` with explicit keys |
| Hackathon time pressure | Sub-tasks 1–4 and 8 are the minimum viable demo; 5–7 are the "wow factor" layer |
