"""
patch_generator.py — generates a suggested fix patch from a CoordinatorReport.

Public API
----------
generate_patch(report, original_diff, repo_files) -> PatchResult

The patch generator asks the LLM to produce a corrected unified diff and a
plain-English explanation (≤5 sentences).  It never applies the patch to disk;
the result is read-only text for display in the UI.

DEMO_MODE: returns DEMO_PATCH_RESULT from demo_mode.py immediately.
Live mode: calls the LLM once with the findings + original diff and parses
           the JSON response into a PatchResult.

On any failure (LLM error, JSON parse error, schema violation) a PatchResult
with patch_diff="" and the error message in explanation is returned —
generate_patch() never raises an unhandled exception.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from mergeproof.schemas import CoordinatorReport, PatchResult

load_dotenv()

# ---------------------------------------------------------------------------
# Optional OpenAI import (None when the package is not installed)
# ---------------------------------------------------------------------------

try:
    from openai import OpenAI as _OpenAIClass
except ImportError:  # pragma: no cover
    _OpenAIClass = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# DEMO_MODE detection (mirrors reviewer.py / coordinator.py)
# ---------------------------------------------------------------------------

_FORCE_DEMO = os.getenv("DEMO_MODE", "false").lower() == "true"
_HAS_KEY = bool(os.getenv("OPENAI_API_KEY", "").strip())
DEMO_MODE: bool = _FORCE_DEMO or not _HAS_KEY

_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Public alias so tests can mock it via mergeproof.patch_generator.OpenAI
OpenAI = _OpenAIClass

# ---------------------------------------------------------------------------
# Fallback helper
# ---------------------------------------------------------------------------

def _error_result(message: str) -> PatchResult:
    """Return a PatchResult describing a failure; patch_diff is always ''."""
    return PatchResult(
        patch_diff="",
        explanation=f"[patch_generator] {message}",
        is_demo=False,
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a senior software engineer tasked with fixing every issue listed in a \
code-review findings report.

Return ONLY a JSON object with exactly two fields:
  "patch_diff"  — a valid unified diff string that fixes ALL findings.
                  Start the diff with "---".  Do not wrap it in markdown \
fences.
                  Do not invent changes to files not present in the original diff.
  "explanation" — a plain-English summary of the changes made, in 5 sentences \
or fewer.
                  No JSON, no markdown — just the sentences.

STRICT RULES:
1. Return ONLY the JSON object.  No prose before or after it.
2. Do not include markdown code fences (no ```).
3. Only modify files that appear in the original diff.
4. Every finding in the report must be addressed by at least one hunk.
5. The patch_diff must be a syntactically valid unified diff.
"""


def _build_patch_prompt(
    report: CoordinatorReport,
    original_diff: str,
    repo_files: dict[str, str],
) -> list[dict]:
    """Build the messages list for the patch-generation LLM call."""
    findings_json = json.dumps(
        [f.model_dump() for f in report.findings], indent=2
    )
    repo_context = ""
    if repo_files:
        parts = [
            f"### {name}\n```python\n{content}\n```"
            for name, content in repo_files.items()
        ]
        repo_context = "\n\nFull repository snapshot:\n" + "\n\n".join(parts)

    user_content = (
        f"Overall risk: {report.overall_risk}\n\n"
        f"Findings to fix:\n{findings_json}\n\n"
        f"Original diff:\n```diff\n{original_diff}\n```"
        f"{repo_context}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_patch(
    report: CoordinatorReport,
    original_diff: str,
    repo_files: dict[str, str],
) -> PatchResult:
    """Generate a suggested fix patch for all findings in the report.

    DEMO_MODE: returns DEMO_PATCH_RESULT immediately (no LLM call).
    Live mode: calls the LLM, validates the JSON response, returns PatchResult.
    On any failure, returns a PatchResult with patch_diff="" and the error
    in explanation — never raises.
    """
    if DEMO_MODE or report.is_demo:
        from mergeproof.demo_mode import DEMO_PATCH_RESULT
        return DEMO_PATCH_RESULT

    messages = _build_patch_prompt(report, original_diff, repo_files)

    # --- LLM call ---
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        return _error_result(f"LLM call failed: {exc}")

    # --- JSON parse ---
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _error_result(f"LLM returned non-JSON: {exc}")

    # --- Normalise and validate ---
    # Ensure is_demo is always set correctly regardless of LLM output.
    data["is_demo"] = False

    # Enforce the patch_diff invariant: must be str, starts with "---" or is "".
    patch_diff = data.get("patch_diff", "")
    if not isinstance(patch_diff, str):
        patch_diff = ""
    if patch_diff and not patch_diff.lstrip().startswith("---"):
        # LLM may have wrapped the diff in a markdown fence; strip it.
        lines = patch_diff.splitlines()
        stripped = [
            l for l in lines
            if not l.startswith("```")
        ]
        patch_diff = "\n".join(stripped).strip()
        if not patch_diff.startswith("---"):
            patch_diff = ""  # could not recover a valid diff
    data["patch_diff"] = patch_diff

    try:
        return PatchResult.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return _error_result(f"Schema validation failed: {exc}")
