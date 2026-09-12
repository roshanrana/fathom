"""Fixture loaders and universe checks (LLD §2.3)."""

from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel

from fathom.config import UNIVERSE, Settings
from fathom.errors import Code, FathomError

FixtureName = Literal["filings", "bars", "quotes", "companies"]

# 05-m4-live-data.md §5 (frozen): live-mode ticker shape, checked after upper-casing.
_LIVE_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class Company(BaseModel):
    """Company master record (LLD §2.3)."""

    ticker: str
    name: str
    exchange: str
    sector: str
    industry: str
    website: str


@functools.cache
def load_frame(name: FixtureName, data_dir: Path) -> pd.DataFrame:
    """Load one of the fixture parquet files, cached by (name, data_dir)."""
    path = data_dir / f"{name}.parquet"
    if not path.exists():
        raise FathomError(
            Code.DATA_MISSING,
            f"fixture {name!r} is missing from {data_dir}",
            {"name": name},
        )
    return pd.read_parquet(path)


def require_ticker(ticker: str, settings: Settings | None = None) -> str:
    """Upper-case and validate a ticker (05-m4-live-data.md §5).

    Fixture mode (`settings` is `None` or `settings.data_source == "fixture"`): unchanged,
    validated against the fixed `UNIVERSE`. Live mode: only the shape
    `^[A-Z][A-Z0-9.\\-]{0,9}$` is checked here; actual existence is deferred to
    `SecClient.lookup` when the ticker is materialized.
    """
    upper = ticker.upper()
    if settings is not None and settings.data_source == "live":
        if not _LIVE_TICKER_RE.match(upper):
            raise FathomError(
                Code.UNKNOWN_TICKER,
                f"invalid ticker format {upper!r}",
                {"ticker": upper},
            )
        return upper
    if upper not in UNIVERSE:
        raise FathomError(
            Code.UNKNOWN_TICKER,
            f"unknown ticker {upper!r}; must be one of {', '.join(UNIVERSE)}",
            {"ticker": upper},
        )
    return upper


def company(ticker: str, data_dir: Path) -> Company:
    """Look up a company's master record from `companies.parquet`."""
    symbol = require_ticker(ticker)
    frame = load_frame("companies", data_dir)
    rows = frame[frame["ticker"] == symbol]
    if rows.empty:
        raise FathomError(
            Code.DATA_MISSING,
            f"no company record for {symbol!r}",
            {"name": "companies"},
        )
    row = rows.iloc[0]
    return Company(
        ticker=symbol,
        name=str(row["long_name"]),
        exchange=str(row["full_exchange_name"]),
        sector=str(row["sector"]),
        industry=str(row["industry"]),
        website=str(row["website"]),
    )
