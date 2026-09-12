---
id: T-018
title: Live foundation — settings, errors, HTTP cache/throttle, SEC EDGAR client
milestone: M4
risk: medium
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-017]
rtm: [FR-021, FR-025, NFR-013]
status: todo
---
# T-018 — Live foundation: settings, errors, HTTP cache/throttle, SEC EDGAR client

## Goal
`fathom.live.sec.SecClient` resolves a ticker to a CIK, lists the qualifying 10-K/10-Q filings,
fetches primary documents through a throttled, cached HTTP layer and converts them to parser-ready
text — all tested offline with recorded fixtures.

## Spec references
`05-m4-live-data.md` §3 (modules, settings, errors), §4 (SecCompany, SecFiling, `html_to_text`,
`filings(cik)` selection, throttle and cache rules — frozen), §6 (fixtures). Settings additions:
`data_source`, `sec_contact`, `live_cache_dir`, `live_ttl_hours`, `price_source` with the env names
given. Errors: `SOURCE_CONFIG`, `SOURCE_HTTP`, `SOURCE_EMPTY`. SEC endpoints:
`https://www.sec.gov/files/company_tickers.json`, `https://data.sec.gov/submissions/CIK<10>.json`,
`https://www.sec.gov/Archives/edgar/data/<cik int>/<accession no dashes>/<primary_document>`,
`https://data.sec.gov/api/xbrl/companyconcept/CIK<10>/<taxonomy>/<concept>.json` (the client
exposes `company_concept(cik, taxonomy, concept) -> dict` for T-019). User-Agent
`Fathom/<__version__> (<contact>)`; `Accept-Encoding: gzip`.

## Scope (files this task may touch)
- fathom/config.py (new fields only), fathom/errors.py (three new codes)
- fathom/live/__init__.py (empty except `__all__` for now), fathom/live/http.py, fathom/live/sec.py
- tests/fixtures/live/** (recorded: trimmed company_tickers.json with AAPL, MSFT, JPM, MCD, BRK-B; AAPL submissions JSON trimmed to 12 recent entries incl. a 10-K/A to prove exclusion; one real AAPL 10-Q primary document trimmed ≤ 300 KB; one real 10-K primary document trimmed ≤ 400 KB — fetch them once with a scratch script using the real endpoints and your contact e-mail, then commit the trimmed files)
- tests/test_live_http.py, tests/test_live_sec.py, tests/test_config.py (new fields)

## Acceptance criteria
- AC1: `Settings.from_env({})` has `data_source == "fixture"`, `sec_contact is None`, `live_cache_dir == Path(".cache/live")`, `live_ttl_hours == 6.0`, `price_source == "yahoo"`; `FATHOM_DATA_SOURCE=live` without `FATHOM_SEC_CONTACT` makes `SecClient.from_settings` raise `SOURCE_CONFIG` naming `FATHOM_SEC_CONTACT`; invalid values raise `PROVIDER_CONFIG`-style config errors.
- AC2: `LiveHttp.get(url, ttl_hours, source)` writes `<cache>/_http/<sha256>` + `.meta`, serves from cache within TTL without calling the transport (assert via MockTransport call count), refetches after TTL or with `force=True`, enforces ≥ 0.12 s spacing between two sec.gov calls (measure with a monkeypatched clock, not sleep), maps non-2xx to `SOURCE_HTTP` with `{"source","status","reason"}` and no body, maps `httpx.HTTPError` to `SOURCE_HTTP` status 0, and rejects bodies > 25 MB with reason "too large".
- AC3: `SecClient.lookup("aapl")` → `SecCompany(ticker="AAPL", cik="0000320193", name="Apple Inc.", exchange="Nasdaq", ...)` from the fixtures; unknown ticker → `UNKNOWN_TICKER`; `lookup("BRK.B")` and `lookup("BRK-B")` both resolve to the same company.
- AC4: `filings("0000320193")` returns newest first, only forms exactly 10-K/10-Q (the 10-K/A excluded), within 730 days of the newest filing date in the fixture, latest 10-K plus ≤ 4 10-Qs, ≤ 5 total, each with the correct `url`.
- AC5: `html_to_text` on the 10-Q fixture yields text where `filings.parse_sections(text, "10-Q")` finds `10-Q:I.2`, `10-Q:I.3`, `10-Q:I.4`, `10-Q:II.1`, `10-Q:II.1A`, and on the 10-K fixture finds `10-K:1A` and `10-K:7` with bodies ≥ 2 000 chars; `period_end` parses on both; no `<` characters remain; entities like `&amp;` are unescaped.
- AC6: `document_text(filing)` caches forever (second call: zero transport calls); the User-Agent header on every SEC request equals `Fathom/<version> (<contact>)`.
- AC7: mypy strict clean; gate green; no network in tests (a fixture asserts the transport is a MockTransport); tests named `test_fr021_*`, `test_fr025_*`, `test_nfr013_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_live_http.py tests/test_live_sec.py tests/test_config.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected; fixtures ≤ sizes stated; total added fixture bytes ≤ 1 MB
- [ ] no network in the gate (grep for real hosts in tests outside test_live_network)
- [ ] SOURCE_HTTP never carries a body; contact never logged
- [ ] html_to_text is stdlib-only
- [ ] tests named with RTM IDs; no new dependencies

## Threat-model boundary touched
B6 (new; `05-m4-live-data.md` §2) — Security Reviewer at T2.

## Handoff (Implementer fills, ≤10 lines)
