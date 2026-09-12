"""Tests for `fathom.quotes` (RTM: FR-002, FR-003)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from fathom import data
from fathom.errors import Code, FathomError
from fathom.quotes import QUOTES_SOURCE, quote_card

# Anchors from data/SOURCES.md §Anchors.
_AAPL_AS_OF = dt.date(2026, 9, 11)
_AAPL_LAST_CLOSE = 332.27
_AAPL_PREV_CLOSE = 326.57
_AAPL_CHANGE_PCT = 1.75
_AAPL_WEEK52_HIGH = 344.27
_AAPL_WEEK52_LOW = 228.18


def test_fr002_aapl_anchors_match_sources(data_dir: Path) -> None:
    """AAPL's core fields match the hand-checked anchors in data/SOURCES.md."""
    card = quote_card("AAPL", data_dir)

    assert card.as_of == _AAPL_AS_OF
    assert card.last_close == _AAPL_LAST_CLOSE
    assert card.prev_close == _AAPL_PREV_CLOSE
    assert card.change_pct == _AAPL_CHANGE_PCT
    assert card.week52_high == _AAPL_WEEK52_HIGH
    assert card.week52_low == _AAPL_WEEK52_LOW


def test_fr002_series_is_trailing_ascending_and_matches_last_close(data_dir: Path) -> None:
    """`series` has at most 252 ascending points, ending at `last_close`."""
    card = quote_card("AAPL", data_dir)

    assert len(card.series) <= 252
    dates = [point.date for point in card.series]
    assert dates == sorted(dates)
    assert card.series[-1].close == card.last_close


def test_fr002_snapshot_fields_come_from_quotes_parquet(data_dir: Path) -> None:
    """Snapshot fields are populated from quotes.parquet with a tz-aware UTC timestamp."""
    card = quote_card("AAPL", data_dir)

    assert card.snapshot_source == QUOTES_SOURCE
    assert card.snapshot_as_of is not None
    assert card.snapshot_as_of.tzinfo is not None
    assert card.snapshot_as_of.utcoffset() == dt.timedelta(0)
    assert card.market_cap is not None
    assert card.pe is not None
    assert card.pb is not None
    assert card.dividend_yield is not None


def test_fr002_snapshot_nan_field_becomes_none(tmp_path: Path) -> None:
    """A NaN snapshot value in quotes.parquet surfaces as None, not NaN."""
    bars = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "AAPL"],
            "date": [dt.date(2026, 9, 9), dt.date(2026, 9, 10), dt.date(2026, 9, 11)],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )
    quotes = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "quote_time": [pd.Timestamp("2026-09-11T16:00:01", tz="UTC")],
            "last_price": [102.5],
            "pre_close": [101.5],
            "change_percent": [0.99],
            "volume": [1200.0],
            "market_cap": [float("nan")],
            "pe": [20.0],
            "pb": [3.0],
            "dividend_yield": [0.5],
        }
    )
    bars.to_parquet(tmp_path / "bars.parquet")
    quotes.to_parquet(tmp_path / "quotes.parquet")

    card = quote_card("AAPL", tmp_path)

    assert card.market_cap is None
    assert card.pe == 20.0
    assert card.pb == 3.0
    assert card.dividend_yield == 0.5


def test_fr002_unknown_ticker_raises_unknown_ticker(data_dir: Path) -> None:
    """An out-of-universe ticker raises UNKNOWN_TICKER via data.require_ticker."""
    with pytest.raises(FathomError) as exc_info:
        quote_card("ZZZZ", data_dir)

    assert exc_info.value.code == Code.UNKNOWN_TICKER


def test_fr002_does_not_mutate_cached_frames(data_dir: Path) -> None:
    """`quote_card` never mutates the cached bars/quotes frames."""
    bars_before = data.load_frame("bars", data_dir).copy(deep=True)
    quotes_before = data.load_frame("quotes", data_dir).copy(deep=True)

    quote_card("AAPL", data_dir)
    quote_card("JPM", data_dir)

    pd.testing.assert_frame_equal(bars_before, data.load_frame("bars", data_dir))
    pd.testing.assert_frame_equal(quotes_before, data.load_frame("quotes", data_dir))


def _independent_bars(data_dir: Path, ticker: str) -> pd.DataFrame:
    """Reload bars directly (bypassing fathom.quotes) for an independent recompute."""
    bars = pd.read_parquet(data_dir / "bars.parquet")
    return bars[bars["symbol"] == ticker].sort_values("date").reset_index(drop=True)


def _closest_on_or_before(frame: pd.DataFrame, target: dt.date) -> float | None:
    eligible = frame[frame["date"] <= target]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1]["close"])


def test_fr003_jpm_ytd_pct_matches_independent_recompute(data_dir: Path) -> None:
    """`ytd_pct` matches an independent recompute vs the prior calendar year's last close."""
    frame = _independent_bars(data_dir, "JPM")
    as_of: dt.date = frame["date"].iloc[-1]
    last_close = float(frame["close"].iloc[-1])
    base = _closest_on_or_before(frame, dt.date(as_of.year - 1, 12, 31))
    expected = round((last_close / base - 1) * 100, 2) if base is not None else None

    card = quote_card("JPM", data_dir)

    assert card.ytd_pct == expected


def test_fr003_jpm_one_year_pct_matches_independent_recompute(data_dir: Path) -> None:
    """`one_year_pct` matches an independent recompute vs the closest bar >= 365 days back."""
    frame = _independent_bars(data_dir, "JPM")
    as_of: dt.date = frame["date"].iloc[-1]
    last_close = float(frame["close"].iloc[-1])
    base = _closest_on_or_before(frame, as_of - dt.timedelta(days=365))
    expected = round((last_close / base - 1) * 100, 2) if base is not None else None

    card = quote_card("JPM", data_dir)

    assert card.one_year_pct == expected


def test_fr003_jpm_thirty_day_pct_matches_independent_recompute(data_dir: Path) -> None:
    """`thirty_day_pct` matches an independent recompute vs the closest bar >= 30 days back."""
    frame = _independent_bars(data_dir, "JPM")
    as_of: dt.date = frame["date"].iloc[-1]
    last_close = float(frame["close"].iloc[-1])
    base = _closest_on_or_before(frame, as_of - dt.timedelta(days=30))
    expected = round((last_close / base - 1) * 100, 2) if base is not None else None

    card = quote_card("JPM", data_dir)

    assert card.thirty_day_pct == expected
