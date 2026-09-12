"""Tests for fathom.data (RTM: FR-001, NFR-005, NFR-009)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fathom.data import company, load_frame, require_ticker
from fathom.errors import Code, FathomError


def test_fr001_require_ticker_uppercases_known_ticker() -> None:
    assert require_ticker("aapl") == "AAPL"


def test_fr001_require_ticker_unknown_raises_with_universe_listed() -> None:
    with pytest.raises(FathomError) as excinfo:
        require_ticker("ZZZZ")

    assert excinfo.value.code == Code.UNKNOWN_TICKER
    from fathom.config import UNIVERSE

    for ticker in UNIVERSE:
        assert ticker in excinfo.value.message


def test_fr001_company_msft_returns_expected_name_and_exchange(data_dir: Path) -> None:
    firm = company("MSFT", data_dir)

    assert firm.name == "Microsoft Corporation"
    assert firm.exchange == "NasdaqGS"


def test_nfr009_bars_frame_has_exact_expected_columns(data_dir: Path) -> None:
    bars = load_frame("bars", data_dir)

    assert list(bars.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]


def test_nfr009_fixture_total_size_under_20mb(data_dir: Path) -> None:
    total_bytes = sum(path.stat().st_size for path in data_dir.glob("*.parquet"))

    assert total_bytes <= 20 * 1024 * 1024


def test_nfr005_load_frame_missing_file_raises_data_missing(tmp_path: Path) -> None:
    with pytest.raises(FathomError) as excinfo:
        load_frame("filings", tmp_path)

    assert excinfo.value.code == Code.DATA_MISSING
    assert excinfo.value.details == {"name": "filings"}
