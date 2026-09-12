"""Quote card and price context (LLD §2.4)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from fathom.data import load_frame, require_ticker
from fathom.errors import Code, FathomError

BARS_SOURCE = "AlphaDojo/dojo_stock_kline via data/bars.parquet"
QUOTES_SOURCE = "AlphaDojo/dojo_quote via data/quotes.parquet"


def _live_sources(data_dir: Path) -> tuple[str | None, str | None]:
    """(bars_source, snapshot_source) from `data_dir`'s `manifest.json`, if present (T-020).

    Live-materialized directories carry a manifest (written by `fathom.live.build.materialize`)
    naming the actual price/snapshot source; fixture directories have none, so callers fall
    back to the `BARS_SOURCE`/`QUOTES_SOURCE` constants.
    """
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    bars_source = manifest.get("bars_source")
    snapshot_source = manifest.get("snapshot_source")
    return (
        bars_source if isinstance(bars_source, str) else None,
        snapshot_source if isinstance(snapshot_source, str) else None,
    )


_WEEK52_WINDOW_DAYS = 365
_ONE_YEAR_WINDOW_DAYS = 365
_THIRTY_DAY_WINDOW_DAYS = 30
_SERIES_MAX_BARS = 252
_ROUND_DP = 2


class PricePoint(BaseModel):
    """One bar's date and close, for the trailing price series."""

    date: date
    close: float


class QuoteCard(BaseModel):
    """A reproducible price snapshot for one ticker (LLD §2.4)."""

    ticker: str
    as_of: date
    source: str
    last_close: float
    prev_close: float
    change_abs: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    week52_high: float
    week52_low: float
    ytd_pct: float | None
    one_year_pct: float | None
    thirty_day_pct: float | None
    market_cap: float | None
    pe: float | None
    pb: float | None
    dividend_yield: float | None
    snapshot_as_of: datetime | None
    snapshot_source: str | None
    series: list[PricePoint]


def _optional_float(value: Any) -> float | None:
    """Convert a possibly-NaN scalar to a float, or None."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _closest_on_or_before(frame: pd.DataFrame, target: date) -> pd.Series | None:
    """The row with the latest `date` <= target, or None if none qualifies."""
    eligible = frame[frame["date"] <= target]
    if eligible.empty:
        return None
    row: pd.Series = eligible.iloc[-1]
    return row


def _pct_change(current: float, base: float | None) -> float | None:
    """Percentage change of `current` vs `base`, rounded, or None if no base."""
    if base is None:
        return None
    return round((current / base - 1) * 100, _ROUND_DP)


def _bars_for(ticker: str, data_dir: Path) -> pd.DataFrame:
    """Ascending, ticker-filtered copy of the bars fixture (never mutates the cache)."""
    bars = load_frame("bars", data_dir)
    frame = bars[bars["symbol"] == ticker].copy().sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise FathomError(Code.DATA_MISSING, f"no bars for {ticker!r}", {"name": "bars"})
    return frame


def _snapshot_for(
    ticker: str, data_dir: Path
) -> tuple[float | None, float | None, float | None, float | None, datetime | None, str | None]:
    """Snapshot fields (market_cap, pe, pb, dividend_yield, as_of, source) for `ticker`."""
    quotes = load_frame("quotes", data_dir)
    rows = quotes[quotes["symbol"] == ticker]
    if rows.empty:
        return None, None, None, None, None, None
    snap = rows.iloc[-1]
    market_cap = _optional_float(snap["market_cap"])
    pe = _optional_float(snap["pe"])
    pb = _optional_float(snap["pb"])
    dividend_yield = _optional_float(snap["dividend_yield"])
    quote_time: pd.Timestamp = snap["quote_time"]
    snapshot_as_of = quote_time.to_pydatetime()
    _, live_snapshot_source = _live_sources(data_dir)
    return (
        market_cap,
        pe,
        pb,
        dividend_yield,
        snapshot_as_of,
        live_snapshot_source or QUOTES_SOURCE,
    )


def quote_card(ticker: str, data_dir: Path) -> QuoteCard:
    """Build a `QuoteCard` for `ticker`, hand-reproducible from the fixtures."""
    symbol = require_ticker(ticker, data_dir=data_dir)
    frame = _bars_for(symbol, data_dir)

    as_of: date = frame["date"].iloc[-1]
    last_row = frame.iloc[-1]
    prev_row = frame.iloc[-2]

    last_close = float(last_row["close"])
    prev_close = float(prev_row["close"])
    change_abs = round(last_close - prev_close, _ROUND_DP)
    change_pct = round((last_close / prev_close - 1) * 100, _ROUND_DP)

    week52_window = frame[frame["date"] > as_of - timedelta(days=_WEEK52_WINDOW_DAYS)]
    week52_high = round(float(week52_window["high"].max()), _ROUND_DP)
    week52_low = round(float(week52_window["low"].min()), _ROUND_DP)

    prior_year_end = date(as_of.year - 1, 12, 31)
    ytd_row = _closest_on_or_before(frame, prior_year_end)
    ytd_pct = _pct_change(last_close, float(ytd_row["close"]) if ytd_row is not None else None)

    one_year_row = _closest_on_or_before(frame, as_of - timedelta(days=_ONE_YEAR_WINDOW_DAYS))
    one_year_pct = _pct_change(
        last_close, float(one_year_row["close"]) if one_year_row is not None else None
    )

    thirty_day_row = _closest_on_or_before(frame, as_of - timedelta(days=_THIRTY_DAY_WINDOW_DAYS))
    thirty_day_pct = _pct_change(
        last_close, float(thirty_day_row["close"]) if thirty_day_row is not None else None
    )

    series = [
        PricePoint(date=row["date"], close=round(float(row["close"]), _ROUND_DP))
        for _, row in frame.tail(_SERIES_MAX_BARS).iterrows()
    ]

    market_cap, pe, pb, dividend_yield, snapshot_as_of, snapshot_source = _snapshot_for(
        symbol, data_dir
    )
    live_bars_source, _ = _live_sources(data_dir)

    return QuoteCard(
        ticker=symbol,
        as_of=as_of,
        source=live_bars_source or BARS_SOURCE,
        last_close=round(last_close, _ROUND_DP),
        prev_close=round(prev_close, _ROUND_DP),
        change_abs=change_abs,
        change_pct=change_pct,
        open=round(float(last_row["open"]), _ROUND_DP),
        high=round(float(last_row["high"]), _ROUND_DP),
        low=round(float(last_row["low"]), _ROUND_DP),
        volume=int(round(float(last_row["volume"]))),
        week52_high=week52_high,
        week52_low=week52_low,
        ytd_pct=ytd_pct,
        one_year_pct=one_year_pct,
        thirty_day_pct=thirty_day_pct,
        market_cap=market_cap,
        pe=pe,
        pb=pb,
        dividend_yield=dividend_yield,
        snapshot_as_of=snapshot_as_of,
        snapshot_source=snapshot_source,
        series=series,
    )
