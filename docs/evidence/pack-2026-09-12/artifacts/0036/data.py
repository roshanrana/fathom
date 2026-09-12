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


def require_ticker(
    ticker: str, settings: Settings | None = None, data_dir: Path | None = None
) -> str:
    """Upper-case and validate a ticker (05-m4-live-data.md §5, amended after T-020 attempt 1).

    The shape `^[A-Z][A-Z0-9.\\-]{0,9}$` is checked first, in every mode, before any path is
    built (B1/B6 control). Then: when `data_dir` is given, existence is checked against that
    directory's `companies.parquet` (fixture directories and live caches behave the same way).
    When `data_dir` is `None` and `settings` is fixture mode or `None`, existence is checked
    against the fixed `UNIVERSE`. When `data_dir` is `None` and `settings` is live, only the
    shape is checked here; existence is deferred to `SecClient.lookup` when materialized.
    """
    upper = ticker.upper()
    if not _LIVE_TICKER_RE.fullmatch(upper):
        raise FathomError(
            Code.UNKNOWN_TICKER,
            f"invalid ticker format {upper!r}",
            {"ticker": upper},
        )

    if data_dir is not None:
        frame = load_frame("companies", data_dir)
        if upper not in set(frame["ticker"]):
            raise FathomError(
                Code.UNKNOWN_TICKER,
                f"unknown ticker {upper!r} in {data_dir}",
                {"ticker": upper},
            )
        return upper

    if settings is not None and settings.data_source == "live":
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
    symbol = require_ticker(ticker, data_dir=data_dir)
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
