"""Tests for fathom.data (RTM: FR-001, NFR-005, NFR-009, FR-020)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fathom.config import Settings
from fathom.data import company, load_frame, require_ticker
from fathom.errors import Code, FathomError
from fathom.live import data_dir_for


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


# --- FR-020 (AC2): require_ticker/data_dir_for source routing --------------------------------


def test_fr020_require_ticker_settings_none_is_fixture_behaviour() -> None:
    assert require_ticker("aapl", None) == "AAPL"


def test_fr020_require_ticker_fixture_settings_unchanged() -> None:
    settings = Settings(data_source="fixture")
    assert require_ticker("aapl", settings) == "AAPL"
    with pytest.raises(FathomError) as excinfo:
        require_ticker("ZZZZ", settings)
    assert excinfo.value.code == Code.UNKNOWN_TICKER


def test_fr020_require_ticker_live_accepts_brk_b_variants() -> None:
    settings = Settings(data_source="live", sec_contact="t@example.com")
    assert require_ticker("brk.b", settings) == "BRK.B"
    assert require_ticker("PYPL", settings) == "PYPL"


def test_fr020_require_ticker_live_rejects_invalid_shape() -> None:
    settings = Settings(data_source="live", sec_contact="t@example.com")
    with pytest.raises(FathomError) as excinfo:
        require_ticker("$$", settings)
    assert excinfo.value.code == Code.UNKNOWN_TICKER


def test_fr020_data_dir_for_fixture_mode_returns_settings_data_dir(data_dir: Path) -> None:
    settings = Settings(data_source="fixture", data_dir=data_dir)
    assert data_dir_for("AAPL", settings) == settings.data_dir


def test_fr020_data_dir_for_live_mode_returns_ticker_cache_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fathom.live as live_module
    from fathom.live.build import LiveManifest

    settings = Settings(
        data_source="live", sec_contact="t@example.com", live_cache_dir=tmp_path / "live"
    )
    fake_manifest = LiveManifest(
        ticker="AAPL",
        cik="0000320193",
        fetched_at="2026-09-01T00:00:00+00:00",
        data_dir=str(tmp_path / "live" / "AAPL"),
        filings=[],
        bars_source="yahoo via .cache/live/AAPL/bars.parquet",
        bars_from="2026-01-01",
        bars_to="2026-06-01",
        snapshot_source="SEC XBRL companyconcept x yahoo close",
        sections_coverage={},
    )

    def fake_materialize(ticker: str, settings: Settings, force: bool = False) -> LiveManifest:
        return fake_manifest

    monkeypatch.setattr(live_module, "materialize", fake_materialize)

    result = data_dir_for("AAPL", settings)

    assert result == tmp_path / "live" / "AAPL"
