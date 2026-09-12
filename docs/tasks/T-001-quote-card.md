---
id: T-001
title: Quote card and price context
milestone: M1
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-000]
rtm: [FR-002, FR-003]
status: todo
---
# T-001 — Quote card and price context

## Goal
`fathom.quotes.quote_card(ticker, data_dir)` returns a `QuoteCard` whose every figure is
reproducible by hand from `data/bars.parquet` and `data/quotes.parquet`, with as-of stamps and
sources.

## Spec references
`03-lld.md §2.4` (verbatim):
```python
class PricePoint(BaseModel): date: date; close: float
class QuoteCard(BaseModel):
    ticker: str; as_of: date; source: str
    last_close: float; prev_close: float; change_abs: float; change_pct: float
    open: float; high: float; low: float; volume: int
    week52_high: float; week52_low: float; ytd_pct: float | None; one_year_pct: float | None; thirty_day_pct: float | None
    market_cap: float | None; pe: float | None; pb: float | None; dividend_yield: float | None
    snapshot_as_of: datetime | None; snapshot_source: str | None
    series: list[PricePoint]                      # trailing 252 bars, ascending
def quote_card(ticker: str, data_dir: Path) -> QuoteCard
```
Definitions: `as_of` = max bar date; `prev_close` = close of the preceding bar; `change_pct =
(last_close/prev_close - 1)*100` rounded 2 dp; `week52_*` over bars with date > as_of − 365 days;
`ytd_pct` vs the last close of the prior calendar year (None if absent); `one_year_pct` vs the
closest bar on or before as_of − 365 days (None if absent); `thirty_day_pct` vs the closest bar on
or before as_of − 30 days. Snapshot fields from `quotes.parquet` (None when null). Sources:
`"AlphaDojo/dojo_stock_kline via data/bars.parquet"`, `"AlphaDojo/dojo_quote via data/quotes.parquet"`.
Percent fields are rounded to 2 dp; prices to 2 dp; `volume` is an int.
Numeric anchors for tests are in `data/SOURCES.md` §Anchors (AAPL and JPM).

## Scope (files this task may touch)
- fathom/quotes.py
- tests/test_quotes.py

## Acceptance criteria
- AC1: For AAPL the card's `as_of`, `last_close`, `prev_close`, `change_pct`, `week52_high`, `week52_low` equal the anchors in `data/SOURCES.md` §Anchors; the test hard-codes those numbers.
- AC2: `series` has ≤ 252 points, ascending dates, last point's close == `last_close`.
- AC3: `ytd_pct`, `one_year_pct`, `thirty_day_pct` follow the definitions; a test recomputes each from the frame independently for JPM and matches to 2 dp.
- AC4: Snapshot fields come from `quotes.parquet` and `snapshot_as_of` is timezone-aware UTC; when a snapshot value is NaN the field is None.
- AC5: Unknown ticker raises `UNKNOWN_TICKER` (via `data.require_ticker`); the function never mutates cached frames (copy before sort).
- AC6: mypy strict clean; tests named `test_fr002_*`, `test_fr003_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_quotes.py -q`
- `uv run ruff check fathom/quotes.py tests/test_quotes.py && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] error taxonomy used
- [ ] no sensitive fields logged
- [ ] tests named with RTM IDs
- [ ] no new dependencies
- [ ] anchors in the test match `data/SOURCES.md`

## Threat-model boundary touched
none

## Handoff (Implementer fills, ≤10 lines)
