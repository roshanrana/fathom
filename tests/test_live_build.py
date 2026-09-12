"""Tests for fathom.live.build.materialize (RTM: FR-020, FR-021, FR-022, FR-023, FR-024, NFR-012).

All tests use `httpx.MockTransport`; no real network call is ever made (NFR-013).
"""

from __future__ import annotations

import copy
import json
import random
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd
import pytest

from fathom.ask import ask
from fathom.briefing import brief
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.filings import filings_for, sections_for
from fathom.live.build import LiveManifest, materialize
from fathom.live.http import LiveHttp
from fathom.quotes import quote_card

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "live"

_COMPANY_TICKERS = (FIXTURES / "company_tickers.json").read_bytes()
_AAPL_SUBMISSIONS = (FIXTURES / "aapl_submissions.json").read_bytes()
_AAPL_10Q = (FIXTURES / "aapl_10q.htm").read_bytes()
_AAPL_10K = (FIXTURES / "aapl_10k.htm").read_bytes()
_YAHOO_CHART = (FIXTURES / "yahoo_chart_aapl.json").read_bytes()
_SHARES = (FIXTURES / "aapl_shares_outstanding.json").read_bytes()
_EPS = (FIXTURES / "aapl_eps_diluted.json").read_bytes()
_EQUITY = (FIXTURES / "aapl_stockholders_equity.json").read_bytes()
_DIVIDENDS = (FIXTURES / "aapl_dividends_per_share.json").read_bytes()

_10Q_DOC_SUFFIXES = (
    "/aapl-20260627.htm",
    "/aapl-20260328.htm",
    "/aapl-20251227.htm",
    "/aapl-20250628.htm",
)
_10K_DOC_SUFFIX = "/aapl-20250927.htm"

_CONCEPT_BODIES = {
    "EntityCommonStockSharesOutstanding": _SHARES,
    "EarningsPerShareDiluted": _EPS,
    "StockholdersEquity": _EQUITY,
    "CommonStockDividendsPerShareDeclared": _DIVIDENDS,
}

_EXPECTED_10K_SECTIONS = ["10-K:1", "10-K:1A", "10-K:1C", "10-K:3", "10-K:7", "10-K:7A", "10-K:9A"]
_EXPECTED_10Q_SECTIONS = ["10-Q:I.2", "10-Q:I.3", "10-Q:I.4", "10-Q:II.1", "10-Q:II.1A"]


def _default_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == "https://www.sec.gov/files/company_tickers.json":
        return httpx.Response(200, content=_COMPANY_TICKERS)
    if url == "https://data.sec.gov/submissions/CIK0000320193.json":
        return httpx.Response(200, content=_AAPL_SUBMISSIONS)
    if url.endswith(_10K_DOC_SUFFIX):
        return httpx.Response(200, content=_AAPL_10K)
    if url.endswith(_10Q_DOC_SUFFIXES):
        return httpx.Response(200, content=_AAPL_10Q)
    if url.startswith("https://query1.finance.yahoo.com/v8/finance/chart/"):
        return httpx.Response(200, content=_YAHOO_CHART)
    if "companyconcept" in url:
        for concept, body in _CONCEPT_BODIES.items():
            if url.endswith(f"/{concept}.json"):
                return httpx.Response(200, content=body)
        return httpx.Response(404)
    return httpx.Response(404)


def _make_http(
    tmp_path: Path, handler: object = _default_handler
) -> tuple[LiveHttp, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)  # type: ignore[operator]

    client = httpx.Client(transport=httpx.MockTransport(wrapped))
    http = LiveHttp(
        cache_dir=tmp_path / "live", user_agent="Fathom/0.1.0 (t@example.com)", client=client
    )
    return http, calls


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    fields: dict[str, object] = {
        "data_source": "live",
        "sec_contact": "t@example.com",
        "live_cache_dir": tmp_path / "live",
        "audit_path": tmp_path / "audit.jsonl",
    }
    fields.update(overrides)
    return Settings(**fields)  # type: ignore[arg-type]


def _clock_at(when: datetime) -> object:
    return lambda: when


# --- AC1: schema + manifest + TTL + force -----------------------------------------------------


def test_fr024_materialize_writes_four_fixture_shaped_tables_and_manifest(tmp_path: Path) -> None:
    http, calls = _make_http(tmp_path)
    settings = _settings(tmp_path)
    now = datetime(2026, 9, 1, tzinfo=UTC)

    manifest = materialize("aapl", settings, http=http, clock=_clock_at(now))

    assert manifest.ticker == "AAPL"
    assert manifest.cik == "0000320193"
    assert manifest.fetched_at == now
    live_dir = Path(manifest.data_dir)
    assert live_dir == tmp_path / "live" / "AAPL"

    filings_frame = pd.read_parquet(live_dir / "filings.parquet")
    assert list(filings_frame.columns) == [
        "ticker",
        "cik",
        "company_name",
        "form",
        "filing_date",
        "accession",
        "text",
        "n_chars",
    ]
    assert len(filings_frame) == 5
    assert set(filings_frame["ticker"]) == {"AAPL"}

    bars_frame = pd.read_parquet(live_dir / "bars.parquet")
    assert list(bars_frame.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert not bars_frame.empty

    quotes_frame = pd.read_parquet(live_dir / "quotes.parquet")
    assert list(quotes_frame.columns) == [
        "symbol",
        "quote_time",
        "last_price",
        "pre_close",
        "change_percent",
        "volume",
        "market_cap",
        "pe",
        "pb",
        "dividend_yield",
    ]
    assert len(quotes_frame) == 1

    companies_frame = pd.read_parquet(live_dir / "companies.parquet")
    assert list(companies_frame.columns) == [
        "ticker",
        "long_name",
        "full_exchange_name",
        "sector",
        "industry",
        "website",
    ]
    row = companies_frame.iloc[0]
    assert row["long_name"] == "Apple Inc."
    assert row["website"] == ""

    manifest_on_disk = LiveManifest.model_validate_json(
        (live_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest_on_disk == manifest

    ten_k = next(f for f in manifest.filings if f.form == "10-K")
    ten_qs = [f for f in manifest.filings if f.form == "10-Q"]
    assert len(ten_qs) == 4
    assert manifest.sections_coverage[ten_k.accession] == _EXPECTED_10K_SECTIONS
    for filing in ten_qs:
        assert manifest.sections_coverage[filing.accession] == _EXPECTED_10Q_SECTIONS

    assert manifest.bars_source.startswith(("yahoo via", "stooq via"))
    assert manifest.bars_source.endswith(".cache/live/AAPL/bars.parquet")
    assert "SEC XBRL companyconcept" in manifest.snapshot_source
    assert "close" in manifest.snapshot_source

    assert len(calls) > 0


def test_fr024_second_call_within_ttl_performs_zero_http_calls(tmp_path: Path) -> None:
    http, calls = _make_http(tmp_path)
    settings = _settings(tmp_path)
    now = datetime(2026, 9, 1, tzinfo=UTC)

    materialize("AAPL", settings, http=http, clock=_clock_at(now))
    first_call_count = len(calls)
    assert first_call_count > 0

    second = materialize("AAPL", settings, http=http, clock=_clock_at(now))

    assert len(calls) == first_call_count, "a fresh manifest must short-circuit before any HTTP"
    assert second.fetched_at == now


def test_fr024_force_true_recomputes_and_bumps_fetched_at(tmp_path: Path) -> None:
    http, calls = _make_http(tmp_path)
    settings = _settings(tmp_path)
    first_time = datetime(2026, 9, 1, tzinfo=UTC)
    second_time = datetime(2026, 9, 1, 0, 5, tzinfo=UTC)

    first = materialize("AAPL", settings, http=http, clock=_clock_at(first_time))
    second = materialize("AAPL", settings, force=True, http=http, clock=_clock_at(second_time))

    assert first.fetched_at == first_time
    assert second.fetched_at == second_time
    assert second.fetched_at > first.fetched_at


def test_fr024_ttl_expiry_triggers_refetch_without_force(tmp_path: Path) -> None:
    http, _ = _make_http(tmp_path)
    settings = _settings(tmp_path, live_ttl_hours=1.0)
    first_time = datetime(2026, 9, 1, tzinfo=UTC)
    later_time = datetime(2026, 9, 1, 2, 0, tzinfo=UTC)  # 2h later, past the 1h TTL

    materialize("AAPL", settings, http=http, clock=_clock_at(first_time))
    second = materialize("AAPL", settings, http=http, clock=_clock_at(later_time))

    assert second.fetched_at == later_time


def test_fr020_materialize_missing_contact_raises_source_config(tmp_path: Path) -> None:
    settings = _settings(tmp_path, sec_contact=None)

    with pytest.raises(FathomError) as excinfo:
        materialize("AAPL", settings)

    assert excinfo.value.code == Code.SOURCE_CONFIG
    assert "FATHOM_SEC_CONTACT" in excinfo.value.message


def test_fr022_materialize_empty_bars_raises_source_http(tmp_path: Path) -> None:
    """`PriceClient` itself now treats a 200-but-empty chart as a malformed response.

    Both Yahoo (empty) and the Stooq fallback (404, unmocked) fail here, so `daily_bars`
    raises `SOURCE_HTTP`; `materialize`'s own `bars.empty` guard is a defensive no-op given
    that `PriceClient` contract (it never returns an empty frame successfully).
    """
    empty_chart = json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "timestamp": [],
                        "indicators": {
                            "quote": [
                                {"open": [], "high": [], "low": [], "close": [], "volume": []}
                            ]
                        },
                    }
                ]
            }
        }
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://query1.finance.yahoo.com/v8/finance/chart/"):
            return httpx.Response(200, content=empty_chart)
        return _default_handler(request)

    http, _ = _make_http(tmp_path, handler)
    settings = _settings(tmp_path)

    with pytest.raises(FathomError) as excinfo:
        materialize("AAPL", settings, http=http)

    assert excinfo.value.code == Code.SOURCE_HTTP


# --- AC3: end-to-end offline on the materialized cache -----------------------------------------


def test_fr020_ac3_end_to_end_offline_on_materialized_cache(tmp_path: Path) -> None:
    http, _ = _make_http(tmp_path)
    settings = _settings(tmp_path, llm_provider="offline")
    manifest = materialize("AAPL", settings, http=http)
    live_dir = Path(manifest.data_dir)

    card = quote_card("AAPL", live_dir)
    assert card.ticker == "AAPL"
    assert card.source.endswith(".cache/live/AAPL/bars.parquet")
    assert card.snapshot_source is not None
    assert "SEC XBRL companyconcept" in card.snapshot_source
    assert card.snapshot_source.endswith("close")

    filings = filings_for("AAPL", live_dir)
    assert len(filings) == 5

    ten_k = next(f for f in filings if f.form == "10-K")
    sections = sections_for(ten_k.accession, live_dir)
    assert {s.section_id for s in sections} == set(_EXPECTED_10K_SECTIONS)

    briefing = brief("AAPL", settings, provider=None)
    assert briefing.ticker == "AAPL"
    assert len(briefing.filings_used) == 3

    answer = ask("AAPL", "What are the main risk factors?", settings, provider=None)
    assert answer.ticker == "AAPL"


# --- AC8 (attempt 2): a non-fixture ticker (NFLX) succeeds end to end in live mode -------------

_NFLX_CIK = "0001065280"


def _nflx_handler(request: httpx.Request) -> httpx.Response:
    """Like `_default_handler`, but the ticker map also resolves NFLX (absent from `UNIVERSE`).

    NFLX's submissions/documents/facts/bars are served from the same AAPL fixtures (the SEC
    endpoints are matched by URL suffix, not by CIK/ticker), which is enough to exercise the
    non-fixture-universe code path end to end without a second full fixture set.
    """
    url = str(request.url)
    if url == "https://www.sec.gov/files/company_tickers.json":
        tickers = json.loads(_COMPANY_TICKERS.decode())
        tickers["5"] = {"cik_str": 1065280, "ticker": "NFLX", "title": "Netflix, Inc."}
        return httpx.Response(200, content=json.dumps(tickers).encode())
    if url == f"https://data.sec.gov/submissions/CIK{_NFLX_CIK}.json":
        return httpx.Response(200, content=_AAPL_SUBMISSIONS)
    return _default_handler(request)


def test_fr020_ac8_materialize_nflx_non_universe_ticker_succeeds(tmp_path: Path) -> None:
    http, _ = _make_http(tmp_path, _nflx_handler)
    settings = _settings(tmp_path, llm_provider="offline")

    manifest = materialize("NFLX", settings, http=http)

    assert manifest.ticker == "NFLX"
    assert manifest.cik == _NFLX_CIK
    live_dir = Path(manifest.data_dir)
    assert live_dir == tmp_path / "live" / "NFLX"

    card = quote_card("NFLX", live_dir)
    assert card.ticker == "NFLX"

    filings = filings_for("NFLX", live_dir)
    assert len(filings) == 5

    briefing = brief("NFLX", settings, provider=None)
    assert briefing.ticker == "NFLX"

    answer = ask("NFLX", "What are the main risk factors?", settings, provider=None)
    assert answer.ticker == "NFLX"


def test_fr020_ac8_fixture_mode_nflx_still_raises_unknown_ticker(tmp_path: Path) -> None:
    """A fixture-mode call with NFLX still raises `UNKNOWN_TICKER` (fixture mode unchanged)."""
    from fathom.data import require_ticker

    settings = _settings(tmp_path, data_source="fixture")
    with pytest.raises(FathomError) as excinfo:
        require_ticker("NFLX", settings)
    assert excinfo.value.code == Code.UNKNOWN_TICKER


def test_fr020_ac8_materialize_path_traversal_rejected_before_any_path_built(
    tmp_path: Path,
) -> None:
    """`materialize("../x", ...)` raises before the cache root is even created."""
    settings = _settings(tmp_path)

    with pytest.raises(FathomError) as excinfo:
        materialize("../x", settings)

    assert excinfo.value.code == Code.UNKNOWN_TICKER
    assert not (tmp_path / "live").exists()


# --- NFR-012: cold-materialize elapsed time (informational, not gated) -------------------------


def test_nfr012_cold_materialize_elapsed_time_is_recorded(tmp_path: Path) -> None:
    import time

    http, _ = _make_http(tmp_path)
    settings = _settings(tmp_path)

    start = time.perf_counter()
    materialize("AAPL", settings, http=http)
    elapsed = time.perf_counter() - start

    # Informational only (NFR-012 measures real cold starts); a mocked call is not gated on a
    # tight bound, only sanity-checked against the 30s live budget so a runaway loop would fail.
    assert elapsed < 30.0


# --- Structural fuzz (T-024 attempt-3 AC2): mutate the *parsed* structure end to end -----------

_STRUCTURAL_REPLACEMENTS: list[object] = [{}, [], None, "x", 0, True, [1], {"a": 1}]


def _collect_paths(node: object, prefix: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    """Every path (including the empty root path) reachable by dict-key/list-index steps."""
    paths = [prefix]
    if isinstance(node, dict):
        for key, value in node.items():
            paths.extend(_collect_paths(value, prefix + (key,)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            paths.extend(_collect_paths(value, prefix + (index,)))
    return paths


def _structural_mutate(data: object, rng: random.Random) -> object:
    """Deep-copy `data` then replace (or, for a dict key, delete) one random node at any depth."""
    mutated = copy.deepcopy(data)
    path = rng.choice(_collect_paths(mutated))
    if not path:
        return rng.choice(_STRUCTURAL_REPLACEMENTS)
    parent: object = mutated
    for key in path[:-1]:
        parent = parent[key]  # type: ignore[index]
    last = path[-1]
    if isinstance(parent, dict) and rng.random() < 0.3:
        del parent[last]
    else:
        parent[last] = rng.choice(_STRUCTURAL_REPLACEMENTS)  # type: ignore[index]
    return mutated


def test_fr024_structural_fuzz_materialize_mutated_payloads_raise_only_fathom_error(
    tmp_path: Path,
) -> None:
    """Structural (parsed-node) fuzz through the full `materialize()` pipeline, 300 iterations.

    Same mutation model as the sec.py-level structural fuzz in `test_live_sec.py` (a random
    node at any depth in the ticker map / submissions / one of the four XBRL concept files / the
    Yahoo chart becomes `{}`/`[]`/`None`/`"x"`/`0`/`True`/`[1]`/`{"a": 1}`, or a dict key is
    deleted, then the structure is re-serialised so the body stays valid JSON), driven end to
    end through `materialize()`. Every iteration must either raise `FathomError` or return a
    valid `LiveManifest` — and, per this task's extra invariant, a raise must never leave a
    partial `<live_cache_dir>/AAPL/` directory behind (T-024 attempt-2 confirmed a bare `KeyError`
    reachable this way left zero partial directories only because the crash preceded
    `live_dir.mkdir`; this test guards that the *fixed* code keeps that property under the wider
    structural-mutation net, not just for the one field attempt-2 found).
    """
    rng = random.Random(24024)
    tickers = json.loads(_COMPANY_TICKERS)
    submissions = json.loads(_AAPL_SUBMISSIONS)
    chart = json.loads(_YAHOO_CHART)
    concepts = {name: json.loads(body) for name, body in _CONCEPT_BODIES.items()}
    concept_names = list(concepts)
    targets = ["tickers", "submissions", "yahoo", *concept_names]

    for i in range(300):
        target = targets[i % len(targets)]
        mutated_tickers = _structural_mutate(tickers, rng) if target == "tickers" else tickers
        mutated_submissions = (
            _structural_mutate(submissions, rng) if target == "submissions" else submissions
        )
        mutated_chart = _structural_mutate(chart, rng) if target == "yahoo" else chart
        mutated_concepts = dict(concepts)
        if target in concept_names:
            mutated_concepts[target] = _structural_mutate(concepts[target], rng)

        def handler(
            request: httpx.Request,
            mt: object = mutated_tickers,
            ms: object = mutated_submissions,
            mch: object = mutated_chart,
            mc: dict[str, object] = mutated_concepts,
        ) -> httpx.Response:
            url = str(request.url)
            if url == "https://www.sec.gov/files/company_tickers.json":
                return httpx.Response(200, content=json.dumps(mt).encode())
            if url == "https://data.sec.gov/submissions/CIK0000320193.json":
                return httpx.Response(200, content=json.dumps(ms).encode())
            if url.endswith(_10K_DOC_SUFFIX) or url.endswith(_10Q_DOC_SUFFIXES):
                return _default_handler(request)
            if url.startswith("https://query1.finance.yahoo.com/v8/finance/chart/"):
                return httpx.Response(200, content=json.dumps(mch).encode())
            if "companyconcept" in url:
                for concept, body in mc.items():
                    if url.endswith(f"/{concept}.json"):
                        return httpx.Response(200, content=json.dumps(body).encode())
                return httpx.Response(404)
            return httpx.Response(404)

        iter_root = tmp_path / f"struct{i}"
        client = httpx.Client(transport=httpx.MockTransport(handler))
        http = LiveHttp(
            cache_dir=iter_root / "live",
            user_agent="Fathom/0.1.0 (t@example.com)",
            client=client,
            sleeper=lambda _seconds: None,  # no real sleep: the per-host throttle is irrelevant
        )
        settings = _settings(iter_root)
        live_dir = iter_root / "live" / "AAPL"

        try:
            manifest = materialize("AAPL", settings, http=http)
            assert manifest.ticker == "AAPL"
            assert live_dir.exists()
        except FathomError:
            assert not live_dir.exists(), "a raise must never leave a partial cache directory"
