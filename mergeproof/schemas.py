"""
schemas.py — strict Pydantic models for all MergeProof data contracts.

Every reviewer, coordinator, patch generator, test runner, and re-review
module must produce and consume only these models.  extra="forbid" ensures
that LLM outputs with invented fields are rejected at parse time, not
silently passed through.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared severity and category literals
# ---------------------------------------------------------------------------

Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["correctness", "security", "performance", "test_coverage"]
RiskLevel = Literal["critical", "high", "medium", "low"]


# ---------------------------------------------------------------------------
# Core finding — one discrete issue discovered by a reviewer
# ---------------------------------------------------------------------------

class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Severity
    category: Category
    file: str
    line: Optional[int] = None
    evidence: str        # verbatim snippet copied from the diff — never paraphrased
    explanation: str
    recommendation: str


# ---------------------------------------------------------------------------
# Output of a single specialised reviewer
# ---------------------------------------------------------------------------

class ReviewerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_name: str
    findings: list[Finding]
    is_demo: bool


# ---------------------------------------------------------------------------
# Coordinator's unified report (merges all reviewer outputs)
# ---------------------------------------------------------------------------

class CoordinatorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]
    overall_risk: RiskLevel
    summary: str
    is_demo: bool


# ---------------------------------------------------------------------------
# Suggested patch produced by the patch generator
# ---------------------------------------------------------------------------

class PatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_diff: str      # unified diff string; starts with "---" or is ""
    explanation: str
    is_demo: bool


# ---------------------------------------------------------------------------
# Result of running pytest on demo/tests/
# ---------------------------------------------------------------------------

class TestRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: int
    failed: int
    errors: int
    output: str


# ---------------------------------------------------------------------------
# Before/after risk comparison produced by the re-review step
# ---------------------------------------------------------------------------

class ReReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_risk: RiskLevel
    new_risk: RiskLevel
    risk_decreased: bool
    summary: str
