"""Tests for fathom.live.http.LiveHttp (RTM: FR-025, NFR-013)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from fathom.errors import Code, FathomError
from fathom.live.http import LiveHttp

CACHE_TTL_HOURS = 6.0


def _counting_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    return httpx.MockTransport(wrapped), calls


def _ok_handler(body: bytes = b"hello") -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    return handler


def _noop_sleeper(seconds: float) -> None:
    return None


def _real_clock() -> float:
    return time.monotonic()


def _make_http(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    clock: Callable[[], float] = _real_clock,
    sleeper: Callable[[float], None] = _noop_sleeper,
) -> tuple[LiveHttp, list[httpx.Request]]:
    transport, calls = _counting_transport(handler)
    client = httpx.Client(transport=transport)
    http = LiveHttp(
        cache_dir=tmp_path,
        user_agent="Fathom/0.1.0 (t@example.com)",
        client=client,
        clock=clock,
        sleeper=sleeper,
    )
    return http, calls


def test_nfr013_get_writes_cache_body_and_meta(tmp_path: Path) -> None:
    http, calls = _make_http(tmp_path, _ok_handler(b"the body"))

    body = http.get("https://example.com/x", ttl_hours=CACHE_TTL_HOURS, source="sec")

    assert body == b"the body"
    assert len(calls) == 1
    cache_files = list((tmp_path / "_http").iterdir())
    bodies = [p for p in cache_files if not p.name.endswith(".meta")]
    metas = [p for p in cache_files if p.name.endswith(".meta")]
    assert len(bodies) == 1
    assert len(metas) == 1
    assert bodies[0].read_bytes() == b"the body"
    meta = json.loads(metas[0].read_text(encoding="utf-8"))
    assert meta["url"] == "https://example.com/x"
    assert meta["status"] == 200
    assert meta["source"] == "sec"
    assert "fetched_at" in meta


def test_nfr013_get_serves_from_cache_within_ttl_without_transport_call(tmp_path: Path) -> None:
    http, calls = _make_http(tmp_path, _ok_handler(b"cached"))

    first = http.get("https://example.com/x", ttl_hours=CACHE_TTL_HOURS, source="sec")
    second = http.get("https://example.com/x", ttl_hours=CACHE_TTL_HOURS, source="sec")

    assert first == second == b"cached"
    assert len(calls) == 1


def test_nfr013_get_refetches_after_ttl_expires(tmp_path: Path) -> None:
    responses = iter([b"first", b"second"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(responses))

    http, calls = _make_http(tmp_path, handler)

    first = http.get("https://example.com/x", ttl_hours=1e-9, source="sec")
    time.sleep(0.01)
    second = http.get("https://example.com/x", ttl_hours=1e-9, source="sec")

    assert first == b"first"
    assert second == b"second"
    assert len(calls) == 2


def test_nfr013_get_force_bypasses_cache(tmp_path: Path) -> None:
    responses = iter([b"first", b"second"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(responses))

    http, calls = _make_http(tmp_path, handler)

    first = http.get("https://example.com/x", ttl_hours=CACHE_TTL_HOURS, source="sec")
    second = http.get("https://example.com/x", ttl_hours=CACHE_TTL_HOURS, source="sec", force=True)

    assert first == b"first"
    assert second == b"second"
    assert len(calls) == 2


def test_nfr013_get_ttl_none_caches_forever(tmp_path: Path) -> None:
    http, calls = _make_http(tmp_path, _ok_handler(b"forever"))

    http.get("https://example.com/doc", ttl_hours=None, source="sec")
    http.get("https://example.com/doc", ttl_hours=None, source="sec")

    assert len(calls) == 1


def test_fr025_throttle_enforces_min_spacing_via_monkeypatched_clock(tmp_path: Path) -> None:
    clock_values = iter([100.0, 100.05])
    sleep_calls: list[float] = []

    http, calls = _make_http(
        tmp_path,
        _ok_handler(b"x"),
        clock=lambda: next(clock_values),
        sleeper=sleep_calls.append,
    )

    http.get("https://www.sec.gov/a", ttl_hours=None, source="sec")
    http.get("https://www.sec.gov/b", ttl_hours=None, source="sec")

    assert len(calls) == 2
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(0.07, abs=1e-9)


def test_fr025_throttle_skips_non_sec_hosts(tmp_path: Path) -> None:
    clock_values = iter([100.0, 100.0])
    sleep_calls: list[float] = []

    http, calls = _make_http(
        tmp_path,
        _ok_handler(b"x"),
        clock=lambda: next(clock_values),
        sleeper=sleep_calls.append,
    )

    http.get("https://query1.finance.yahoo.com/a", ttl_hours=None, source="yahoo")
    http.get("https://query1.finance.yahoo.com/b", ttl_hours=None, source="yahoo")

    assert len(calls) == 2
    assert sleep_calls == []


def test_fr025_non_2xx_maps_to_source_http_with_no_body(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"secret internal detail", text="not found")

    http, _ = _make_http(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        http.get("https://www.sec.gov/missing", ttl_hours=None, source="sec")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details.keys() == {"source", "status", "reason"}
    assert err.details["source"] == "sec"
    assert err.details["status"] == 404
    assert "secret internal detail" not in err.message
    assert "secret internal detail" not in str(err.details)


def test_fr025_httpx_error_maps_to_source_http_status_zero(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    http, _ = _make_http(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        http.get("https://www.sec.gov/unreachable", ttl_hours=None, source="sec")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["source"] == "sec"
    assert err.details["status"] == 0


def test_fr025_body_over_25mb_rejected_as_too_large(tmp_path: Path) -> None:
    big_body = b"x" * (25 * 1024 * 1024 + 1)

    http, _ = _make_http(tmp_path, _ok_handler(big_body))

    with pytest.raises(FathomError) as excinfo:
        http.get("https://www.sec.gov/huge", ttl_hours=None, source="sec")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "too large"
    cache_dir = tmp_path / "_http"
    assert not cache_dir.exists() or list(cache_dir.iterdir()) == []


def _counted_chunk_stream(total_bytes: int, counter: list[int], chunk_size: int = 1024 * 1024):
    remaining = total_bytes
    while remaining > 0:
        n = min(chunk_size, remaining)
        counter[0] += n
        yield b"x" * n
        remaining -= n


def test_fr025_streamed_30mb_body_aborts_after_26mb_read_no_text_decode(
    tmp_path: Path,
) -> None:
    read_bytes = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_counted_chunk_stream(30 * 1024 * 1024, read_bytes))

    http, _ = _make_http(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        http.get("https://www.sec.gov/huge-stream", ttl_hours=None, source="sec")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "too large"
    # Aborted well before the full 30 MB was pulled from the source stream.
    assert read_bytes[0] <= 26 * 1024 * 1024


def test_fr025_streamed_20mb_body_succeeds(tmp_path: Path) -> None:
    read_bytes = [0]
    total = 20 * 1024 * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_counted_chunk_stream(total, read_bytes))

    http, _ = _make_http(tmp_path, handler)

    body = http.get("https://www.sec.gov/ok-stream", ttl_hours=None, source="sec")

    assert len(body) == total
    assert read_bytes[0] == total


def test_fr025_transport_error_reason_is_exception_class_name_no_url(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("http://host/secret?x=1")

    http, _ = _make_http(tmp_path, handler)

    with pytest.raises(FathomError) as excinfo:
        http.get("https://www.sec.gov/unreachable", ttl_hours=None, source="sec")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "ConnectError"
    assert "secret" not in err.message
    assert "secret" not in str(err.details)
    assert "http://host" not in err.message
    assert "http://host" not in str(err.details)


def test_nfr013_user_agent_header_set_on_every_request(tmp_path: Path) -> None:
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, content=b"ok")

    http, _ = _make_http(tmp_path, handler)
    http.get("https://www.sec.gov/a", ttl_hours=None, source="sec")

    assert seen_headers == ["Fathom/0.1.0 (t@example.com)"]
