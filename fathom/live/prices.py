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
        source's `SOURCE_HTTP` if both sources fail.
        """
        symbol = ticker.upper()
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
        try:
            payload = json.loads(body)
            result = cast(dict[str, object], payload["chart"]["result"][0])
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise FathomError(
                Code.SOURCE_HTTP,
                "yahoo response missing chart.result",
                {"source": "yahoo", "status": 200, "reason": "malformed body"},
            ) from exc
        return self._bars_from_yahoo(ticker, result)

    def _bars_from_yahoo(self, ticker: str, result: dict[str, object]) -> pd.DataFrame:
        timestamps = cast(list[int], result.get("timestamp") or [])
        indicators = cast(dict[str, object], result.get("indicators") or {})
        quote_list = cast(list[dict[str, object]], indicators.get("quote") or [])
        quote = quote_list[0] if quote_list else {}
        opens = cast(list[object], quote.get("open") or [])
        highs = cast(list[object], quote.get("high") or [])
        lows = cast(list[object], quote.get("low") or [])
        closes = cast(list[object], quote.get("close") or [])
        volumes = cast(list[object], quote.get("volume") or [])

        rows: list[dict[str, object]] = []
        for i, ts in enumerate(timestamps):
            close = closes[i] if i < len(closes) else None
            if close is None:
                continue
            rows.append(
                {
                    "symbol": ticker,
                    "date": datetime.fromtimestamp(ts, tz=UTC).date(),
                    "open": _safe_float(opens, i),
                    "high": _safe_float(highs, i),
                    "low": _safe_float(lows, i),
                    "close": float(cast(float, close)),
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

        rows: list[dict[str, object]] = []
        csv_frame = pd.read_csv(io.StringIO(text))
        for _, row in csv_frame.iterrows():
            close = row["Close"]
            if pd.isna(close):
                continue
            rows.append(
                {
                    "symbol": ticker,
                    "date": datetime.strptime(str(row["Date"]), "%Y-%m-%d").date(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(close),
                    "volume": float(row["Volume"]),
                }
            )
        return _bars_frame(rows)


def _safe_float(values: list[object], index: int) -> float:
    if index >= len(values) or values[index] is None:
        return float("nan")
    return float(cast(float, values[index]))


def _bars_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build the fixture-schema bars frame: ascending dates, float64 OHLCV columns."""
    frame = pd.DataFrame(rows, columns=_BAR_COLUMNS)
    for column in _FLOAT_COLUMNS:
        frame[column] = frame[column].astype("float64")
    return frame.sort_values("date").reset_index(drop=True)
