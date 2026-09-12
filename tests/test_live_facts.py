"""Tests for fathom.live.facts.snapshot (RTM: FR-023)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from fathom.errors import Code, FathomError
from fathom.live.facts import SNAPSHOT_SOURCE, snapshot
from fathom.live.http import LiveHttp
from fathom.live.sec import SecClient

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "live"

_CIK = "0000320193"
_LAST_CLOSE = 332.27
_QUOTE_TIME = datetime(2026, 9, 1, tzinfo=UTC)

_SHARES = (FIXTURES / "aapl_shares_outstanding.json").read_bytes()
_EPS = (FIXTURES / "aapl_eps_diluted.json").read_bytes()
_EQUITY = (FIXTURES / "aapl_stockholders_equity.json").read_bytes()
_DIVIDENDS = (FIXTURES / "aapl_dividends_per_share.json").read_bytes()

# Hand-computed from the trimmed fixtures (last 8 entries each):
#   shares: latest dei:EntityCommonStockSharesOutstanding, end=2026-07-17 -> 14,594,180,000
#   eps_ttm: CY2025Q2 1.57 + CY2025Q4 2.84 + CY2026Q1 2.01 + CY2026Q2 2.02 = 8.44
#   equity: latest CY####Q#I StockholdersEquity, end=2026-06-27 -> 107,520,000,000
#   dps_ttm: CY2025Q2 0.26 + CY2025Q4 0.26 + CY2026Q1 0.26 + CY2026Q2 0.27 = 1.05
_EXPECTED_MARKET_CAP = 4849208188600.0
_EXPECTED_PE = 39.37
_EXPECTED_PB = 45.1
_EXPECTED_DIVIDEND_YIELD = 0.32


def _concept_handler(
    overrides: dict[str, bytes | int] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """Route companyconcept URLs to the fixtures; `overrides` maps concept name -> body/status."""
    overrides = overrides or {}
    bodies = {
        "EntityCommonStockSharesOutstanding": _SHARES,
        "EarningsPerShareDiluted": _EPS,
        "StockholdersEquity": _EQUITY,
        "CommonStockDividendsPerShareDeclared": _DIVIDENDS,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for concept, body in bodies.items():
            if url.endswith(f"/{concept}.json"):
                override = overrides.get(concept)
                if isinstance(override, int):
                    return httpx.Response(override, content=b"not found")
                return httpx.Response(200, content=override if override is not None else body)
        return httpx.Response(404, content=b"not found")

    return handler


def _make_sec(tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response]) -> SecClient:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    return SecClient(http=http, contact="t@example.com")


def test_fr023_snapshot_matches_hand_computed_values_from_fixtures(tmp_path: Path) -> None:
    sec = _make_sec(tmp_path, _concept_handler())

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["market_cap"] == _EXPECTED_MARKET_CAP
    assert result["pe"] == _EXPECTED_PE
    assert result["pb"] == _EXPECTED_PB
    assert result["dividend_yield"] == _EXPECTED_DIVIDEND_YIELD
    assert result["snapshot_source"] == SNAPSHOT_SOURCE


def test_fr023_missing_shares_concept_yields_market_cap_and_pb_none(tmp_path: Path) -> None:
    sec = _make_sec(tmp_path, _concept_handler({"EntityCommonStockSharesOutstanding": 404}))

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["market_cap"] is None
    assert result["pb"] is None
    assert result["pe"] == _EXPECTED_PE
    assert result["dividend_yield"] == _EXPECTED_DIVIDEND_YIELD


def test_fr023_missing_eps_concept_yields_pe_none_others_computed(tmp_path: Path) -> None:
    sec = _make_sec(tmp_path, _concept_handler({"EarningsPerShareDiluted": 404}))

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["pe"] is None
    assert result["market_cap"] == _EXPECTED_MARKET_CAP
    assert result["pb"] == _EXPECTED_PB
    assert result["dividend_yield"] == _EXPECTED_DIVIDEND_YIELD


def test_fr023_missing_equity_concept_yields_pb_none_others_computed(tmp_path: Path) -> None:
    sec = _make_sec(tmp_path, _concept_handler({"StockholdersEquity": 404}))

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["pb"] is None
    assert result["market_cap"] == _EXPECTED_MARKET_CAP
    assert result["pe"] == _EXPECTED_PE
    assert result["dividend_yield"] == _EXPECTED_DIVIDEND_YIELD


def test_fr023_missing_dividends_concept_yields_zero_yield_not_none(tmp_path: Path) -> None:
    sec = _make_sec(tmp_path, _concept_handler({"CommonStockDividendsPerShareDeclared": 404}))

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["dividend_yield"] == 0.0
    assert result["market_cap"] == _EXPECTED_MARKET_CAP
    assert result["pe"] == _EXPECTED_PE
    assert result["pb"] == _EXPECTED_PB


def test_fr023_eps_ttm_non_positive_yields_pe_none(tmp_path: Path) -> None:
    negative_eps = json.dumps(
        {
            "units": {
                "USD/shares": [
                    {"end": "2026-03-28", "val": -1.0, "frame": "CY2026Q1"},
                    {"end": "2026-06-27", "val": -0.5, "frame": "CY2026Q2"},
                ]
            }
        }
    ).encode()

    sec = _make_sec(tmp_path, _concept_handler({"EarningsPerShareDiluted": negative_eps}))

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["pe"] is None


def test_fr023_fuzz_odd_fact_shapes_never_raise(tmp_path: Path) -> None:
    empty_units = json.dumps({"units": {}}).encode()
    missing_frame = json.dumps({"units": {"USD": [{"end": "2026-06-27", "val": 1.0}]}}).encode()
    non_numeric_val = json.dumps(
        {"units": {"USD": [{"end": "2026-06-27", "val": "not-a-number", "frame": "CY2026Q2I"}]}}
    ).encode()
    no_units_key = json.dumps({"unexpected": True}).encode()

    sec = _make_sec(
        tmp_path,
        _concept_handler(
            {
                "EntityCommonStockSharesOutstanding": empty_units,
                "EarningsPerShareDiluted": missing_frame,
                "StockholdersEquity": non_numeric_val,
                "CommonStockDividendsPerShareDeclared": no_units_key,
            }
        ),
    )

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["market_cap"] is None
    assert result["pe"] is None
    assert result["pb"] is None
    assert result["dividend_yield"] == 0.0
    assert result["snapshot_source"] == SNAPSHOT_SOURCE


def test_fr023_invalid_cik_raises_source_http_before_any_request(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(404, content=b"not found")

    sec = _make_sec(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        snapshot(sec, "12", last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details == {"source": "sec", "status": 0, "reason": "invalid identifier"}
    assert calls == []


def test_fr023_cik_with_trailing_newline_raises_source_http_zero_requests(
    tmp_path: Path,
) -> None:
    """T-023 attempt 2 F2: "0000320193\\n" must not slip past `$`-anchored validation."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(404, content=b"not found")

    sec = _make_sec(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        snapshot(sec, "0000320193\n", last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details == {"source": "sec", "status": 0, "reason": "invalid identifier"}
    assert calls == []


def test_fr023_nan_and_infinity_literals_yield_none_and_json_serialisable(
    tmp_path: Path,
) -> None:
    nan_shares = json.dumps(
        {
            "units": {
                "shares": [{"end": "2026-07-17", "val": float("nan"), "frame": None}],
            }
        },
        allow_nan=True,
    ).encode()
    inf_equity = json.dumps(
        {
            "units": {
                "USD": [{"end": "2026-06-27", "val": float("inf"), "frame": "CY2026Q2I"}],
            }
        },
        allow_nan=True,
    ).encode()

    sec = _make_sec(
        tmp_path,
        _concept_handler(
            {
                "EntityCommonStockSharesOutstanding": nan_shares,
                "StockholdersEquity": inf_equity,
            }
        ),
    )

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["market_cap"] is None
    assert result["pb"] is None
    # Every field must be finite/None so strict JSON serialisation never fails.
    json.dumps(result, allow_nan=False)


def test_fr023_out_of_range_facts_are_treated_as_missing(tmp_path: Path) -> None:
    huge_shares = json.dumps(
        {"units": {"shares": [{"end": "2026-07-17", "val": 1e13, "frame": None}]}}
    ).encode()
    huge_equity = json.dumps(
        {"units": {"USD": [{"end": "2026-06-27", "val": 2e13, "frame": "CY2026Q2I"}]}}
    ).encode()
    huge_eps = json.dumps(
        {"units": {"USD/shares": [{"end": "2026-06-27", "val": 1e5, "frame": "CY2026Q2"}]}}
    ).encode()
    huge_dps = json.dumps(
        {"units": {"USD/shares": [{"end": "2026-06-27", "val": 1e4, "frame": "CY2026Q2"}]}}
    ).encode()

    sec = _make_sec(
        tmp_path,
        _concept_handler(
            {
                "EntityCommonStockSharesOutstanding": huge_shares,
                "StockholdersEquity": huge_equity,
                "EarningsPerShareDiluted": huge_eps,
                "CommonStockDividendsPerShareDeclared": huge_dps,
            }
        ),
    )

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert result["market_cap"] is None
    assert result["pb"] is None
    assert result["pe"] is None
    assert result["dividend_yield"] == 0.0


def test_fr023_zero_last_close_does_not_raise(tmp_path: Path) -> None:
    sec = _make_sec(tmp_path, _concept_handler())

    result = snapshot(sec, _CIK, last_close=0.0, quote_time=_QUOTE_TIME)

    assert result["market_cap"] == 0.0
    assert result["dividend_yield"] is None


@pytest.mark.parametrize("concept", ["EntityCommonStockSharesOutstanding"])
def test_fr023_all_four_concepts_are_fetched(tmp_path: Path, concept: str) -> None:
    calls: list[str] = []
    base_handler = _concept_handler()

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return base_handler(request)

    sec = _make_sec(tmp_path, handler)
    snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)

    assert any(concept in url for url in calls)
    assert len(calls) == 4


class _StubSecReturns:
    """Stands in for `SecClient`, returning a fixed (possibly malformed) payload."""

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def company_concept(self, cik: str, taxonomy: str, concept: str) -> dict[str, object]:
        del cik, taxonomy, concept
        return self._payload  # type: ignore[return-value]


class _StubSecRaises:
    """Stands in for `SecClient`, always raising the given `FathomError`."""

    def __init__(self, error: FathomError) -> None:
        self._error = error

    def company_concept(self, cik: str, taxonomy: str, concept: str) -> dict[str, object]:
        del cik, taxonomy, concept
        raise self._error


@pytest.mark.parametrize(
    "payload",
    ["str", [], None, 42, True],
    ids=["json-string", "json-list", "json-null", "json-int", "json-bool"],
)
def test_fr023_snapshot_malformed_concept_payload_yields_none_fields_no_raise(
    payload: object,
) -> None:
    sec = _StubSecReturns(payload)

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)  # type: ignore[arg-type]

    assert result["market_cap"] is None
    assert result["pe"] is None
    assert result["pb"] is None
    assert result["dividend_yield"] == 0.0


def test_fr023_snapshot_concept_source_http_raise_yields_none_fields_no_raise() -> None:
    error = FathomError(
        Code.SOURCE_HTTP,
        "sec companyconcept response could not be parsed",
        {"source": "sec", "status": 200, "reason": "malformed response"},
    )
    sec = _StubSecRaises(error)

    result = snapshot(sec, _CIK, last_close=_LAST_CLOSE, quote_time=_QUOTE_TIME)  # type: ignore[arg-type]

    assert result["market_cap"] is None
    assert result["pe"] is None
    assert result["pb"] is None
    assert result["dividend_yield"] == 0.0
