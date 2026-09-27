# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Start the app (DEMO_MODE — no API key needed)
DEMO_MODE=true streamlit run app.py

# Start the app with live AI (requires OPENAI_API_KEY in .env)
streamlit run app.py

# Run all tests
python -m pytest tests/ demo/tests/ demo/tests_fixed/ -v

# Run a single test file
python -m pytest tests/test_schemas.py -v

# Run a single test function
python -m pytest tests/test_coordinator.py::TestCoordinate::test_empty_input_returns_low_risk -v
```

## Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | No | — | If absent → DEMO_MODE activates automatically |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Override for any OpenAI chat model |
| `DEMO_MODE` | No | `false` | Force DEMO_MODE even when API key is present |

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` for live mode.

## DEMO_MODE Behaviour — Non-Obvious

- `DEMO_MODE` is computed **at module import time** in `reviewer.py`, `coordinator.py`, and `patch_generator.py`. Changing `os.environ` after import has no effect. Tests that toggle DEMO_MODE must use `monkeypatch.setattr(mod, "DEMO_MODE", True/False)`.
- All four reviewer engines (`reviewer.py`), the coordinator (`coordinator.py`), the patch generator (`patch_generator.py`), and `rerun_review` in `coordinator.py` check their own module-level `DEMO_MODE` flag independently.
- Demo fixtures live in `mergeproof/demo_mode.py`. Edit that file to change demo output — never edit the Pydantic models in `schemas.py`.

## Schema Strictness — Critical

- Every Pydantic model uses `model_config = ConfigDict(extra="forbid")`. Adding any field not declared in `schemas.py` raises `ValidationError` immediately.
- `Finding.category` is `Literal["correctness","security","performance","test_coverage"]` — exactly. Reviewer prompts must use these exact strings.
- `CoordinatorReport.overall_risk` is `Literal["critical","high","medium","low"]` — `"info"` is **not** a valid risk level (it maps to `"low"` in `_derive_overall_risk`).
- `PatchResult.patch_diff` must start with `"---"` or be `""` — never `None`.

## Reviewer Prompt Constraints

- System prompts in `reviewer.py` must contain: `"Return ONLY valid JSON"`, `"Do not include markdown fences"`, `"Do not invent file paths or line numbers not present in the diff"`, `"Copy evidence verbatim"`.
- The `category` field in each finding is **clamped** to the reviewer's own role inside `_call_reviewer` — LLM output is corrected before schema validation.
- Parse errors never raise: `_call_reviewer` catches all exceptions and returns a `ReviewerOutput` with a single `info`-severity finding describing the error.

## Test Fixture Rules — Non-Obvious

- `demo/tests/test_calculator.py::test_divide_by_zero` **intentionally fails** — `ZeroDivisionError` vs expected `ValueError`. Do not fix it; this failure is the demo's correctness story.
- `demo/repo/calculator.py` must **never be modified**. The patched version is `demo/repo/calculator_fixed.py`.
- `demo/tests_fixed/` runs against `calculator_fixed.py` and must always be green (0 failures).
- `run_tests()` in `test_runner.py` uses `sys.executable -m pytest` — not bare `pytest` — to avoid PATH issues in virtual environments.

## Architecture at a Glance

```
app.py  →  run_all_reviewers()   [reviewer.py — 4 parallel LLM calls]
       →  coordinate()           [coordinator.py — dedup + risk + summary]
       →  generate_patch()       [patch_generator.py — LLM fix diff]
       →  run_tests()            [test_runner.py — subprocess pytest]
       →  rerun_review()         [coordinator.py — re-review + compare_risk]
```

All data flows through strict Pydantic models defined in `mergeproof/schemas.py`. UI helpers in `mergeproof/ui_helpers.py` are pure functions (no Streamlit imports) and are fully unit-tested.
