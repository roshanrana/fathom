---
id: T-020
title: Live materialization, data_dir_for, surface wiring, fetch command
milestone: M4
risk: medium
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-018, T-019]
rtm: [FR-020, FR-024, NFR-012]
status: todo
---
# T-020 — Live materialization, data_dir_for, surface wiring, fetch command

## Goal
In live mode every surface serves any SEC-listed ticker: `materialize` writes the four
fixture-shaped tables plus a manifest into `.cache/live/<TICKER>/`, `data_dir_for` routes callers
there, `require_ticker` accepts live tickers, and `fathom fetch` pre-warms and reports coverage.

## Spec references
`05-m4-live-data.md` §4 (`LiveManifest`, `data_dir_for`, `materialize`, table schemas —
frozen), §5 (CLI `--source`, `fetch` output, `require_ticker` live rule, page radio + ticker box +
status strip, API `?source=`, MCP `source` argument). Call sites to route through `data_dir_for`:
`fathom/briefing.py` (`brief` → `build_context(ticker, data_dir_for(...))`), `fathom/ask.py`,
`fathom/cli.py`, `fathom/api.py`, `fathom/mcp_server.py`, `app/main.py`. `bench.py` stays on
fixtures (do not touch). `companies.parquet` row: long_name = SEC `name`, full_exchange_name =
first exchange or "", sector = industry = `sicDescription` or "", website = "".
`quotes.parquet` row: symbol, quote_time = last bar date at 21:00 UTC, last_price = last close,
pre_close, change_percent, volume, + snapshot fields. TTL: if `manifest.json` exists and
`fetched_at` is within `live_ttl_hours` and `force` is false, return it without any HTTP call.

## Scope (files this task may touch)
- fathom/live/__init__.py, fathom/live/build.py, fathom/data.py (`require_ticker(ticker, settings=None)`), fathom/config.py (only if a helper is needed), fathom/briefing.py, fathom/ask.py, fathom/cli.py, fathom/api.py, fathom/mcp_server.py, app/main.py, app/components/rendering.py
- tests/test_live_build.py, tests/test_data.py, tests/test_cli.py, tests/test_api.py, tests/test_app.py, tests/test_mcp.py, tests/test_briefing.py, tests/test_ask.py (source-routing tests only)

## Acceptance criteria
- AC1: With MockTransport-backed clients and `Settings(data_source="live", sec_contact="test@example.com", live_cache_dir=tmp)`, `materialize("AAPL", settings)` writes the four parquet files with the exact fixture schemas and a `manifest.json` that validates as `LiveManifest` with `sections_coverage` listing canonical ids per accession; a second call performs zero HTTP calls (TTL); `force=True` refetches.
- AC2: `data_dir_for("AAPL", fixture_settings) == settings.data_dir`; in live mode it returns the ticker cache dir; `require_ticker("brk.b", live_settings) == "BRK.B"`; `require_ticker("$$", live_settings)` → `UNKNOWN_TICKER`; fixture-mode behaviour unchanged (existing tests pass).
- AC3: End to end offline on the materialized cache: `quote_card("AAPL", live_dir)`, `filings_for`, `sections_for`, `brief` (offline provider) and `ask` all work and produce contract-valid outputs with `QuoteCard.source` naming the price source and `snapshot_source` the XBRL derivation; `Briefing.filings_used` come from the live cache.
- AC4: CLI: `fathom fetch AAPL --source live` prints filings (form, date, accession), per-accession section coverage, bars range/source, and which snapshot fields are present; `fathom quote AAPL --source live` uses the cache; `--source fixture` on a live-configured settings forces fixtures; missing contact → `error SOURCE_CONFIG: …FATHOM_SEC_CONTACT…` exit 2.
- AC5: API: `GET /api/quote/AAPL?source=live` routes to the cache (MockTransport injected via `create_app(settings, http=...)` or a monkeypatched client factory); `meta.source` present on every response; `?source=bogus` → 422.
- AC6: Page (AppTest, live settings with a monkeypatched materialize that returns a prepared cache dir): sidebar radio shows both sources; in live mode a text input + "Fetch" button appear; the status strip shows "source: live" and the fetched-at time; a `SOURCE_HTTP` from materialize renders as `st.error`. MCP: `get_quote("AAPL", source="live")` works via the same monkeypatch.
- AC7: Full gate green with no network; mypy strict; tests named `test_fr020_*`, `test_fr024_*`, `test_nfr012_*` (NFR-012 test records the elapsed time of a mocked cold materialize as informational).

## Validation commands (targeted)
- `uv run pytest tests/test_live_build.py tests/test_data.py tests/test_cli.py tests/test_api.py tests/test_app.py tests/test_mcp.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected; bench untouched; fixture mode byte-identical behaviour (existing tests unchanged except additions)
- [ ] no network in the gate
- [ ] SOURCE_* errors surface cleanly on every surface
- [ ] tests named with RTM IDs; no new dependencies

## Threat-model boundary touched
B1 (free-text ticker input validated by regex + SEC map), B6 — Security Reviewer at T2.

## Handoff (Implementer fills, ≤10 lines)
Added `fathom/live/build.py` (`LiveManifest`, `materialize`) and filled `fathom/live/__init__.py`
(`data_dir_for`, `is_live`); wired `data.require_ticker(ticker, settings=None)`, `briefing.brief`,
`ask.ask`, `cli.py` (`--source`, new `fetch` command), `api.py` (`?source=`, `meta.source`,
`create_app(..., http=...)`), `mcp_server.py` (`source` arg), `app/main.py` + `rendering.py`
(radio/ticker-box/Fetch/status strip). Scope exception used: `fathom/quotes.py` reads
`manifest.json` (bars_source/snapshot_source) for `QuoteCard.source`/`snapshot_source`, falling
back to fixture constants — no schema change to `quotes.parquet`.
`prices.py`/`facts.py` changed underfoot mid-task (not by me, not http.py/sec.py); adapted:
empty-bars now raises `SOURCE_HTTP` not `SOURCE_EMPTY` (see test_live_build.py note) — my
`bars.empty` guard in `materialize` is now defensive dead code, left in place, harmless.
Gate green (385 tests, 95.67% cov, mypy x2, ruff, secrets, bench, card drift), no network.
