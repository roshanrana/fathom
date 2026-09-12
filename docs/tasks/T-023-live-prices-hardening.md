---
id: T-023
title: Live prices/facts hardening — parse failures fall back, bounds, finiteness
milestone: M4
risk: medium
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-019]
rtm: [FR-022, FR-023]
status: todo
---
# T-023 — Live prices/facts hardening

## Goal
Close T-019 security findings F1, F2 (HIGH), F3, F4 (MEDIUM); F5 (LOW) as a cheap bound.

## Spec references
`05-m4-live-data.md` §4 (`daily_bars` fallback rule: "Yahoo failure" includes any body that
cannot be parsed into ≥ 1 valid bar; "Stooq failure" includes any CSV that cannot be parsed);
`T-019.security.md` F1–F5. Rules added (frozen): (1) all Yahoo/Stooq parsing runs inside a
guard that converts `TypeError`/`ValueError`/`KeyError`/`IndexError`/`json.JSONDecodeError`
into a source failure (fallback, then `SOURCE_HTTP` reason "malformed response" when both
fail); rows with null/non-numeric/non-finite close, or non-positive prices, are dropped; if no
rows remain the source failed; (2) CSV parsing reads at most 10 000 data rows; (3) `ticker`
must match `^[A-Z0-9.\-]{1,10}$` and `cik` `^\d{10}$` before URL interpolation, else
`UNKNOWN_TICKER` / `SOURCE_HTTP` reason "invalid identifier"; (4) every fact value is checked
with `math.isfinite` and every derived ratio is `None` unless finite; (5) sanity bounds: shares
in (0, 1e12], equity magnitude ≤ 1e13, |EPS| ≤ 1e4, DPS in [0, 1e3] — out-of-range facts are
treated as missing.

## Scope (files this task may touch)
- fathom/live/prices.py, fathom/live/facts.py
- tests/test_live_prices.py, tests/test_live_facts.py

## Acceptance criteria
- AC1: Yahoo bodies with `timestamp: null`, string OHLCV values, mismatched array lengths, and `{"chart": {"result": null}}` each cause the Stooq fallback (assert the Stooq URL was requested) and, when Stooq also fails, `SOURCE_HTTP` reason "malformed response" with no body.
- AC2: A Stooq CSV with 20 000 rows yields at most 10 000 bars; a CSV with a non-numeric cell in one row drops that row; an all-garbage CSV is a source failure.
- AC3: `daily_bars("bad ticker!")` raises `UNKNOWN_TICKER` before any request; `snapshot(sec, "12", …)` raises `SOURCE_HTTP` reason "invalid identifier" before any request.
- AC4: Concept JSON containing `NaN`/`Infinity` literals (Python's json accepts them) or values outside the bounds → the affected field is `None` and no ratio is non-finite; `json.dumps` of the snapshot succeeds with `allow_nan=False`.
- AC5: Existing T-019 tests pass; full gate green; mypy strict; tests named `test_fr022_*`, `test_fr023_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_live_prices.py tests/test_live_facts.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] no raw exception escapes from parsing (fuzz)
- [ ] bounds and finiteness enforced
- [ ] no body/URL in errors

## Threat-model boundary touched
B6 — fresh Security Reviewer at T2 confirms closure of T-019 F1–F5.

## Handoff (Implementer fills, ≤10 lines)
