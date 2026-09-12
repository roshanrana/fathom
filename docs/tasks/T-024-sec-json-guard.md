---
id: T-024
title: SEC client — guarded JSON decoding everywhere
milestone: M4
risk: medium
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 20000, tool_calls: 20, wall_clock_min: 20}
depends_on: [T-023]
rtm: [FR-021, FR-025]
status: todo
---
# T-024 — SEC client: guarded JSON decoding everywhere

## Goal
Close the final-round HIGH from `T-023.security.md`: `SecClient.ticker_map`, `_submissions` and
the paginated-filings decode call `json.loads` unguarded, so a corrupted SEC body raises
`UnicodeDecodeError`/`JSONDecodeError` out of `lookup()`/`filings()` and `materialize`.

## Spec references
`05-m4-live-data.md` §4 (SOURCE_HTTP "malformed response" never carries a body) and the
T-023 attempt-3 amendment (whole-body guard for payload parsing). Rule (frozen): every JSON
body from SEC is decoded through one helper `_decode_json(body: bytes, source: str) -> dict` that
decodes UTF-8 and JSON inside `except Exception` and requires a dict, raising `SOURCE_HTTP`
`{"source", "status": 200, "reason": "malformed response"}` otherwise; `company_concept` uses the
same helper. Callers (`lookup`, `filings`, `materialize`) let that `FathomError` propagate; the
surfaces already map `SOURCE_HTTP` to 502 / exit 2 / `st.error`.

## Scope (files this task may touch)
- fathom/live/sec.py, tests/test_live_sec.py
- README.md, docs/SHOWCASE.md (gate figure strings only, after the full gate run)

## Acceptance criteria
- AC1: With MockTransport bodies `b"\xff\xfe"`, `b"not json"`, `b"[]"`, `b"null"`, `b'"s"'` for the ticker map, the submissions document and an older-pages document, `lookup("AAPL")` / `filings(cik)` raise `SOURCE_HTTP` reason "malformed response" with no body in message/details; valid fixtures unchanged.
- AC2: A 1 000-iteration random-byte mutation fuzz of the recorded submissions and ticker-map fixtures through `lookup()` and `filings()` raises only `FathomError` (add it as a fast test with a fixed seed and 200 iterations).
- AC3: Public signatures unchanged; full gate green; mypy strict; tests named `test_fr021_*`; the gate figures quoted in README.md and docs/SHOWCASE.md equal the final gate output.

## Validation commands (targeted)
- `uv run pytest tests/test_live_sec.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] no unguarded `json.loads` remains in fathom/live (grep)
- [ ] no body in errors
- [ ] docs figures equal the gate

## Threat-model boundary touched
B6 — combined final Verifier + Security review.

## Handoff (Implementer fills, ≤10 lines)
Added `_decode_json(body, source)` in `sec.py`; routed `ticker_map`, `_submissions`, the
paginated older-filings decode, and `company_concept` through it (removed dead
`_malformed_concept_error`). Added AC1 tests (5 malformed bodies x ticker-map/submissions/
older-page) and a seeded 200-iter mutation fuzz (seed 20240024) in `test_live_sec.py`.
`grep json.loads fathom/live` shows only the one guarded call. Targeted: 42 passed. Full gate:
456 passed (2 network tests skipped offline), 95.62% coverage, all clean. Updated
`docs/SHOWCASE.md` figure 440->456; README.md has no gate-figure string.
