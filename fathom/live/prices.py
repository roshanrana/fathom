"""Live daily bars: Yahoo primary, Stooq CSV fallback (05-m4-live-data.md §4).

Frozen rules: Yahoo `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=2y&interval=1d`
(Yahoo symbol = ticker with "." -> "-"); rows with a null close are dropped; a 200 body without
`chart.result[0]` counts as a Yahoo failure. Stooq fallback
`https://stooq.com/q/d/l/?s=<sym>.us&i=d` (`<sym>` = the Yahoo symbol, lower-cased); a body that
does not start with the documented CSV header counts as a Stooq failure. Either failure mode
(`SOURCE_HTTP` from `LiveHttp`, or the malformed-body cases above) triggers the fallback to the
other source; `primary` picks which one is tried first.
"""

from __future__ import annotations

import io
import json
import math
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, cast

import pandas as pd

from fathom.errors import Code, FathomError
from fathom.live.http import LiveHttp

_YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d"
_STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"
_STOOQ_HEADER = "Date,Open,High,Low,Close,Volume"
_BARS_TTL_HOURS = 6.0
_BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
_FLOAT_COLUMNS = ("open", "high", "low", "close", "volume")
_MAX_STOOQ_ROWS = 10_000
_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")
# T-023 attempt 3: a timestamp outside [0, 4102444800] (2100-01-01T00:00:00Z) is dropped before
# ever reaching `datetime.fromtimestamp`, which otherwise raises OSError/OverflowError on
# platform-dependent extreme values (attempt-3 HIGH finding).
_MAX_YAHOO_TIMESTAMP = 4_102_444_800
_MIN_YAHOO_TIMESTAMP = 0

PriceSource = Literal["yahoo", "stooq"]


def _yahoo_symbol(ticker: str) -> str:
    """Yahoo's chart symbol: upper-cased ticker with "." mapped to "-" (e.g. BRK.B -> BRK-B)."""
    return ticker.upper().replace(".", "-")


def _stooq_symbol(ticker: str) -> str:
    """Stooq's bare symbol (without the ".us" suffix the URL template adds)."""
    return _yahoo_symbol(ticker).lower()


class PriceClient:
    """Daily bars for a ticker, from Yahoo with an automatic Stooq fallback."""

    def __init__(self, http: LiveHttp, primary: PriceSource = "yahoo") -> None:
        self._http = http
        self._primary = primary
        self.last_source: str | None = None

    def daily_bars(self, ticker: str) -> pd.DataFrame:
        """Ascending daily bars for `ticker`, trying `primary` first with an automatic fallback.

        Sets `last_source` to whichever source actually served the bars. Raises the fallback
        source's `SOURCE_HTTP` if both sources fail. Raises `UNKNOWN_TICKER` before any request
        if `ticker` does not match the safe identifier pattern (T-019 F3).
        """
        symbol = ticker.upper()
        # T-023 attempt 2 F2: fullmatch (not match+`$`) so a trailing "\n" cannot sneak through —
        # Python's `$` matches end-of-string *or* just before one trailing "\n".
        if not _TICKER_RE.fullmatch(symbol):
            raise FathomError(Code.UNKNOWN_TICKER, f"invalid ticker {symbol!r}", {"ticker": symbol})
        fallback: PriceSource = "stooq" if self._primary == "yahoo" else "yahoo"
        fetchers: dict[PriceSource, Callable[[str], pd.DataFrame]] = {
            "yahoo": self._yahoo,
            "stooq": self._stooq,
        }

        try:
            frame = fetchers[self._primary](symbol)
        except FathomError as exc:
            if exc.code != Code.SOURCE_HTTP:
                raise
            frame = fetchers[fallback](symbol)
            self.last_source = fallback
            return frame
        self.last_source = self._primary
        return frame

    def _yahoo(self, ticker: str) -> pd.DataFrame:
        url = _YAHOO_URL.format(symbol=_yahoo_symbol(ticker))
        body = self._http.get(url, ttl_hours=_BARS_TTL_HOURS, source="yahoo")
        # T-023 attempt 3: the whole parse is I/O-free and has no control flow that should
        # propagate, so any failure (including exception types not anticipated by an enumerated
        # tuple, e.g. the OSError/OverflowError previously reachable via `datetime.fromtimestamp`)
        # becomes a plain source failure rather than an uncaught exception.
        try:
            payload = json.loads(body)
            result = payload["chart"]["result"][0]
            # T-023 attempt 2 F1: `result` may be a truthy non-dict (e.g. an error string); index
            # [0] on a string succeeds via char-indexing, so validate the type explicitly rather
            # than trusting the type-checker-only `cast`.
            if not isinstance(result, dict):
                raise TypeError("yahoo result is not a dict")
            frame = self._bars_from_yahoo(ticker, result)
        except Exception as exc:  # noqa: BLE001 - deliberate whole-body parse guard, see above
            raise _malformed_response_error("yahoo") from exc
        if frame.empty:
            raise _malformed_response_error("yahoo")
        return frame

    def _bars_from_yahoo(self, ticker: str, result: dict[str, object]) -> pd.DataFrame:
        timestamps = cast(list[int], result.get("timestamp") or [])
        indicators = result.get("indicators") or {}
        if not isinstance(indicators, dict):
            raise TypeError("yahoo indicators is not a dict")
        quote_list = indicators.get("quote") or []
        if not isinstance(quote_list, list):
            raise TypeError("yahoo quote is not a list")
        quote = quote_list[0] if quote_list else {}
        if not isinstance(quote, dict):
            raise TypeError("yahoo quote entry is not a dict")
        opens = cast(list[object], quote.get("open") or [])
        highs = cast(list[object], quote.get("high") or [])
        lows = cast(list[object], quote.get("low") or [])
        closes = cast(list[object], quote.get("close") or [])
        volumes = cast(list[object], quote.get("volume") or [])

        rows: list[dict[str, object]] = []
        for i, ts in enumerate(timestamps):
            if _is_out_of_range_yahoo_timestamp(ts):
                continue
            close = closes[i] if i < len(closes) else None
            close_value = _valid_close(close)
            if close_value is None:
                continue
            rows.append(
                {
                    "symbol": ticker,
                    "date": datetime.fromtimestamp(ts, tz=UTC).date(),
                    "open": _safe_float(opens, i),
                    "high": _safe_float(highs, i),
                    "low": _safe_float(lows, i),
                    "close": close_value,
                    "volume": _safe_float(volumes, i),
                }
            )
        return _bars_frame(rows)

    def _stooq(self, ticker: str) -> pd.DataFrame:
        url = _STOOQ_URL.format(symbol=_stooq_symbol(ticker))
        body = self._http.get(url, ttl_hours=_BARS_TTL_HOURS, source="stooq")
        text = body.decode("utf-8", errors="replace")
        if not text.startswith(_STOOQ_HEADER):
            raise FathomError(
                Code.SOURCE_HTTP,
                "stooq response was not a bars CSV",
                {"source": "stooq", "status": 200, "reason": "not a CSV body"},
            )

        try:
            csv_frame = pd.read_csv(io.StringIO(text), nrows=_MAX_STOOQ_ROWS)
        except Exception as exc:  # noqa: BLE001 - whole-body parse guard, see _yahoo above
            raise _malformed_response_error("stooq") from exc

        rows: list[dict[str, object]] = []
        for _, row in csv_frame.iterrows():
            parsed = _parse_stooq_row(ticker, row)
            if parsed is not None:
                rows.append(parsed)

        frame = _bars_frame(rows)
        if frame.empty:
            raise _malformed_response_error("stooq")
        return frame


def _is_out_of_range_yahoo_timestamp(ts: object) -> bool:
    """True only for a *numeric* Yahoo timestamp outside [0, 4102444800] (2100-01-01T00:00:00Z).

    Rejecting these here (T-023 attempt 3) drops just that row before it ever reaches
    `datetime.fromtimestamp`, which otherwise raises `OSError`/`OverflowError` on
    platform-dependent extreme values (e.g. `10**18`, `-1`, or a value just past the bound).
    A non-numeric `ts` (e.g. `None`) is left alone: it still reaches `datetime.fromtimestamp`
    and raises there, which the whole-body guard in `_yahoo()` converts to a source failure —
    preserving the earlier T-019/T-023 behavior for a malformed (not merely out-of-range) shape.

    T-023 attempt 4 LOW: `bool` is excluded from "acceptable" here (treated as out of range,
    same as any other non-numeric shape) rather than silently accepted as 0/1, matching
    `_valid_close`/`_safe_float` elsewhere in this file which already special-case `bool`.
    """
    if isinstance(ts, bool):
        return True
    if not isinstance(ts, int | float):
        return False
    if not math.isfinite(ts):
        return True
    return not (_MIN_YAHOO_TIMESTAMP <= ts <= _MAX_YAHOO_TIMESTAMP)


def _malformed_response_error(source: str) -> FathomError:
    """SOURCE_HTTP for a body that raised while parsing, or parsed into zero valid bars."""
    return FathomError(
        Code.SOURCE_HTTP,
        f"{source} response could not be parsed into valid bars",
        {"source": source, "status": 200, "reason": "malformed response"},
    )


def _valid_close(value: object) -> float | None:
    """A close is usable only if it is a finite, positive number (T-019 F1)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(cast(float, value))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def _safe_float(values: list[object], index: int) -> float:
    """Best-effort float for a Yahoo non-close OHLCV cell; unusable values become NaN."""
    if index >= len(values):
        return float("nan")
    value = values[index]
    if value is None or isinstance(value, bool):
        return float("nan")
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return float("nan")


def _parse_stooq_row(ticker: str, row: pd.Series) -> dict[str, object] | None:
    """Parse one Stooq CSV row; any unparsable cell drops the whole row (T-019 F2)."""
    try:
        close_value = _valid_close(row["Close"])
        if close_value is None:
            return None
        return {
            "symbol": ticker,
            "date": datetime.strptime(str(row["Date"]), "%Y-%m-%d").date(),
            "open": _required_float(row["Open"]),
            "high": _required_float(row["High"]),
            "low": _required_float(row["Low"]),
            "close": close_value,
            "volume": _required_float(row["Volume"]),
        }
    except Exception:  # noqa: BLE001 - whole-body parse guard, see _yahoo above
        return None


def _required_float(value: object) -> float:
    """Strict float conversion for a Stooq cell; raises on anything unparsable."""
    if value is None or isinstance(value, bool):
        raise TypeError("not a valid numeric cell")
    return float(cast(float, value))


def _bars_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build the fixture-schema bars frame: ascending dates, float64 OHLCV columns."""
    frame = pd.DataFrame(rows, columns=_BAR_COLUMNS)
    for column in _FLOAT_COLUMNS:
        frame[column] = frame[column].astype("float64")
    return frame.sort_values("date").reset_index(drop=True)
