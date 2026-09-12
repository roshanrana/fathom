"""XBRL valuation snapshot: market cap, P/E, P/B, dividend yield (05-m4-live-data.md §4).

Frozen formula: shares = latest `dei:EntityCommonStockSharesOutstanding`; EPS TTM = sum of the
four most recent `us-gaap:EarningsPerShareDiluted` entries whose `frame` matches `^CY\\d{4}Q\\d$`;
equity = latest `us-gaap:StockholdersEquity` instant (`frame` `^CY\\d{4}Q\\dI$`); DPS TTM = sum of
the four most recent `us-gaap:CommonStockDividendsPerShareDeclared` quarterly frames (0 if the
concept is absent); market_cap = last_close * shares; pe = last_close / eps_ttm if eps_ttm > 0
else None; pb = market_cap / equity if both are available; dividend_yield = dps_ttm / last_close
* 100. A 404 (`SOURCE_HTTP`) on any concept is caught per-concept and treated as missing data for
the fields that depend on it; malformed fact shapes (empty units, missing frame, non-numeric val)
are skipped rather than raising.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from datetime import date, datetime

from fathom.errors import Code, FathomError
from fathom.live.sec import SecClient

_QUARTERLY_FRAME_RE = re.compile(r"^CY\d{4}Q\d$")
_INSTANT_FRAME_RE = re.compile(r"^CY\d{4}Q\dI$")
_TTM_QUARTER_COUNT = 4
_ROUND_DP = 2
_CIK_RE = re.compile(r"^\d{10}$")

# T-023/T-019 F5: out-of-range facts are treated as missing.
_SHARES_MAX = 1e12
_EQUITY_ABS_MAX = 1e13
_EPS_ABS_MAX = 1e4
_DPS_MAX = 1e3

SNAPSHOT_SOURCE = "SEC XBRL companyconcept (shares, EPS TTM, equity, DPS TTM)"


def _within_shares_bounds(value: float) -> bool:
    return 0.0 < value <= _SHARES_MAX


def _within_equity_bounds(value: float) -> bool:
    return abs(value) <= _EQUITY_ABS_MAX


def _within_eps_bounds(value: float) -> bool:
    return abs(value) <= _EPS_ABS_MAX


def _within_dps_bounds(value: float) -> bool:
    return 0.0 <= value <= _DPS_MAX


def snapshot(
    sec: SecClient, cik: str, last_close: float, quote_time: datetime
) -> dict[str, float | str | None]:
    """Derive market cap, P/E, P/B and dividend yield from XBRL facts and the latest close.

    `quote_time` is accepted for provenance/signature symmetry with the rest of the live
    pipeline; the derivation itself only depends on the facts and `last_close`. Never raises:
    a concept that cannot be fetched (`SOURCE_HTTP`, e.g. 404) leaves the fields that depend on
    it as `None` (dividend TTM instead defaults to 0, per the frozen formula). Raises
    `SOURCE_HTTP` reason "invalid identifier" before any request if `cik` is not a 10-digit
    string (T-019 F3).
    """
    del quote_time
    # T-023 attempt 2 F2: fullmatch (not match+`$`) so a trailing "\n" cannot sneak through —
    # Python's `$` matches end-of-string *or* just before one trailing "\n".
    if not _CIK_RE.fullmatch(cik):
        raise FathomError(
            Code.SOURCE_HTTP,
            "invalid cik supplied to snapshot",
            {"source": "sec", "status": 0, "reason": "invalid identifier"},
        )

    shares_payload = _fetch_concept(sec, cik, "dei", "EntityCommonStockSharesOutstanding")
    shares = _latest_value(_entries(shares_payload), is_valid=_within_shares_bounds)
    eps_ttm = _ttm_sum(
        _entries(_fetch_concept(sec, cik, "us-gaap", "EarningsPerShareDiluted")),
        _QUARTERLY_FRAME_RE,
        is_valid=_within_eps_bounds,
    )
    equity = _latest_value(
        _matching(
            _entries(_fetch_concept(sec, cik, "us-gaap", "StockholdersEquity")),
            _INSTANT_FRAME_RE,
        ),
        is_valid=_within_equity_bounds,
    )
    dps_ttm = _ttm_sum(
        _entries(_fetch_concept(sec, cik, "us-gaap", "CommonStockDividendsPerShareDeclared")),
        _QUARTERLY_FRAME_RE,
        is_valid=_within_dps_bounds,
    )
    if dps_ttm is None:
        dps_ttm = 0.0

    market_cap = last_close * shares if shares is not None else None
    pe = round(last_close / eps_ttm, _ROUND_DP) if eps_ttm is not None and eps_ttm > 0 else None
    pb = (
        round(market_cap / equity, _ROUND_DP)
        if market_cap is not None and equity is not None and equity != 0
        else None
    )
    dividend_yield = round(dps_ttm / last_close * 100, _ROUND_DP) if last_close != 0 else None

    return {
        "market_cap": _finite_or_none(
            round(market_cap, _ROUND_DP) if market_cap is not None else None
        ),
        "pe": _finite_or_none(pe),
        "pb": _finite_or_none(pb),
        "dividend_yield": _finite_or_none(dividend_yield),
        "snapshot_source": SNAPSHOT_SOURCE,
    }


def _finite_or_none(value: float | None) -> float | None:
    """Belt-and-suspenders: never surface a non-finite derived ratio (T-019 F4)."""
    if value is None or not math.isfinite(value):
        return None
    return value


def _fetch_concept(
    sec: SecClient, cik: str, taxonomy: str, concept: str
) -> dict[str, object] | None:
    """Fetch one company-concept payload; `None` when the concept is missing (SOURCE_HTTP)."""
    try:
        return sec.company_concept(cik, taxonomy, concept)
    except FathomError as exc:
        if exc.code == Code.SOURCE_HTTP:
            return None
        raise


def _entries(payload: dict[str, object] | None) -> list[dict[str, object]]:
    """Flatten every unit's fact list, tolerating empty/malformed shapes."""
    if payload is None:
        return []
    units = payload.get("units")
    if not isinstance(units, dict):
        return []
    entries: list[dict[str, object]] = []
    for facts in units.values():
        if isinstance(facts, list):
            entries.extend(fact for fact in facts if isinstance(fact, dict))
    return entries


def _matching(
    entries: list[dict[str, object]], pattern: re.Pattern[str]
) -> list[dict[str, object]]:
    return [
        e for e in entries if isinstance(e.get("frame"), str) and pattern.match(str(e["frame"]))
    ]


def _numeric_val(
    entry: dict[str, object], *, is_valid: Callable[[float], bool] | None = None
) -> float | None:
    # T-023 attempt 3: whole-body guard, same rationale as the Yahoo/Stooq parse helpers in
    # prices.py — this parses an untrusted fact dict, so any failure (not just the exception
    # types anticipated up front) is treated as "this fact is unusable", never propagated.
    try:
        val = entry.get("val")
        if isinstance(val, bool) or not isinstance(val, int | float):
            return None
        value = float(val)
        if not math.isfinite(value):
            return None
        if is_valid is not None and not is_valid(value):
            return None
        return value
    except Exception:  # noqa: BLE001 - whole-body parse guard, see above
        return None


def _end_date(entry: dict[str, object]) -> date | None:
    try:
        raw = entry.get("end")
        if not isinstance(raw, str):
            return None
        return date.fromisoformat(raw)
    except Exception:  # noqa: BLE001 - whole-body parse guard, see _numeric_val above
        return None


def _sorted_by_end_desc(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    dated = [(entry, end) for entry in entries if (end := _end_date(entry)) is not None]
    dated.sort(key=lambda pair: pair[1], reverse=True)
    return [entry for entry, _ in dated]


def _latest_value(
    entries: list[dict[str, object]], *, is_valid: Callable[[float], bool] | None = None
) -> float | None:
    for entry in _sorted_by_end_desc(entries):
        val = _numeric_val(entry, is_valid=is_valid)
        if val is not None:
            return val
    return None


def _ttm_sum(
    entries: list[dict[str, object]],
    pattern: re.Pattern[str],
    *,
    is_valid: Callable[[float], bool] | None = None,
) -> float | None:
    """Sum of the 4 most recent numeric entries matching `pattern`; `None` if none qualify.

    An entry failing `is_valid` (out-of-range magnitude, T-019 F5) is treated as missing and
    skipped, same as a non-numeric `val`.
    """
    values: list[float] = []
    for entry in _sorted_by_end_desc(_matching(entries, pattern)):
        val = _numeric_val(entry, is_valid=is_valid)
        if val is None:
            continue
        values.append(val)
        if len(values) == _TTM_QUARTER_COUNT:
            break
    return sum(values) if values else None
