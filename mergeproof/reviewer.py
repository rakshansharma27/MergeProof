"""
reviewer.py — four specialised AI reviewers run in parallel.

Public API
----------
run_all_reviewers(diff, repo_files) -> list[ReviewerOutput]

Each reviewer sends a focused system prompt + diff to the LLM and parses
the response into a validated ReviewerOutput.  If the LLM returns
malformed JSON or a schema violation the reviewer returns an empty
ReviewerOutput with a single info-severity finding describing the error —
it never raises an unhandled exception.

DEMO_MODE is active when OPENAI_API_KEY is absent or DEMO_MODE=true.
In that case the pre-computed outputs from demo_mode.py are returned
immediately (no LLM calls are made).
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from mergeproof.schemas import Finding, ReviewerOutput

load_dotenv()

# ---------------------------------------------------------------------------
# DEMO_MODE detection (evaluated once at import time)
# ---------------------------------------------------------------------------

_FORCE_DEMO = os.getenv("DEMO_MODE", "false").lower() == "true"
_HAS_KEY = bool(os.getenv("OPENAI_API_KEY", "").strip())
DEMO_MODE: bool = _FORCE_DEMO or not _HAS_KEY

# ---------------------------------------------------------------------------
# OpenAI client (initialised lazily; None in DEMO_MODE)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Return the shared OpenAI client, creating it on first use."""
    global _client
    if _client is None:
        from openai import OpenAI  # deferred so demo mode never imports openai
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Reviewer role definitions
# ---------------------------------------------------------------------------

_ROLES: list[str] = ["correctness", "security", "performance", "test_coverage"]

_ROLE_FOCUS: dict[str, str] = {
    "correctness": (
        "logic errors, unhandled edge cases, incorrect calculations, "
        "missing error handling, and runtime exceptions."
    ),
    "security": (
        "injection vulnerabilities (SQL, command, eval), insecure use of "
        "dangerous built-ins, missing input validation, and data exposure."
    ),
    "performance": (
        "unnecessary allocations, redundant loops, O(n) operations that "
        "could be O(1), and missing use of built-in optimised functions."
    ),
    "test_coverage": (
        "untested public functions, missing edge-case tests, absence of "
        "negative-input tests, and security-relevant paths with no coverage."
    ),
}

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """\
You are a specialised code reviewer focused exclusively on {focus}

Your task: review the unified diff below and return a JSON object that \
conforms EXACTLY to this schema:

{{
  "reviewer_name": "{role}",
  "findings": [
    {{
      "severity": "<critical|high|medium|low|info>",
      "category": "{role}",
      "file": "<filename from the diff header>",
      "line": <integer line number from the diff, or null>,
      "evidence": "<verbatim line(s) copied from the diff>",
      "explanation": "<why this is a problem>",
      "recommendation": "<concrete fix>"
    }}
  ],
  "is_demo": false
}}

STRICT RULES — violation causes the entire response to be discarded:
1. Return ONLY valid JSON. Do not include markdown fences or any prose.
2. Do not invent file paths or line numbers not present in the diff.
3. Copy evidence verbatim from the diff — do not paraphrase.
4. Only report issues relevant to your specific focus area.
5. If you find no issues, return an empty findings list.
6. The "category" field must always be exactly "{role}".
"""


def _build_prompt(role: str, diff: str, repo_files: dict[str, str]) -> list[dict]:
    """Build the messages list for the given reviewer role."""
    system = _SYSTEM_TEMPLATE.format(role=role, focus=_ROLE_FOCUS[role])
    repo_context = ""
    if repo_files:
        parts = [f"### {name}\n```python\n{content}\n```" for name, content in repo_files.items()]
        repo_context = "\n\nFull repository snapshot for context:\n" + "\n\n".join(parts)
    user_content = f"Diff to review:\n```diff\n{diff}\n```{repo_context}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Single-reviewer call (safe — never raises)
# ---------------------------------------------------------------------------

def _parse_error_output(role: str, message: str) -> ReviewerOutput:
    """Return a well-formed ReviewerOutput describing a parse/call failure."""
    return ReviewerOutput(
        reviewer_name=role,
        is_demo=False,
        findings=[
            Finding(
                severity="info",
                category="correctness",  # closest neutral category
                file="(reviewer error)",
                line=None,
                evidence="",
                explanation=f"[{role} reviewer] {message}",
                recommendation="Check the application logs and retry the review.",
            )
        ],
    )


def _call_reviewer(role: str, diff: str, repo_files: dict[str, str]) -> ReviewerOutput:
    """Call the LLM for one reviewer role and return a validated ReviewerOutput.

    On any failure (network, JSON, schema) returns a parse-error output
    instead of raising.
    """
    messages = _build_prompt(role, diff, repo_files)
    try:
        response = _get_client().chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0.1,  # low temperature for deterministic structured output
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        return _parse_error_output(role, f"LLM call failed: {exc}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _parse_error_output(role, f"LLM returned non-JSON: {exc}")

    # Ensure reviewer_name and is_demo are set correctly regardless of LLM output
    data["reviewer_name"] = role
    data["is_demo"] = False

    # Clamp category on each finding to the reviewer's own role
    for f in data.get("findings", []):
        if isinstance(f, dict):
            f["category"] = role

    try:
        return ReviewerOutput.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return _parse_error_output(role, f"Schema validation failed: {exc}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_all_reviewers(diff: str, repo_files: dict[str, str]) -> list[ReviewerOutput]:
    """Run all four specialised reviewers and return their outputs.

    In DEMO_MODE the pre-computed outputs from demo_mode.py are returned
    immediately — no LLM calls are made.

    In live mode all four reviewers run concurrently via ThreadPoolExecutor.
    """
    if DEMO_MODE:
        from mergeproof.demo_mode import DEMO_REVIEWER_OUTPUTS
        return list(DEMO_REVIEWER_OUTPUTS)

    results: list[ReviewerOutput] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_call_reviewer, role, diff, repo_files): role
            for role in _ROLES
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Sort into a stable order for consistent UI display
    role_order = {r: i for i, r in enumerate(_ROLES)}
    results.sort(key=lambda ro: role_order.get(ro.reviewer_name, 99))
    return results
