"""Opt-in network smoke test against real SEC EDGAR / Yahoo / Stooq endpoints.

RTM: FR-020, FR-024, FR-025, NFR-012, NFR-013. This is the one test in the suite that touches
the network; it is skipped unless both `FATHOM_NETWORK_TESTS=1` and `FATHOM_SEC_CONTACT` are set,
so the gate, CI and every other test run (NFR-013) never hit the network. Run it explicitly:

    FATHOM_NETWORK_TESTS=1 FATHOM_SEC_CONTACT=<your.name@example.com> \
        uv run pytest tests/test_live_network.py -q

Two tickers outside the 20-ticker fixture universe (NFLX, COST) are materialized with
`force=True` into a temporary cache directory (never `.cache/live/` — this test never touches
the repo's own cache), so this run always exercises a real cold start. Elapsed seconds per
ticker are printed (NFR-012 is measured and reported, not gated — no timing assertion here).
"""

from __future__ import annotations

import os
import time

import pytest

from fathom.briefing import brief
from fathom.config import Settings
from fathom.live.build import materialize

pytestmark = pytest.mark.skipif(
    os.environ.get("FATHOM_NETWORK_TESTS") != "1" or not os.environ.get("FATHOM_SEC_CONTACT"),
    reason="network smoke test: set FATHOM_NETWORK_TESTS=1 and FATHOM_SEC_CONTACT to run",
)

_TICKERS = ("NFLX", "COST")
_MIN_BARS = 250


@pytest.mark.parametrize("ticker", _TICKERS)
def test_live_materialize_and_offline_brief(ticker: str, tmp_path: object) -> None:
    settings = Settings(
        live_cache_dir=tmp_path / "live",  # type: ignore[arg-type]
        data_source="live",
        sec_contact=os.environ["FATHOM_SEC_CONTACT"],
        audit_path=tmp_path / "audit.jsonl",  # type: ignore[arg-type]
    )

    start = time.perf_counter()
    manifest = materialize(ticker, settings, force=True)
    elapsed = time.perf_counter() - start
    print(f"\n[live smoke] {ticker} cold materialize: {elapsed:.2f}s")

    assert manifest.ticker == ticker

    ten_k = next(f for f in manifest.filings if f.form == "10-K")
    ten_qs = [f for f in manifest.filings if f.form == "10-Q"]
    assert ten_qs, f"{ticker}: expected at least one 10-Q in the last 24 months"

    ten_k_sections = set(manifest.sections_coverage[ten_k.accession])
    assert {"10-K:1A", "10-K:7"} <= ten_k_sections, (
        f"{ticker}: 10-K parser coverage missing 1A/7, got {sorted(ten_k_sections)}"
    )
    for filing in ten_qs:
        q_sections = set(manifest.sections_coverage[filing.accession])
        assert "10-Q:I.2" in q_sections, (
            f"{ticker}: 10-Q {filing.accession} parser coverage missing I.2, "
            f"got {sorted(q_sections)}"
        )

    import pandas as pd

    bars = pd.read_parquet(manifest.data_dir + "/bars.parquet")
    assert len(bars) >= _MIN_BARS, f"{ticker}: expected >= {_MIN_BARS} bars, got {len(bars)}"

    quotes = pd.read_parquet(manifest.data_dir + "/quotes.parquet")
    assert quotes.iloc[0]["market_cap"] is not None
    assert not pd.isna(quotes.iloc[0]["market_cap"])

    # Offline brief on the now-materialized live cache: same-process TTL cache hit, zero HTTP.
    briefing = brief(ticker, settings, provider=None)
    assert briefing.ticker == ticker
    assert briefing.verified_share == 1.0
