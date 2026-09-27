# MergeProof

**Evidence-first AI pull-request reviewer** — built for the IBM Bob 2.0 Hackathon.

MergeProof fans out to four specialised AI reviewers in parallel, combines their findings into a unified risk report, generates a suggested fix, runs tests before and after the patch, and re-reviews the result to prove risk has decreased.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2a. Run in DEMO_MODE (no API key needed)
DEMO_MODE=true streamlit run app.py

# 2b. Run with live AI
#     Copy .env.example → .env, fill in OPENAI_API_KEY
streamlit run app.py
```

Open **http://localhost:8501** and follow the nine-step golden path.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                      app.py (Streamlit UI)          │
└───────────┬─────────────────────────────────────────┘
            │
            ▼
   run_all_reviewers()          ← reviewer.py
   ThreadPoolExecutor(4)        ← parallel LLM calls
   ┌──────────┬───────────┬──────────────┬──────────────┐
   │correctness│ security  │ performance  │test_coverage │
   └──────────┴───────────┴──────────────┴──────────────┘
            │
            ▼
   coordinate()                 ← coordinator.py
   (deduplicate · risk · LLM summary)
            │
            ▼
   generate_patch()             ← patch_generator.py
   (LLM unified-diff fix)
            │
            ▼
   run_tests(before / after)    ← test_runner.py
   (subprocess pytest)
            │
            ▼
   rerun_review() → compare_risk()   ← coordinator.py
   (before vs after risk delta)
            │
            ▼
   All data validated by strict Pydantic models
   (schemas.py — extra="forbid" on every model)
```

### Key files

| File | Role |
|---|---|
| `app.py` | Streamlit single-page app — sole entry point |
| `mergeproof/schemas.py` | Pydantic data contracts (`extra="forbid"`) |
| `mergeproof/reviewer.py` | Four specialised reviewers + `ThreadPoolExecutor` |
| `mergeproof/coordinator.py` | Dedup · risk · LLM summary · re-review |
| `mergeproof/patch_generator.py` | AI fix-diff generation |
| `mergeproof/test_runner.py` | `subprocess pytest` wrapper |
| `mergeproof/demo_mode.py` | Pre-computed demo fixtures (all `is_demo=True`) |
| `mergeproof/ui_helpers.py` | Pure helper functions (severity badges, table rows) |
| `demo/repo/calculator.py` | **Intentionally flawed** demo source — never modify |
| `demo/repo/calculator_fixed.py` | Patched version used by `demo/tests_fixed/` |
| `demo/sample.diff` | Pre-prepared unified diff for the demo |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | No | — | Absent → DEMO_MODE activates automatically |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Any OpenAI chat-completion model |
| `DEMO_MODE` | No | `false` | Force demo even when key is present |

---

## Demo Mode

When `OPENAI_API_KEY` is absent **or** `DEMO_MODE=true`, the app runs entirely from pre-computed fixtures in `mergeproof/demo_mode.py`. Every finding, patch, and re-review result is clearly labelled `[DEMO MODE]` in the UI and in `is_demo=True` on every schema object. No LLM calls are made.

---

## Running Tests

```bash
# Full suite (219 pass, 1 intentional failure in demo/tests/)
python -m pytest tests/ demo/tests/ demo/tests_fixed/ -v

# Unit tests only
python -m pytest tests/ -v

# Single test
python -m pytest tests/test_coordinator.py::TestDeduplicate::test_empty_list -v
```

The single failure (`test_divide_by_zero` in `demo/tests/`) is **intentional** — it proves the demo bug is real and is the correctness finding the reviewer catches.

---

## IBM Bob Integration

MergeProof was built with IBM Bob 2.0 as the primary development assistant. Bob was used to:

- Generate the full implementation plan (`mergeproof-plan.md`) from requirements
- Implement all nine sub-tasks one at a time, running tests after each
- Maintain the AGENTS.md file so future Bob sessions have immediate context

To continue development with Bob, open this repository and Bob will read `AGENTS.md` automatically.

---

## Limitations & Known Issues

- **`ast.literal_eval` scope**: The patched `evaluate()` only accepts numeric literals (`42`, `3.14`), not arithmetic expressions. This is correct and intentional — the security fix restricts to safe-only input.
- **`TestRunResult` pytest warning**: Pytest sees `TestRunResult` (a Pydantic model in `schemas.py`) as a potential test class and emits a `PytestCollectionWarning`. This is cosmetic and does not affect test results.
- **Python 3.14 + Streamlit**: Streamlit ≥1.35 runs on Python 3.14 but some PATH entries for scripts may not be registered. Use `python -m streamlit run app.py` (not bare `streamlit`).
- **Live mode latency**: Four parallel LLM calls to `gpt-4o-mini` typically complete in 5–15 seconds. The spinner is shown during this period.
- **No authentication, webhooks, or database** — out of scope by design for the hackathon.

---

## Project Structure

```
MergeProof/
├── app.py                        # Streamlit entry point
├── requirements.txt
├── .env.example
├── pytest.ini
├── AGENTS.md                     # AI assistant guidance
├── README.md
├── DEMO_SCRIPT.md                # 60–90 second presentation script
├── PITCH.md                      # Hackathon pitch document
├── mergeproof-plan.md            # Original implementation plan
├── demo/
│   ├── sample.diff               # Demo unified diff
│   ├── repo/
│   │   ├── calculator.py         # Flawed original (never modify)
│   │   └── calculator_fixed.py  # Patched version
│   ├── tests/                    # Pre-patch tests (1 intentional failure)
│   └── tests_fixed/              # Post-patch tests (all green)
├── mergeproof/
│   ├── schemas.py
│   ├── reviewer.py
│   ├── coordinator.py
│   ├── patch_generator.py
│   ├── test_runner.py
│   ├── demo_mode.py
│   └── ui_helpers.py
└── tests/
    ├── test_schemas.py
    ├── test_reviewer_output.py
    ├── test_coordinator.py
    ├── test_patch_generator.py
    ├── test_test_runner.py
    ├── test_rereview.py
    └── test_ui_helpers.py
```
