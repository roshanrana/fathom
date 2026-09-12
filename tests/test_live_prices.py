"""Tests for fathom.live.prices.PriceClient (RTM: FR-022, NFR-013)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from fathom.errors import Code, FathomError
from fathom.live.http import LiveHttp
from fathom.live.prices import _STOOQ_HEADER, PriceClient

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "live"

_YAHOO_CHART = (FIXTURES / "yahoo_chart_aapl.json").read_bytes()
_STOOQ_CSV = (FIXTURES / "stooq_aapl.csv").read_bytes()
_STOOQ_MAINTENANCE = (FIXTURES / "stooq_maintenance.html").read_bytes()

_YAHOO_HOST = "https://query1.finance.yahoo.com/v8/finance/chart/"
_STOOQ_HOST = "https://stooq.com/q/d/l/"


def _yahoo_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_YAHOO_CHART)


def _stooq_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_STOOQ_CSV)


def _default_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.startswith(_YAHOO_HOST):
        return _yahoo_ok(request)
    if url.startswith(_STOOQ_HOST):
        return _stooq_ok(request)
    return httpx.Response(404)


def _make_client(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response] = _default_handler,
    *,
    primary: str = "yahoo",
) -> tuple[PriceClient, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(wrapped))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    return PriceClient(http, primary=primary), calls


def test_fr022_daily_bars_from_yahoo_has_exact_schema_and_last_source(tmp_path: Path) -> None:
    client, calls = _make_client(tmp_path)

    frame = client.daily_bars("AAPL")

    assert len(frame) == 30
    assert list(frame.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert (frame["symbol"] == "AAPL").all()
    assert all(isinstance(d, dt.date) for d in frame["date"])
    dates = list(frame["date"])
    assert dates == sorted(dates)
    for column in ("open", "high", "low", "close", "volume"):
        assert frame[column].dtype == "float64"
    assert client.last_source == "yahoo"
    assert len(calls) == 1


def test_fr022_daily_bars_requests_yahoo_and_stooq_symbols_for_brk_b(tmp_path: Path) -> None:
    client, calls = _make_client(tmp_path)

    client.daily_bars("BRK.B")

    assert len(calls) == 1
    assert str(calls[0].url).startswith(_YAHOO_HOST + "BRK-B")

    client2, calls2 = _make_client(tmp_path, primary="stooq")
    client2.daily_bars("BRK.B")

    assert len(calls2) == 1
    assert str(calls2[0].url).startswith(_STOOQ_HOST + "?s=brk-b.us")


def test_fr022_yahoo_500_falls_back_to_stooq(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_YAHOO_HOST):
            return httpx.Response(500)
        return _stooq_ok(request)

    client, calls = _make_client(tmp_path, handler)

    frame = client.daily_bars("AAPL")

    assert len(frame) == 30
    assert client.last_source == "stooq"
    assert len(calls) == 2


def test_fr022_yahoo_body_without_chart_result_falls_back_to_stooq(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_YAHOO_HOST):
            return httpx.Response(200, content=b'{"chart": {"result": null}}')
        return _stooq_ok(request)

    client, calls = _make_client(tmp_path, handler)

    frame = client.daily_bars("AAPL")

    assert len(frame) == 30
    assert client.last_source == "stooq"
    assert len(calls) == 2


def test_fr022_stooq_503_raises_source_http_with_no_body(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_YAHOO_HOST):
            return httpx.Response(500)
        return httpx.Response(503, content=b"maintenance detail")

    client, _ = _make_client(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        client.daily_bars("AAPL")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["source"] == "stooq"
    assert err.details.keys() == {"source", "status", "reason"}
    assert "maintenance detail" not in str(err.details)
    assert "maintenance detail" not in err.message


def test_fr022_stooq_maintenance_html_raises_source_http(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_YAHOO_HOST):
            return httpx.Response(500)
        return httpx.Response(200, content=_STOOQ_MAINTENANCE)

    client, _ = _make_client(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        client.daily_bars("AAPL")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["source"] == "stooq"
    assert "<html" not in str(err.details).lower()


def test_fr022_price_source_stooq_makes_stooq_primary_and_yahoo_fallback(tmp_path: Path) -> None:
    client, calls = _make_client(tmp_path, primary="stooq")

    frame = client.daily_bars("AAPL")

    assert client.last_source == "stooq"
    assert len(frame) == 30
    assert len(calls) == 1
    assert str(calls[0].url).startswith(_STOOQ_HOST)

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_STOOQ_HOST):
            return httpx.Response(503)
        return _yahoo_ok(request)

    client2, calls2 = _make_client(tmp_path / "second", handler, primary="stooq")
    frame2 = client2.daily_bars("AAPL")

    assert client2.last_source == "yahoo"
    assert len(frame2) == 30
    assert len(calls2) == 2


def test_nfr013_daily_bars_cached_second_call_zero_transport_calls(tmp_path: Path) -> None:
    client, calls = _make_client(tmp_path)

    first = client.daily_bars("AAPL")
    calls_after_first = len(calls)
    second = client.daily_bars("AAPL")
    calls_after_second = len(calls)

    assert calls_after_first == 1
    assert calls_after_second == calls_after_first
    assert first["close"].tolist() == second["close"].tolist()


def test_fr022_daily_bars_invalid_ticker_raises_unknown_ticker_before_request(
    tmp_path: Path,
) -> None:
    client, calls = _make_client(tmp_path)

    with pytest.raises(FathomError) as excinfo:
        client.daily_bars("bad ticker!")

    assert excinfo.value.code == Code.UNKNOWN_TICKER
    assert calls == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            b'{"chart": {"result": [{"timestamp": [null, 1700086400], '
            b'"indicators": {"quote": [{"open": [1.0, 2.0], "high": [1.5, 2.5], '
            b'"low": [0.5, 1.5], "close": [1.1, 2.2], "volume": [100, 200]}]}}]}}',
            id="null-timestamp-entry",
        ),
        pytest.param(
            b'{"chart": {"result": [{"timestamp": [1700000000], '
            b'"indicators": {"quote": [{"open": ["x"], "high": ["x"], '
            b'"low": ["x"], "close": ["not-a-number"], "volume": ["x"]}]}}]}}',
            id="string-ohlcv-values",
        ),
        pytest.param(
            b'{"chart": {"result": [{"timestamp": [1700000000, 1700086400], '
            b'"indicators": {"quote": [{"open": [1.0, 2.0], "high": [1.5, 2.5], '
            b'"low": [0.5, 1.5], "close": [], "volume": [100, 200]}]}}]}}',
            id="mismatched-array-lengths",
        ),
        pytest.param(b'{"chart": {"result": null}}', id="null-result"),
    ],
)
def test_fr022_yahoo_malformed_bodies_fall_back_to_stooq(tmp_path: Path, body: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_YAHOO_HOST):
            return httpx.Response(200, content=body)
        return _stooq_ok(request)

    client, calls = _make_client(tmp_path, handler)

    frame = client.daily_bars("AAPL")

    assert client.last_source == "stooq"
    assert any(str(c.url).startswith(_STOOQ_HOST) for c in calls)
    assert len(frame) == 30


def test_fr022_yahoo_and_stooq_both_malformed_raises_malformed_response_no_body(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(_YAHOO_HOST):
            return httpx.Response(200, content=b'{"chart": {"result": null}}')
        return httpx.Response(200, content=b"Date,Open,High,Low,Close,Volume\nnotadate,x,x,x,x,x\n")

    client, _ = _make_client(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        client.daily_bars("AAPL")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details == {"source": "stooq", "status": 200, "reason": "malformed response"}
    assert "notadate" not in str(err.details)
    assert "notadate" not in err.message


def test_fr022_stooq_csv_20000_rows_yields_at_most_10000_bars(tmp_path: Path) -> None:
    lines = [_STOOQ_HEADER]
    base = dt.date(2020, 1, 1)
    for i in range(20_000):
        day = base + dt.timedelta(days=i)
        price = 1.0 + (i % 100) * 0.01
        lines.append(f"{day.isoformat()},{price},{price},{price},{price},100")
    csv_body = ("\n".join(lines) + "\n").encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=csv_body)

    client, _ = _make_client(tmp_path, handler, primary="stooq")

    frame = client.daily_bars("AAPL")

    assert len(frame) <= 10_000


def test_fr022_stooq_non_numeric_cell_drops_only_that_row(tmp_path: Path) -> None:
    csv_body = (
        f"{_STOOQ_HEADER}\n"
        "2024-01-01,1.0,1.5,0.5,1.2,100\n"
        "2024-01-02,bad,1.6,0.6,1.3,200\n"
        "2024-01-03,1.1,1.6,0.6,1.4,300\n"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=csv_body)

    client, _ = _make_client(tmp_path, handler, primary="stooq")

    frame = client.daily_bars("AAPL")

    assert len(frame) == 2
    assert dt.date(2024, 1, 2) not in list(frame["date"])


def test_fr022_stooq_all_garbage_csv_is_source_failure(tmp_path: Path) -> None:
    csv_body = (f"{_STOOQ_HEADER}\nbad,bad,bad,bad,bad,bad\nalso-bad,x,x,x,x,x\n").encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=csv_body)

    client, _ = _make_client(tmp_path, handler, primary="stooq")

    with pytest.raises(FathomError) as excinfo:
        client.daily_bars("AAPL")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "malformed response"


def test_fr022_yahoo_drops_rows_with_null_close(tmp_path: Path) -> None:
    body = (
        b'{"chart": {"result": [{"timestamp": [1700000000, 1700086400], '
        b'"indicators": {"quote": [{"open": [1.0, 2.0], "high": [1.5, 2.5], '
        b'"low": [0.5, 1.5], "close": [null, 2.2], "volume": [100, 200]}]}}]}}'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    client, _ = _make_client(tmp_path, handler)

    frame = client.daily_bars("AAPL")

    assert len(frame) == 1
    assert frame["close"].iloc[0] == 2.2
