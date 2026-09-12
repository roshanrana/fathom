---
id: T-019
title: Live prices (Yahoo → Stooq) and XBRL valuation snapshot
milestone: M4
risk: medium
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-018]
rtm: [FR-022, FR-023]
status: todo
---
# T-019 — Live prices (Yahoo → Stooq) and XBRL valuation snapshot

## Goal
`fathom.live.prices.PriceClient.daily_bars(ticker)` returns fixture-schema bars from Yahoo with
Stooq fallback; `fathom.live.facts.snapshot(...)` derives market cap, P/E, P/B and dividend yield
from SEC XBRL company-concept facts. Offline-tested with recorded fixtures.

## Spec references
`05-m4-live-data.md` §4 `daily_bars` and `snapshot` (frozen formulas, symbol mapping, fallback
rule, source strings) and §3. Uses `fathom.live.http.LiveHttp` and `SecClient.company_concept`
from T-018 (read their signatures; do not modify them — if a signature is insufficient, record
it under "## Blocked"). Bars schema: symbol str, date `datetime.date`, open/high/low/close/volume
float64; ascending by date; ≥ 250 rows from the Yahoo 2y range in production, ≥ 1 in tests.
Yahoo JSON path: `chart.result[0].timestamp[]`, `indicators.quote[0].{open,high,low,close,volume}[]`;
rows with null close dropped; timestamps → UTC dates. Stooq CSV header `Date,Open,High,Low,Close,Volume`.

## Scope (files this task may touch)
- fathom/live/prices.py, fathom/live/facts.py
- tests/fixtures/live/** (add: Yahoo chart JSON for AAPL trimmed to 30 bars; Stooq CSV 30 rows; Stooq maintenance HTML; four company-concept JSONs for AAPL trimmed to the last 8 entries each, keeping `frame`, `end`, `val`, `fp`, `form`)
- tests/test_live_prices.py, tests/test_live_facts.py

## Acceptance criteria
- AC1: With a MockTransport serving the Yahoo fixture, `daily_bars("AAPL")` returns 30 rows with the exact schema/dtypes, ascending dates, `symbol == "AAPL"`, and `PriceClient.last_source == "yahoo"`; `daily_bars("BRK.B")` requests the Yahoo symbol `BRK-B` and the Stooq symbol `brk-b.us`.
- AC2: When Yahoo returns 500 or a body without `chart.result`, the client falls back to Stooq and returns its 30 rows with `last_source == "stooq"`; when Stooq returns 503 or an HTML body, `SOURCE_HTTP` is raised with source "stooq" and no body; `price_source="stooq"` makes Stooq primary and Yahoo the fallback.
- AC3: Bars are cached via `LiveHttp` (6 h TTL) — a second call performs zero transport calls.
- AC4: `snapshot(sec, cik, last_close=332.27, quote_time=...)` on the fixtures returns market_cap = 332.27 × latest shares, pe = 332.27 / (sum of the four most recent `CY####Q#` EPS frames) rounded 2 dp, pb = market_cap / latest `CY####Q#I` equity rounded 2 dp, dividend_yield = DPS TTM / 332.27 × 100 rounded 2 dp, and the exact `snapshot_source` string; the test hard-codes the expected numbers computed by hand from the fixture files.
- AC5: Missing concept (404) → that field `None`, others still computed; EPS TTM ≤ 0 → `pe is None`; no exception for any missing/odd fact shape (fuzz: empty `units`, missing `frame`, non-numeric `val`).
- AC6: mypy strict clean; gate green; no network in tests; tests named `test_fr022_*`, `test_fr023_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_live_prices.py tests/test_live_facts.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected; fixtures small
- [ ] formulas match §4 exactly (recompute by hand)
- [ ] fallback order honoured; failures are SOURCE_HTTP without bodies
- [ ] tests named with RTM IDs; no new dependencies

## Threat-model boundary touched
B6 — Security Reviewer at T2 (malformed JSON/CSV handling).

## Handoff (Implementer fills, ≤10 lines)
Implemented `fathom/live/prices.py` (`PriceClient.daily_bars`, Yahoo primary/Stooq fallback,
BRK.B->BRK-B/brk-b.us mapping) and `fathom/live/facts.py` (`snapshot`, XBRL TTM/latest formulas).
Fixtures recorded live via a scratch script (Yahoo 3mo trimmed to 30 bars; SEC 4 concepts for
CIK 0000320193, last 8 entries/unit); Stooq returned a JS bot-challenge page instead of the
documented 503, saved as the maintenance fixture, with a 30-row CSV hand-derived from Yahoo closes.
`snapshot_source` is the fixed string "SEC XBRL companyconcept (shares, EPS TTM, equity, DPS TTM)"
— no price-source suffix, since `snapshot()`'s frozen signature has none; `quote_time` unused.
Targeted tests (18) + full gate green: 339 passed, coverage 95.88%, mypy strict clean, no network.
Did not modify http.py/sec.py.
