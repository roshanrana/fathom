"""Materialize the fixture-shaped live cache for one ticker (05-m4-live-data.md §4).

`materialize(ticker, settings, force=False)` writes `filings.parquet`, `bars.parquet`,
`quotes.parquet`, `companies.parquet` (exactly the fixture schemas, LLD §2.3) plus
`manifest.json` into `<live_cache_dir>/<TICKER>/`. A fresh `manifest.json` (within
`settings.live_ttl_hours`) short-circuits the whole pipeline with zero HTTP calls;
`force=True` always recomputes. `data_dir_for` (in `fathom/live/__init__.py`) is the only
call site the rest of the app should use.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ValidationError

from fathom import __version__
from fathom.config import Settings
from fathom.data import require_ticker
from fathom.errors import Code, FathomError
from fathom.filings import parse_sections
from fathom.live.facts import snapshot as compute_snapshot
from fathom.live.http import LiveHttp
from fathom.live.prices import PriceClient
from fathom.live.sec import SecClient, SecFiling

_ROUND_DP = 2
_QUOTE_TIME_HOUR_UTC = 21


class LiveManifest(BaseModel):
    """Per-ticker live-materialization manifest (05-m4-live-data.md §4, frozen)."""

    ticker: str
    cik: str
    fetched_at: datetime
    data_dir: str
    filings: list[SecFiling]
    bars_source: str
    bars_from: date
    bars_to: date
    snapshot_source: str
    sections_coverage: dict[str, list[str]]


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _read_fresh_manifest(
    manifest_path: Path, ttl_hours: float, clock: Callable[[], datetime]
) -> LiveManifest | None:
    """The manifest at `manifest_path` if it parses and is within `ttl_hours`, else None."""
    if not manifest_path.exists():
        return None
    try:
        manifest = LiveManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None
    age_hours = (clock() - manifest.fetched_at).total_seconds() / 3600.0
    if age_hours >= ttl_hours:
        return None
    return manifest


def _sections_for_filing(accession: str, form: str, text: str) -> list[str]:
    """Canonical section ids found in `text`; empty list when the parser finds none."""
    try:
        sections = parse_sections(text, form)
    except FathomError as exc:
        if exc.code is not Code.PARSE_FAILED:
            raise
        return []
    return [section.section_id for section in sections]


def _filing_row(symbol: str, filing: SecFiling, company_name: str, text: str) -> dict[str, Any]:
    return {
        "ticker": symbol,
        "cik": filing.cik,
        "company_name": company_name,
        "form": filing.form,
        "filing_date": filing.filing_date,
        "accession": filing.accession,
        "text": text,
        "n_chars": len(text),
    }


def _quote_row(
    symbol: str,
    bars: pd.DataFrame,
    snapshot: dict[str, float | str | None],
    quote_time: datetime,
) -> dict[str, Any]:
    last_close = float(bars.iloc[-1]["close"])
    prev_close = float(bars.iloc[-2]["close"]) if len(bars) > 1 else last_close
    change_percent = round((last_close / prev_close - 1) * 100, _ROUND_DP) if prev_close else 0.0
    return {
        "symbol": symbol,
        "quote_time": quote_time,
        "last_price": last_close,
        "pre_close": prev_close,
        "change_percent": change_percent,
        "volume": float(bars.iloc[-1]["volume"]),
        "market_cap": snapshot["market_cap"],
        "pe": snapshot["pe"],
        "pb": snapshot["pb"],
        "dividend_yield": snapshot["dividend_yield"],
    }


def materialize(
    ticker: str,
    settings: Settings,
    force: bool = False,
    *,
    http: LiveHttp | None = None,
    clock: Callable[[], datetime] = _default_clock,
) -> LiveManifest:
    """Materialize `ticker`'s live cache, serving a fresh manifest without any HTTP call.

    `force=True` bypasses the manifest TTL check and always recomputes. `http`/`clock` are
    test seams: production callers leave both at their defaults.
    """
    symbol = require_ticker(ticker, settings)
    live_dir = settings.live_cache_dir / symbol
    manifest_path = live_dir / "manifest.json"

    if not force:
        cached = _read_fresh_manifest(manifest_path, settings.live_ttl_hours, clock)
        if cached is not None:
            return cached

    if not settings.sec_contact:
        raise FathomError(
            Code.SOURCE_CONFIG,
            "FATHOM_SEC_CONTACT is required to contact SEC EDGAR in live mode",
            {"var": "FATHOM_SEC_CONTACT"},
        )

    live_http = http
    if live_http is None:
        user_agent = f"Fathom/{__version__} ({settings.sec_contact})"
        live_http = LiveHttp(cache_dir=settings.live_cache_dir, user_agent=user_agent)

    sec = SecClient(http=live_http, contact=settings.sec_contact)
    price_client = PriceClient(live_http, primary=settings.price_source)

    company = sec.lookup(symbol)
    filings = sec.filings(company.cik)

    bars = price_client.daily_bars(symbol)
    if bars.empty:
        raise FathomError(Code.SOURCE_EMPTY, f"no bars for {symbol!r}", {"ticker": symbol})
    bars_source = price_client.last_source or settings.price_source

    last_close = float(bars.iloc[-1]["close"])
    quote_time = datetime.combine(bars.iloc[-1]["date"], time(_QUOTE_TIME_HOUR_UTC), tzinfo=UTC)

    snapshot = compute_snapshot(sec, company.cik, last_close, quote_time)
    snapshot_source = f"{snapshot['snapshot_source']} × {bars_source} close"
    full_bars_source = f"{bars_source} via .cache/live/{symbol}/bars.parquet"

    filing_rows: list[dict[str, Any]] = []
    sections_coverage: dict[str, list[str]] = {}
    for filing in filings:
        text = sec.document_text(filing)
        filing_rows.append(_filing_row(symbol, filing, company.name, text))
        sections_coverage[filing.accession] = _sections_for_filing(
            filing.accession, filing.form, text
        )

    companies_row = {
        "ticker": symbol,
        "long_name": company.name,
        "full_exchange_name": company.exchange or "",
        "sector": company.sic_description or "",
        "industry": company.sic_description or "",
        "website": "",
    }
    quotes_row = _quote_row(symbol, bars, snapshot, quote_time)

    live_dir.mkdir(parents=True, exist_ok=True)
    filings_columns = [
        "ticker",
        "cik",
        "company_name",
        "form",
        "filing_date",
        "accession",
        "text",
        "n_chars",
    ]
    pd.DataFrame(filing_rows, columns=filings_columns).to_parquet(
        live_dir / "filings.parquet", index=False
    )
    bars.to_parquet(live_dir / "bars.parquet", index=False)
    pd.DataFrame(
        [quotes_row],
        columns=[
            "symbol",
            "quote_time",
            "last_price",
            "pre_close",
            "change_percent",
            "volume",
            "market_cap",
            "pe",
            "pb",
            "dividend_yield",
        ],
    ).to_parquet(live_dir / "quotes.parquet", index=False)
    pd.DataFrame(
        [companies_row],
        columns=["ticker", "long_name", "full_exchange_name", "sector", "industry", "website"],
    ).to_parquet(live_dir / "companies.parquet", index=False)

    manifest = LiveManifest(
        ticker=symbol,
        cik=company.cik,
        fetched_at=clock(),
        data_dir=str(live_dir),
        filings=filings,
        bars_source=full_bars_source,
        bars_from=bars["date"].min(),
        bars_to=bars["date"].max(),
        snapshot_source=snapshot_source,
        sections_coverage=sections_coverage,
    )
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest
