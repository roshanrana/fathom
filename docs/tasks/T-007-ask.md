---
id: T-007
title: Grounded Q&A
milestone: M2
risk: medium
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-003, T-004, T-005]
rtm: [FR-009]
status: todo
---
# T-007 — Grounded Q&A

## Goal
`fathom.ask.ask(ticker, question, settings, provider=None, k=6)`: input guard → BM25 retrieval →
provider → `AnswerDraft` (one repair retry) → verify → scrub → audit → `Answer`.

## Spec references
`03-lld.md §2.10` (verbatim): `ask`: input guard first (advice → Answer with one guarded claim
and `not_found=False`, no call, audited with provider "guard"); retrieval → zero hits →
`Answer(not_found=True)`, no call, audited with provider "none"; else as `brief` with
`SYSTEM_ASK` and `AnswerDraft`. Ask context (`§6.2`): user JSON `{"task": "ask", "ticker",
"company", "question": str, "excerpts": [{"accession", "section_id", "title", "text": <chunk
text>}]}` from the top-k hits (title from `prompts.CANONICAL_SECTIONS`). Verification uses the
full section text of the cited `section_id` (via `filings.sections_for`), not only the chunk.
The guarded claim for an advice question: `Claim(text=GUARD_NOTICE, source=Source(accession="",
section_id=""), quote="", verified=False, guarded=True)`, `guard_hits=1`. `question_sha256` =
sha256 of the raw question; the question text itself is never logged or audited (bodies flag
governs only prompt/response). INFO log `ask ticker=%s provider=%s hits=%d not_found=%s
latency_ms=%d`. Model/provider fields for the no-call paths: provider "guard"/"none", model "-".

## Scope (files this task may touch)
- fathom/ask.py
- tests/test_ask.py (may import `tests/fakes.py` from T-006; if absent, define a local ScriptedProvider in the test file)

## Acceptance criteria
- AC1: `ask("AAPL", "Should I buy Apple?", settings, provider=failing_provider)` returns `guard_hits == 1`, one guarded claim, `not_found is False`, and the provider is never called; the audit record has `provider == "guard"`.
- AC2: `ask("AAPL", "zqxjv wvutsr", settings, provider=failing_provider)` returns `not_found is True`, no claims, provider never called, audit `provider == "none"`.
- AC3: Offline: `ask("AAPL", "What are the main risk factors?", Settings())` returns ≥ 1 claim, every claim `verified is True`, every `source.section_id` is a canonical id, `not_found is False`.
- AC4: With a scripted draft whose quote is a real sentence from the cited section but was not in the retrieved chunk, `verified is True` (verification is against the full section).
- AC5: Repair path as in T-006 AC2 (invalid then valid → Answer; twice invalid → `CONTRACT_INVALID`).
- AC6: A capturing log handler sees no record containing the question text; mypy strict clean; tests named `test_fr009_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_ask.py -q`
- `uv run ruff check fathom/ask.py tests/test_ask.py && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] error taxonomy used
- [ ] question text never logged or audited
- [ ] tests named with RTM IDs
- [ ] no new dependencies

## Threat-model boundary touched
B1 (advice elicitation, injection via question) — Security Reviewer at T2.

## Handoff (Implementer fills, ≤10 lines)
- Implemented: `ask()` per LLD §2.10 — guard→retrieval→provider(+1 repair)→verify-against-full-section→scrub→audit→`Answer`; no-call paths audited provider "guard"/"none", model "-"; question text never logged/audited (only its sha256).
- Files changed: `fathom/ask.py` (new), `tests/test_ask.py` (new, local `ScriptedProvider`/`FailingProvider` since `tests/fakes.py` did not exist yet).
- Tests run: `uv run pytest tests/test_ask.py -q` → 7 passed. Full gate `uv run python scripts/check.py` → all checks passed (154 tests total, 97.59% coverage, ruff/mypy/format/secrets clean).
- Deviations: none from spec. `_section_text_index` catches `FathomError` per-accession (unknown accession → verified False) rather than propagating, per §2.10's "unknown accession/section_id → verified False" rule.
- Open questions: none.
- Budget actual: in≈40k tokens, ~35 tool calls, well under 45 min wall clock.
