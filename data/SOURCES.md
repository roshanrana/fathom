# Data sources

Fixtures rebuilt by `scripts/fetch_data.py` on 2026-09-12. Universe: AAPL, AMZN, BAC, CAT, CVX, GOOGL, GS, JNJ, JPM, KO, MCD, META, MSFT, NVDA, PFE, PG, TSLA, UNH, WMT, XOM.

| Fixture | Hugging Face dataset | Licence | Rows kept | Description |
|---|---|---|---|---|
| `data/filings.parquet` | `musk1209/finsight-sec-filings` | MIT | 97 | Cleaned plain-text 10-K and 10-Q filings for 20 large caps (SEC EDGAR) |
| `data/bars.parquet` | `AlphaDojo/dojo_stock_kline` | Apache-2.0 | 8480 | Daily OHLCV bars, US/CN/HK equities |
| `data/quotes.parquet` | `AlphaDojo/dojo_quote` | Apache-2.0 | 20 | Latest-session quote snapshots: price, change, volume, market cap, valuation ratios |
| `data/companies.parquet` | `AlphaDojo/dojo_stock_info` | Apache-2.0 | 20 | Company master: names, exchange, sector, industry, website |

## Coverage

- Filings: 97 (20 10-K, 77 10-Q), filed 2025-04-23 to 2026-05-29.
- Bars: 8480 daily rows, 2025-01-02 to 2026-09-11, 20 symbols.
- Quotes: latest snapshot per symbol, quote_time max 2026-09-11T16:00:01+00:00.

## Anchors (hand-checkable values used by tests)

- AAPL: as_of=2026-09-11 last_close=332.27 prev_close=326.57 change_pct=1.75 open=327.45 high=336.22 low=326.30 volume=50163361 week52_high=344.27 week52_low=228.18 bars=424
- AAPL snapshot: quote_time=2026-09-11T16:00:01+00:00 last_price=332.27 market_cap=4849208188600 pe=38.10 pb=45.10 dividend_yield=0.32
- JPM: as_of=2026-09-11 last_close=356.23 prev_close=353.56 change_pct=0.76 open=358.32 high=360.05 low=354.79 volume=5322855 week52_high=366.50 week52_low=276.43 bars=424
- JPM snapshot: quote_time=2026-09-11T16:00:01+00:00 last_price=356.28 market_cap=947058577555 pe=15.26 pb=2.68 dividend_yield=1.68

Provenance note: dataset text and rows are public disclosures / market data redistributed under the licences above; they are treated as untrusted data by the application.
