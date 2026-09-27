# MergeProof — IBM Bob 2.0 Hackathon Pitch

## Problem

Pull-request review is a bottleneck in every engineering team.
AI assistants can summarise code, but their review comments are typically vague,
ungrounded, and impossible to verify — they hallucinate file names, line numbers,
and severity ratings.
When an AI says "there may be a security issue", a reviewer has no idea
whether to block the PR or ignore it.

**The root problem: AI PR review lacks evidence.**

---

## Solution

MergeProof is an **evidence-first AI pull-request reviewer**.

Every finding it produces has:
- **Severity** — critical / high / medium / low / info
- **Category** — correctness, security, performance, or test coverage
- **File + line** — taken directly from the diff header
- **Evidence** — a verbatim snippet copied from the diff (never paraphrased)
- **Explanation** — why this is a problem
- **Recommendation** — a concrete fix

If a finding doesn't have evidence from the diff, the schema rejects it.
**MergeProof cannot hallucinate a file name or line number that isn't in the diff.**

---

## The Full Workflow

```
Load PR diff
    ↓
4 specialised reviewers (parallel) — correctness · security · performance · test coverage
    ↓
Coordinator — deduplicate · risk scoring · executive summary
    ↓
Patch generator — AI-generated unified diff fixing all findings
    ↓
Test runner — pytest before the patch (1 failure) → after the patch (0 failures)
    ↓
Re-reviewer — re-runs all reviewers on the patched diff
    ↓
Risk comparison — CRITICAL → LOW, 8 findings resolved, 1 minor gap remains
```

---

## Differentiation

| Feature | MergeProof | Generic AI review |
|---|---|---|
| Evidence-grounded findings | ✅ Verbatim diff quotes | ❌ Free-form prose |
| Schema-validated output | ✅ Pydantic `extra="forbid"` | ❌ Unstructured |
| Specialised reviewers | ✅ 4 parallel focused calls | ❌ One generic prompt |
| Suggested fix | ✅ Unified diff patch | ❌ Prose suggestions |
| Test before/after | ✅ Real pytest execution | ❌ Not supported |
| Re-review with risk delta | ✅ Quantified improvement | ❌ Not supported |
| DEMO_MODE (no API key) | ✅ Clearly labeled fallback | ❌ N/A |

---

## Technology Stack

- **Python 3.11+** — runtime
- **Streamlit** — single-page UI, zero-config deployment
- **OpenAI `gpt-4o-mini`** — four specialised reviewer calls + coordinator summary + patch generation
- **Pydantic v2** — strict JSON schema validation (`extra="forbid"`) on every LLM response
- **`ThreadPoolExecutor`** — four reviewers run concurrently, not sequentially
- **`subprocess` pytest** — real test execution, not mocked
- **IBM Bob 2.0** — primary development assistant throughout the build

---

## IBM Bob Usage

MergeProof was built **entirely with IBM Bob 2.0** as the coding assistant:

1. Bob generated the full 9-sub-task implementation plan from the product requirements
2. Bob implemented each sub-task sequentially, running the test suite after every step
3. Bob maintained `AGENTS.md` so each new session had immediate project context
4. Bob identified and fixed three bugs during implementation (module-level import for testability, `ast.literal_eval` scope, and a test helper sentinel pattern)

The build followed Bob's Plan → Agent workflow throughout, with the plan file (`mergeproof-plan.md`) updated as each sub-task was marked done.

---

## Demo Scenario

The demo uses a pre-prepared Python calculator that has three intentional flaws:

1. **Correctness** — `divide()` raises `ZeroDivisionError` instead of `ValueError`
2. **Security** — `evaluate()` calls `eval()` on unsanitised user input
3. **Performance** — `sum_range()` uses a two-loop O(n) algorithm where O(1) is trivial

MergeProof finds all three, generates a patch, proves the fix with pytest (9→18 tests, 1 failure → 0 failures), and shows risk drop from **CRITICAL to LOW**.

---

## Limitations (Honest)

- `ast.literal_eval` only evaluates numeric literals, not arithmetic expressions — the patched `evaluate()` is safer but more restrictive than the original
- Live mode requires an `OPENAI_API_KEY` and incurs per-token costs (~$0.001 per full review with `gpt-4o-mini`)
- No GitHub OAuth, webhooks, or database — diff must be pasted or loaded from disk
- Schema validation catches structural errors in LLM output; it cannot catch semantic hallucinations (a line number that exists in the diff but is wrong)

---

## Future Roadmap

1. **GitHub integration** — PR webhook triggers MergeProof automatically; findings posted as review comments
2. **Custom reviewer personas** — teams define their own review focus (e.g. HIPAA compliance, GDPR, internal coding standards)
3. **Historical risk tracking** — database of findings per repository, trend graphs per team
4. **MCP tool registration** — expose `run_review`, `generate_patch`, and `compare_risk` as MCP tools so Bob and other agents can call MergeProof directly
5. **Diff-level evidence pinning** — highlight exact characters in the diff viewer that correspond to each finding
6. **Multi-language support** — extend reviewer prompts to TypeScript, Java, Go beyond Python
