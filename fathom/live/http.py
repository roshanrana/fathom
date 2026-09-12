"""Shared HTTP client: on-disk cache, per-host throttle, size cap (05-m4-live-data.md §4).

Frozen rules: cache key = sha256(url) hex under `<cache_dir>/_http/`; `.meta` JSON carries
`{url, fetched_at (ISO UTC), status, source}`; TTL is checked against `fetched_at`
(`ttl_hours=None` means cache forever); `force=True` bypasses the cache read (but the fresh
response still repopulates it); bodies over 25 MB raise `SOURCE_HTTP` with reason "too large".
Throttle: per-host last-request timestamp; sec.gov/data.sec.gov require >= 0.12s spacing,
every other host is unthrottled.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from fathom.errors import Code, FathomError

_MAX_BODY_BYTES = 25 * 1024 * 1024
_THROTTLED_HOSTS = frozenset({"www.sec.gov", "data.sec.gov"})
_THROTTLE_INTERVAL_S = 0.12


class LiveHttp:
    """Cached, throttled HTTP GET for live data sources.

    Tests must always pass `client` (an `httpx.Client` built on `httpx.MockTransport`) and
    fake `clock`/`sleeper` callables — this type is never given a real transport in tests.
    """

    def __init__(
        self,
        *,
        cache_dir: Path,
        user_agent: str,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cache_dir = cache_dir
        self._user_agent = user_agent
        self._client = client if client is not None else httpx.Client(timeout=30.0)
        self._clock = clock
        self._sleeper = sleeper
        self._last_request: dict[str, float] = {}

    def close(self) -> None:
        """Close the underlying `httpx.Client`."""
        self._client.close()

    def get(self, url: str, *, ttl_hours: float | None, source: str, force: bool = False) -> bytes:
        """Fetch `url`, serving from cache when fresh; always returns the raw body bytes."""
        cache_path, meta_path = self._cache_paths(url)
        if not force:
            cached = self._read_cache(cache_path, meta_path, ttl_hours)
            if cached is not None:
                return cached

        self._throttle(urlparse(url).hostname or "")

        try:
            response = self._client.get(
                url,
                headers={"User-Agent": self._user_agent, "Accept-Encoding": "gzip"},
            )
        except httpx.HTTPError as exc:
            raise FathomError(
                Code.SOURCE_HTTP,
                f"{source} request failed",
                {"source": source, "status": 0, "reason": str(exc)},
            ) from exc

        if not (200 <= response.status_code < 300):
            raise FathomError(
                Code.SOURCE_HTTP,
                f"{source} returned status {response.status_code}",
                {
                    "source": source,
                    "status": response.status_code,
                    "reason": response.reason_phrase or "",
                },
            )

        body = response.content
        if len(body) > _MAX_BODY_BYTES:
            raise FathomError(
                Code.SOURCE_HTTP,
                f"{source} response exceeded the size cap",
                {"source": source, "status": response.status_code, "reason": "too large"},
            )

        self._write_cache(
            cache_path, meta_path, body, url=url, status=response.status_code, source=source
        )
        return body

    def _throttle(self, host: str) -> None:
        if host not in _THROTTLED_HOSTS:
            return
        now = self._clock()
        last = self._last_request.get(host)
        if last is not None:
            remaining = _THROTTLE_INTERVAL_S - (now - last)
            if remaining > 0:
                self._sleeper(remaining)
        self._last_request[host] = now

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        base = self._cache_dir / "_http" / digest
        return base, base.parent / f"{base.name}.meta"

    def _read_cache(
        self, cache_path: Path, meta_path: Path, ttl_hours: float | None
    ) -> bytes | None:
        if not cache_path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(meta["fetched_at"])
        except (OSError, ValueError, KeyError):
            return None
        if ttl_hours is not None:
            age_hours = (datetime.now(UTC) - fetched_at).total_seconds() / 3600.0
            if age_hours >= ttl_hours:
                return None
        return cache_path.read_bytes()

    def _write_cache(
        self, cache_path: Path, meta_path: Path, body: bytes, *, url: str, status: int, source: str
    ) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(body)
        meta = {
            "url": url,
            "fetched_at": datetime.now(UTC).isoformat(),
            "status": status,
            "source": source,
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
