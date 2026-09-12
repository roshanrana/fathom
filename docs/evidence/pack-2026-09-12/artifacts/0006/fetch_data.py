"""Rebuild the demo fixtures under data/ from four Hugging Face datasets (FR-016, D-002).

Usage: uv run --with pandas --with pyarrow python scripts/fetch_data.py [--cache DIR]

Downloads (with retries) the parquet files listed in SOURCES, filters to the 20-ticker universe,
dedupes the company master, writes data/{filings,bars,quotes,companies}.parquet and
data/SOURCES.md (dataset ids, licences, row counts, retrieval date, spot anchors for tests).
Run by the owner only; CI and the gate never call this script. Stdlib + pandas + pyarrow.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

UNIVERSE = (
    "AAPL", "AMZN", "BAC", "CAT", "CVX", "GOOGL", "GS", "JNJ", "JPM", "KO",
    "MCD", "META", "MSFT", "NVDA", "PFE", "PG", "TSLA", "UNH", "WMT", "XOM",
)

HF = "https://huggingface.co/datasets"
SOURCES = {
    "filings": {
        "id": "musk1209/finsight-sec-filings",
        "license": "MIT",
        "url": f"{HF}/musk1209/finsight-sec-filings/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet",
        "what": "Cleaned plain-text 10-K and 10-Q filings for 20 large caps (SEC EDGAR)",
    },
    "bars": {
        "id": "AlphaDojo/dojo_stock_kline",
        "license": "Apache-2.0",
        "url": f"{HF}/AlphaDojo/dojo_stock_kline/resolve/main/data.parquet",
        "what": "Daily OHLCV bars, US/CN/HK equities",
    },
    "quotes": {
        "id": "AlphaDojo/dojo_quote",
        "license": "Apache-2.0",
        "url": f"{HF}/AlphaDojo/dojo_quote/resolve/main/data.parquet",
        "what": "Latest-session quote snapshots: price, change, volume, market cap, valuation ratios",
    },
    "companies": {
        "id": "AlphaDojo/dojo_stock_info",
        "license": "Apache-2.0",
        "url": f"{HF}/AlphaDojo/dojo_stock_info/resolve/main/data.parquet",
        "what": "Company master: names, exchange, sector, industry, website",
    },
}


def download(url: str, dest: Path, attempts: int = 6) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached {dest.name} ({dest.stat().st_size:,} bytes)")
        return
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, dest.open("wb") as out:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            print(f"  downloaded {dest.name} ({dest.stat().st_size:,} bytes)")
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            print(f"  attempt {attempt} failed: {exc}")
            dest.unlink(missing_ok=True)
            time.sleep(3 * attempt)
    raise SystemExit(f"could not download {url}")


def build_filings(raw: Path) -> pd.DataFrame:
    df = pd.read_parquet(raw)
    df = df[df.ticker.isin(UNIVERSE)].copy()
    df["cik"] = df["cik"].astype(str).str.zfill(10)
    df["filing_date"] = pd.to_datetime(df["filing_date"]).dt.date
    df = df[["ticker", "cik", "company_name", "form", "filing_date", "accession", "text", "n_chars"]]
    return df.sort_values(["ticker", "filing_date", "accession"]).reset_index(drop=True)


def build_bars(raw: Path) -> pd.DataFrame:
    import pyarrow.parquet as pq

    tbl = pq.read_table(raw, filters=[("symbol", "in", list(UNIVERSE))],
                        columns=["symbol", "bar_time", "open", "high", "low", "close", "vol"])
    df = tbl.to_pandas()
    df = df.rename(columns={"bar_time": "date", "vol": "volume"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.drop_duplicates(["symbol", "date"], keep="last")
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def build_quotes(raw: Path) -> pd.DataFrame:
    import pyarrow.parquet as pq

    cols = ["symbol", "quote_time", "last_price", "pre_close", "change_percent", "volume",
            "market_cap", "pe", "pb", "dividend_yield"]
    tbl = pq.read_table(raw, filters=[("symbol", "in", list(UNIVERSE))], columns=cols)
    df = tbl.to_pandas()
    df["quote_time"] = pd.to_datetime(df["quote_time"], utc=True)
    df = df.sort_values(["symbol", "quote_time"]).groupby("symbol", as_index=False).tail(1)
    df["volume"] = df["volume"].astype("float64")
    return df.sort_values("symbol").reset_index(drop=True)


def build_companies(raw: Path) -> pd.DataFrame:
    df = pd.read_parquet(raw)
    df = df[(df.market == "us") & df.ticker.isin(UNIVERSE)].copy()
    df = df.sort_values(["ticker", "symbol"], na_position="first").drop_duplicates("ticker", keep="first")
    df = df[["ticker", "long_name", "full_exchange_name", "sector", "industry", "website"]]
    return df.sort_values("ticker").reset_index(drop=True)


def anchors(bars: pd.DataFrame, quotes: pd.DataFrame) -> list[str]:
    lines = []
    for sym in ("AAPL", "JPM"):
        b = bars[bars.symbol == sym].sort_values("date")
        last, prev = b.iloc[-1], b.iloc[-2]
        as_of = last["date"]
        cutoff = as_of - dt.timedelta(days=365)
        w = b[b.date > cutoff]
        chg = round((last["close"] / prev["close"] - 1) * 100, 2)
        q = quotes[quotes.symbol == sym].iloc[0]
        lines += [
            f"- {sym}: as_of={as_of} last_close={last['close']:.2f} prev_close={prev['close']:.2f} "
            f"change_pct={chg:.2f} open={last['open']:.2f} high={last['high']:.2f} low={last['low']:.2f} "
            f"volume={int(last['volume'])} week52_high={w['high'].max():.2f} week52_low={w['low'].min():.2f} "
            f"bars={len(b)}",
            f"- {sym} snapshot: quote_time={q['quote_time'].isoformat()} last_price={q['last_price']:.2f} "
            f"market_cap={q['market_cap']:.0f} pe={q['pe']:.2f} pb={q['pb']:.2f} dividend_yield={q['dividend_yield']:.2f}",
        ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / ".cache" / "hf"))
    args = ap.parse_args()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(exist_ok=True)

    raw: dict[str, Path] = {}
    for key, src in SOURCES.items():
        print(f"{key}: {src['id']}")
        raw[key] = cache / f"{key}.parquet"
        download(src["url"], raw[key])

    frames = {
        "filings": build_filings(raw["filings"]),
        "bars": build_bars(raw["bars"]),
        "quotes": build_quotes(raw["quotes"]),
        "companies": build_companies(raw["companies"]),
    }
    for name, df in frames.items():
        out = DATA / f"{name}.parquet"
        df.to_parquet(out, index=False)
        print(f"wrote {out} rows={len(df)} bytes={out.stat().st_size:,}")

    missing = sorted(set(UNIVERSE) - set(frames["companies"].ticker))
    if missing or len(frames["companies"]) != len(UNIVERSE):
        raise SystemExit(f"companies incomplete: missing={missing}")
    for name in ("bars", "quotes"):
        got = set(frames[name].symbol)
        if got != set(UNIVERSE):
            raise SystemExit(f"{name} universe mismatch: {sorted(set(UNIVERSE) ^ got)}")

    today = dt.date.today().isoformat()
    f, b = frames["filings"], frames["bars"]
    lines = [
        "# Data sources",
        "",
        f"Fixtures rebuilt by `scripts/fetch_data.py` on {today}. Universe: {', '.join(UNIVERSE)}.",
        "",
        "| Fixture | Hugging Face dataset | Licence | Rows kept | Description |",
        "|---|---|---|---|---|",
    ]
    for key, src in SOURCES.items():
        lines.append(f"| `data/{key}.parquet` | `{src['id']}` | {src['license']} | {len(frames[key])} | {src['what']} |")
    lines += [
        "",
        "## Coverage",
        "",
        f"- Filings: {len(f)} ({int((f.form == '10-K').sum())} 10-K, {int((f.form == '10-Q').sum())} 10-Q), "
        f"filed {f.filing_date.min()} to {f.filing_date.max()}.",
        f"- Bars: {len(b)} daily rows, {b.date.min()} to {b.date.max()}, {b.symbol.nunique()} symbols.",
        f"- Quotes: latest snapshot per symbol, quote_time max {frames['quotes'].quote_time.max().isoformat()}.",
        "",
        "## Anchors (hand-checkable values used by tests)",
        "",
        *anchors(b, frames["quotes"]),
        "",
        "Provenance note: dataset text and rows are public disclosures / market data redistributed "
        "under the licences above; they are treated as untrusted data by the application.",
    ]
    (DATA / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote data/SOURCES.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
