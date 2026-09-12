# M4 amendment — live, free data sources

Status: approved at G1–G4 re-entry for M4 (D-013). Extends `01-requirements.md`, `02-hld.md`,
`02-threat-model.md` and `03-lld.md`; contracts in §4 are frozen.

## 1. Requirements

| ID | Requirement | Acceptance criterion | Priority |
|---|---|---|---|
| FR-020 | Live data source switch | `FATHOM_DATA_SOURCE` ∈ {fixture (default), live}. In live mode every surface (page, CLI, API, MCP) serves any US-listed ticker known to SEC EDGAR; in fixture mode behaviour is unchanged. CLI commands accept `--source live|fixture`; the page has a sidebar radio and a free-text ticker box in live mode; the API accepts `?source=live`. | Must |
| FR-021 | Live filings from SEC EDGAR | For a ticker, the latest 10-K and up to four latest 10-Qs (filed within the last 24 months) are fetched from EDGAR's submissions API and primary documents, converted HTML → text, and exposed through the existing `filings_for` / `sections_for` with the same `Filing` / `Section` contracts. Parser coverage on the live text: 10-K yields `10-K:1A` and `10-K:7`; 10-Q yields `10-Q:I.2` (checked by `fathom fetch`). | Must |
| FR-022 | Live prices | Daily bars for at least the trailing 365 days from Yahoo Finance's chart endpoint, with Stooq CSV as an automatic fallback; the `QuoteCard` is computed by the unchanged `quotes.quote_card` from those bars. | Must |
| FR-023 | Live valuation snapshot from XBRL | Market cap, P/E, P/B and dividend yield derived from SEC XBRL company-concept facts (shares outstanding, diluted EPS TTM, stockholders' equity, dividends per share TTM) and the latest close; `snapshot_source` names the derivation; any missing fact yields `None`, never an error. | Must |
| FR-024 | Cache, freshness and pre-warm | Live fetches are cached under `FATHOM_LIVE_CACHE_DIR` (default `.cache/live/<TICKER>/`) as the four fixture-shaped parquet files plus `manifest.json` (fetched_at, sources, filing accessions); reads within `FATHOM_LIVE_TTL_HOURS` (default 6) hit the cache; `fathom fetch TICKER [--force]` pre-warms and prints coverage; the page/status strip shows the data source and fetched-at time. | Must |
| FR-025 | SEC fair-access compliance | Every SEC request carries `User-Agent: Fathom/<version> (<FATHOM_SEC_CONTACT>)`; live mode refuses to start without `FATHOM_SEC_CONTACT`; requests to `sec.gov`/`data.sec.gov` are spaced ≥ 0.12 s apart per process; responses are cached so a briefing never re-downloads a document. | Must |
| NFR-012 | Live cold-start latency | ≤ 30 s for a ticker with no cache on a normal connection (5 documents + 4 facts + 1 chart); warm reads ≤ 1 s. Measured by `fathom fetch --force` and reported, not gated. | Should |
| NFR-013 | Offline gate | The gate, bench and CI never touch the network: live code is tested with recorded fixtures under `tests/fixtures/live/`; network smoke tests run only when `FATHOM_NETWORK_TESTS=1`. | Must |

Out of scope: intraday quotes, options, non-US filers, keyed providers (Finnhub, Alpha Vantage) —
an adapter slot is left in `prices.py` for a keyed source later.

## 2. Design (HLD delta)

```
                 ┌── fixture mode ──► data/*.parquet ─────────────────────────┐
ticker ──► data_dir_for(ticker, settings) ─┤                                       ├─► load_frame → quotes / filings / retrieval / briefing (unchanged)
                 └── live mode ──► live.build.materialize(ticker) ──► .cache/live/<T>/*.parquet ─┘
                                        │
                                        ├── live.sec.SecClient: company_tickers.json → CIK; submissions → filings; primary doc → html_to_text
                                        ├── live.prices.PriceClient: Yahoo chart (2y, 1d) → Stooq CSV fallback
                                        └── live.facts.snapshot(): XBRL companyconcept → market cap, P/E, P/B, yield
```

Live mode is a data pipeline that produces the fixture schema on demand. Nothing downstream
changes; `data_dir` becomes per-ticker in live mode. Rationale: the parser, BM25 index,
briefing, verifier and guard are all contract-tested against the fixture schema already; the
cheapest correct extension is to feed them the same shapes.

Trust boundary **B6** (new): fathom ↔ SEC EDGAR / Yahoo / Stooq over HTTPS. Threats: T —
tampered or malformed HTML/JSON (mitigated: stdlib parsing only, no script execution, contract
validation, size caps 25 MB per document); D — rate limiting or outages (mitigated: spacing,
cache, fallback price source, clean `SOURCE_HTTP` errors, fixture mode always available); I —
contact email in User-Agent leaves the machine (by SEC policy; configured per operator, never in
the repo); R — provenance (manifest records URLs, accession numbers, fetched_at). Data class:
public. Prompt-injection surface unchanged (filing text was already untrusted).

## 3. Module design

```
fathom/live/__init__.py      data_dir_for(ticker, settings) -> Path ; is_live(settings)
fathom/live/http.py          LiveHttp: shared httpx.Client factory, per-host min-interval throttle, on-disk cache (path = sha256(url)), size cap, SOURCE_HTTP mapping
fathom/live/sec.py           SecClient(http, contact): ticker_map(), lookup(ticker) -> SecCompany, filings(cik) -> list[SecFiling], document_text(filing) -> str ; html_to_text(html) -> str
fathom/live/prices.py        PriceClient(http): daily_bars(ticker) -> pd.DataFrame ; _yahoo(), _stooq()
fathom/live/facts.py         snapshot(sec, cik, last_close, quote_time) -> dict  (market_cap, pe, pb, dividend_yield, snapshot_source)
fathom/live/build.py         materialize(ticker, settings, force=False) -> LiveManifest ; writes the four parquet files + manifest.json
```

Settings additions (`config.py`): `data_source: Literal["fixture","live"] = "fixture"`
(`FATHOM_DATA_SOURCE`), `sec_contact: str | None` (`FATHOM_SEC_CONTACT`), `live_cache_dir: Path =
Path(".cache/live")` (`FATHOM_LIVE_CACHE_DIR`), `live_ttl_hours: float = 6` (`FATHOM_LIVE_TTL_HOURS`),
`price_source: Literal["yahoo","stooq"] = "yahoo"` (`FATHOM_PRICE_SOURCE`, the other is the fallback).
Errors (`errors.py`): `Code.SOURCE_CONFIG` (missing contact; message names `FATHOM_SEC_CONTACT`),
`Code.SOURCE_HTTP` (details `{"source": "sec|yahoo|stooq", "status": int, "reason": str}` — never a
body), `Code.SOURCE_EMPTY` (ticker known but no 10-K/10-Q in 24 months, or no bars).

## 4. Contracts (FROZEN)

```python
class SecCompany(BaseModel): ticker: str; cik: str; name: str; exchange: str | None; sic_description: str | None; fiscal_year_end: str | None
class SecFiling(BaseModel): cik: str; accession: str; form: Literal["10-K","10-Q"]; filing_date: date; report_date: date | None; primary_document: str; url: str
class LiveManifest(BaseModel):
    ticker: str; cik: str; fetched_at: datetime; data_dir: str
    filings: list[SecFiling]; bars_source: str; bars_from: date; bars_to: date; snapshot_source: str
    sections_coverage: dict[str, list[str]]     # accession -> canonical ids found
def data_dir_for(ticker: str, settings: Settings) -> Path     # fixture: settings.data_dir ; live: materialize(...).data_dir (cache within TTL)
def materialize(ticker: str, settings: Settings, force: bool = False) -> LiveManifest
def html_to_text(html: str) -> str
```
Materialized tables use exactly the fixture schemas (LLD §2.3): `filings.parquet` (ticker, cik
10-digit, company_name, form, filing_date, accession, text, n_chars), `bars.parquet` (symbol, date,
open, high, low, close, volume), `quotes.parquet` (one row: symbol, quote_time, last_price,
pre_close, change_percent, volume, market_cap, pe, pb, dividend_yield), `companies.parquet`
(ticker, long_name, full_exchange_name, sector, industry, website) — sector = SIC description,
industry = SIC description, website = "" (SEC does not publish it).

`html_to_text` (frozen): drop `<script>`/`<style>`/`<head>` and XBRL `ix:header`; `<br>` and the
close of `p, div, tr, li, h1–h6, table, section` become "\n"; every other tag becomes " ";
HTML entities unescaped; `\xa0` → space; runs of spaces/tabs collapsed; blank-line runs collapsed
to one "\n". Stdlib `html` + `re` only.

`filings(cik)` selection: from `submissions.recent` (plus older pages only if fewer than 5
qualifying filings are found in `recent`), forms exactly "10-K" or "10-Q" (amendments excluded),
filed within 730 days, newest first, the latest 10-K plus up to four 10-Qs, at most five in total.

`daily_bars`: Yahoo `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=2y&interval=1d`
(Yahoo symbol = ticker with "." → "-"), rows with null close dropped; fallback Stooq
`https://stooq.com/q/d/l/?s=<sym>.us&i=d` (CSV Date,Open,High,Low,Close,Volume); a 503 or HTML
body from Stooq counts as failure. Source string recorded in the manifest and in `QuoteCard.source`
as "<yahoo|stooq> via .cache/live/<T>/bars.parquet".

`snapshot`: shares = latest `dei:EntityCommonStockSharesOutstanding`; EPS TTM = sum of the four
most recent `us-gaap:EarningsPerShareDiluted` entries whose `frame` matches `^CY\d{4}Q\d$`; equity
= latest `us-gaap:StockholdersEquity` instant (`frame` `^CY\d{4}Q\dI$`); DPS TTM = sum of the four
most recent `us-gaap:CommonStockDividendsPerShareDeclared` quarterly frames (0 if the concept is
absent); market_cap = last_close × shares; pe = last_close / eps_ttm if eps_ttm > 0 else None;
pb = market_cap / equity if both; dividend_yield = dps_ttm / last_close × 100. `snapshot_source` =
"SEC XBRL companyconcept (shares, EPS TTM, equity, DPS TTM) × <price source> close".

Throttle and cache (`http.py`): per-host minimum interval 0.12 s (sec.gov, data.sec.gov) and 0 s
otherwise; cache directory `<live_cache_dir>/_http/<sha256(url)>` with a `.meta` JSON (url,
fetched_at, status); TTL per call (ticker map 24 h, submissions and facts 6 h, documents ∞,
bars 6 h); `force=True` bypasses the cache; bodies larger than 25 MB raise `SOURCE_HTTP`
reason "too large".

## 5. Surfaces

CLI: `fathom fetch TICKER [--force] [--source live]` prints the manifest summary (filings with
forms/dates, section coverage per accession, bars range and source, snapshot fields present);
`quote`, `filings`, `brief`, `ask` gain `--source {fixture,live}` (default from settings).
`require_ticker(ticker, settings=None, data_dir=None)` (amended after T-020 attempt 1): the
ticker is upper-cased and must match `^[A-Z][A-Z0-9.\-]{0,9}$` in every mode (shape check first,
before any path is built — B1/B6 control); then, when `data_dir` is given, existence is checked
against that directory's `companies.parquet` (this makes fixture data and live caches behave the
same way: the fixture directory lists the 20-ticker universe, a live cache lists its one ticker);
when `data_dir` is None and `settings` is fixture mode or None, existence is checked against
`UNIVERSE`; when `data_dir` is None and `settings` is live, only the shape is checked and
existence is deferred to `SecClient.lookup`. Internal callers that receive a `data_dir`
(`quotes.quote_card`, `filings.filings_for`, `briefing.build_context`, `retrieval.index_for`)
pass it. `materialize` runs the shape check before constructing the cache directory path.
API status mapping gains `SOURCE_CONFIG` → 503, `SOURCE_HTTP` → 502, `SOURCE_EMPTY` → 404. Page: sidebar radio "Data source" (Fixtures — 20 tickers / Live — SEC EDGAR + Yahoo),
free-text ticker input in live mode with a "Fetch" button, status strip adds "source: live ·
fetched <time>"; a `SOURCE_*` error renders as `st.error`. API: `?source=live` on the four routes;
`meta.source` added. MCP: optional `source` argument on the four tools.

## 6. Test strategy

Recorded fixtures under `tests/fixtures/live/`: a trimmed `company_tickers.json` (5 tickers),
one `submissions` JSON (AAPL, trimmed to 12 filings), one real 10-Q primary document trimmed to
≤ 300 KB that still yields `10-Q:I.2`/`I.3`/`I.4`/`II.1`/`II.1A`, a 10-K sample ≤ 400 KB yielding
`10-K:1A`/`7`, four company-concept JSONs trimmed to the last 8 entries, a Yahoo chart JSON with
30 bars, a Stooq CSV with 30 rows and a Stooq maintenance HTML. All live tests use
`httpx.MockTransport` routing by URL. Network smoke test `tests/test_live_network.py` skips
unless `FATHOM_NETWORK_TESTS=1`. Bench stays on fixtures. Coverage target for `fathom/live` ≥ 85 %.
