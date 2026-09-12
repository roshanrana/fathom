"""Tests for fathom.live.sec (RTM: FR-021, FR-025, NFR-013)."""

from __future__ import annotations

import copy
import json
import random
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from fathom import __version__
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.filings import parse_sections, period_end
from fathom.live.facts import snapshot as compute_snapshot
from fathom.live.http import LiveHttp
from fathom.live.prices import PriceClient
from fathom.live.sec import SecClient, SecCompany, SecFiling, html_to_text

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "live"

_COMPANY_TICKERS = (FIXTURES / "company_tickers.json").read_bytes()
_AAPL_SUBMISSIONS = (FIXTURES / "aapl_submissions.json").read_bytes()
_AAPL_10Q = (FIXTURES / "aapl_10q.htm").read_bytes()
_AAPL_10K = (FIXTURES / "aapl_10k.htm").read_bytes()

_BRK_B_CIK = "0001067983"
_BRK_B_SUBMISSIONS = (
    b'{"name": "Berkshire Hathaway Inc", "exchanges": ["NYSE"], '
    b'"sicDescription": "Fire, Marine & Casualty Insurance", "fiscalYearEnd": "1231", '
    b'"filings": {"recent": {"form": [], "filingDate": [], "reportDate": [], '
    b'"accessionNumber": [], "primaryDocument": []}, "files": []}}'
)


def _default_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == "https://www.sec.gov/files/company_tickers.json":
        return httpx.Response(200, content=_COMPANY_TICKERS)
    if url == "https://data.sec.gov/submissions/CIK0000320193.json":
        return httpx.Response(200, content=_AAPL_SUBMISSIONS)
    if url == f"https://data.sec.gov/submissions/CIK{_BRK_B_CIK}.json":
        return httpx.Response(200, content=_BRK_B_SUBMISSIONS)
    if url.endswith("/aapl-20260627.htm"):
        return httpx.Response(200, content=_AAPL_10Q)
    if url.endswith("/aapl-20250927.htm"):
        return httpx.Response(200, content=_AAPL_10K)
    return httpx.Response(404)


def _make_client(
    tmp_path: Path,
) -> tuple[SecClient, httpx.MockTransport, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _default_handler(request)

    transport = httpx.MockTransport(wrapped)
    client = httpx.Client(transport=transport)
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    return SecClient(http=http, contact="t@example.com"), transport, calls


def test_nfr013_transport_is_a_mock_transport(tmp_path: Path) -> None:
    sec, transport, _ = _make_client(tmp_path)

    assert isinstance(transport, httpx.MockTransport)
    # SecClient never touches a real transport; this is the only transport it can reach.
    assert sec is not None


def test_fr021_lookup_resolves_ticker_to_sec_company(tmp_path: Path) -> None:
    sec, _, _ = _make_client(tmp_path)

    company = sec.lookup("aapl")

    assert company.ticker == "AAPL"
    assert company.cik == "0000320193"
    assert company.name == "Apple Inc."
    assert company.exchange == "Nasdaq"
    assert company.sic_description == "Electronic Computers"
    assert company.fiscal_year_end == "0926"


def test_fr021_lookup_unknown_ticker_raises_unknown_ticker(tmp_path: Path) -> None:
    sec, _, _ = _make_client(tmp_path)

    with pytest.raises(FathomError) as excinfo:
        sec.lookup("ZZZZZ")

    assert excinfo.value.code == Code.UNKNOWN_TICKER


@pytest.mark.parametrize("raw", ["BRK.B", "BRK-B", "brk.b", "brk-b"])
def test_fr021_lookup_normalises_brk_b_variants(tmp_path: Path, raw: str) -> None:
    sec, _, _ = _make_client(tmp_path)

    company = sec.lookup(raw)

    assert company.ticker == "BRK-B"
    assert company.cik == _BRK_B_CIK
    assert company.name == "Berkshire Hathaway Inc"


def test_fr021_filings_newest_first_excludes_amendment_caps_at_five(tmp_path: Path) -> None:
    sec, _, _ = _make_client(tmp_path)

    filings = sec.filings("0000320193")

    assert [f.form for f in filings] == ["10-Q", "10-Q", "10-Q", "10-K", "10-Q"]
    assert [f.accession for f in filings] == [
        "0000320193-26-000020",
        "0000320193-26-000013",
        "0000320193-26-000006",
        "0000320193-25-000079",
        "0000320193-25-000073",
    ]
    assert all("10-K/A" != f.form for f in filings)
    dates = [f.filing_date for f in filings]
    assert dates == sorted(dates, reverse=True)
    assert len(filings) <= 5

    tenk = next(f for f in filings if f.form == "10-K")
    assert tenk.url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
    )


def test_fr021_html_to_text_10q_yields_required_canonical_ids(tmp_path: Path) -> None:
    text = html_to_text(_AAPL_10Q.decode("utf-8"))

    sections = {s.section_id for s in parse_sections(text, "10-Q")}
    for required in ("10-Q:I.2", "10-Q:I.3", "10-Q:I.4", "10-Q:II.1", "10-Q:II.1A"):
        assert required in sections
    assert "<" not in text
    assert period_end(text) is not None


def test_fr021_html_to_text_10k_yields_required_canonical_ids_with_min_body(tmp_path: Path) -> None:
    text = html_to_text(_AAPL_10K.decode("utf-8"))

    sections = {s.section_id: s for s in parse_sections(text, "10-K")}
    assert len(sections["10-K:1A"].text) >= 2000
    assert len(sections["10-K:7"].text) >= 2000
    assert "<" not in text
    assert period_end(text) is not None


def test_fr021_html_to_text_unescapes_entities() -> None:
    text = html_to_text("<p>Risk &amp; Uncertainty</p>")

    assert "&amp;" not in text
    assert "Risk & Uncertainty" in text


def test_fr025_document_text_caches_forever_zero_transport_calls_second_time(
    tmp_path: Path,
) -> None:
    sec, _, calls = _make_client(tmp_path)
    filing = SecFiling(
        cik="0000320193",
        accession="0000320193-26-000020",
        form="10-Q",
        filing_date=date(2026, 7, 31),
        report_date=None,
        primary_document="aapl-20260627.htm",
        url="https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm",
    )

    before = len(calls)
    first = sec.document_text(filing)
    after_first = len(calls)
    second = sec.document_text(filing)
    after_second = len(calls)

    assert first == second
    assert after_first == before + 1
    assert after_second == after_first


def test_fr025_user_agent_matches_version_and_contact(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("user-agent", ""))
        return _default_handler(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(
        cache_dir=tmp_path, user_agent=f"Fathom/{__version__} (t@example.com)", client=client
    )
    sec = SecClient(http=http, contact="t@example.com")

    sec.lookup("aapl")

    assert seen
    assert all(ua == f"Fathom/{__version__} (t@example.com)" for ua in seen)


def test_fr025_from_settings_without_contact_raises_source_config() -> None:
    settings = Settings.from_env({"FATHOM_DATA_SOURCE": "live"})

    with pytest.raises(FathomError) as excinfo:
        SecClient.from_settings(settings)

    assert excinfo.value.code == Code.SOURCE_CONFIG
    assert excinfo.value.details["var"] == "FATHOM_SEC_CONTACT"


def test_fr025_from_settings_builds_client_with_injected_http(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {"FATHOM_DATA_SOURCE": "live", "FATHOM_SEC_CONTACT": "ops@example.com"}
    )
    client = httpx.Client(transport=httpx.MockTransport(_default_handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="unused", client=client)

    sec = SecClient.from_settings(settings, http=http)
    company = sec.lookup("aapl")

    assert company.ticker == "AAPL"


def test_fr021_filings_uses_older_pages_when_recent_has_too_few_qualifying(
    tmp_path: Path,
) -> None:
    recent = {
        "form": ["4", "8-K"],
        "filingDate": ["2026-09-01", "2026-08-15"],
        "reportDate": ["", ""],
        "accessionNumber": ["0000000000-26-000001", "0000000000-26-000002"],
        "primaryDocument": ["form4.xml", "form8k.htm"],
    }
    older_page = {
        "form": ["10-Q", "10-K"],
        "filingDate": ["2026-05-01", "2026-02-01"],
        "reportDate": ["2026-03-31", "2025-12-31"],
        "accessionNumber": ["0000000000-26-000003", "0000000000-26-000004"],
        "primaryDocument": ["q.htm", "k.htm"],
    }
    submissions = {
        "name": "Sparse Filer Inc",
        "exchanges": ["Nasdaq"],
        "sicDescription": "Testing",
        "fiscalYearEnd": "1231",
        "filings": {
            "recent": recent,
            "files": [{"name": "CIK0000000000-submissions-001.json"}],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://data.sec.gov/submissions/CIK0000000000.json":
            return httpx.Response(200, content=json.dumps(submissions).encode())
        if url == "https://data.sec.gov/submissions/CIK0000000000-submissions-001.json":
            return httpx.Response(200, content=json.dumps(older_page).encode())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    filings = sec.filings("0000000000")

    assert [f.form for f in filings] == ["10-Q", "10-K"]
    assert {f.accession for f in filings} == {
        "0000000000-26-000003",
        "0000000000-26-000004",
    }


def test_fr021_filings_raises_source_empty_when_no_qualifying_filings(tmp_path: Path) -> None:
    submissions = {
        "name": "No Filings Inc",
        "exchanges": [],
        "sicDescription": None,
        "fiscalYearEnd": None,
        "filings": {
            "recent": {
                "form": ["4"],
                "filingDate": ["2026-09-01"],
                "reportDate": [""],
                "accessionNumber": ["0000000001-26-000001"],
                "primaryDocument": ["form4.xml"],
            },
            "files": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://data.sec.gov/submissions/CIK0000000001.json":
            return httpx.Response(200, content=json.dumps(submissions).encode())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.filings("0000000001")

    assert excinfo.value.code == Code.SOURCE_EMPTY


def test_fr021_filings_rejects_invalid_accession_number(tmp_path: Path) -> None:
    submissions = {
        "name": "Tampered Filer Inc",
        "exchanges": [],
        "sicDescription": None,
        "fiscalYearEnd": None,
        "filings": {
            "recent": {
                "form": ["10-K"],
                "filingDate": ["2026-09-01"],
                "reportDate": [""],
                "accessionNumber": ["../../etc"],
                "primaryDocument": ["k.htm"],
            },
            "files": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://data.sec.gov/submissions/CIK0000000002.json":
            return httpx.Response(200, content=json.dumps(submissions).encode())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.filings("0000000002")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "invalid edgar field"
    assert "../../etc" not in err.message
    assert "../../etc" not in str(err.details)


def test_fr021_filings_rejects_invalid_primary_document(tmp_path: Path) -> None:
    submissions = {
        "name": "Tampered Filer Inc",
        "exchanges": [],
        "sicDescription": None,
        "fiscalYearEnd": None,
        "filings": {
            "recent": {
                "form": ["10-K"],
                "filingDate": ["2026-09-01"],
                "reportDate": [""],
                "accessionNumber": ["0000000003-26-000001"],
                "primaryDocument": ["../x.htm"],
            },
            "files": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://data.sec.gov/submissions/CIK0000000003.json":
            return httpx.Response(200, content=json.dumps(submissions).encode())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.filings("0000000003")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "invalid edgar field"
    assert "../x.htm" not in err.message
    assert "../x.htm" not in str(err.details)


def test_fr021_filings_rejects_invalid_older_page_name(tmp_path: Path) -> None:
    submissions = {
        "name": "Sparse Tampered Filer Inc",
        "exchanges": [],
        "sicDescription": None,
        "fiscalYearEnd": None,
        "filings": {
            "recent": {
                "form": ["4"],
                "filingDate": ["2026-09-01"],
                "reportDate": [""],
                "accessionNumber": ["0000000004-26-000001"],
                "primaryDocument": ["form4.xml"],
            },
            "files": [{"name": "../../etc/passwd"}],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://data.sec.gov/submissions/CIK0000000004.json":
            return httpx.Response(200, content=json.dumps(submissions).encode())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.filings("0000000004")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "invalid edgar field"
    assert "../../etc/passwd" not in err.message
    assert "../../etc/passwd" not in str(err.details)


def test_fr021_company_concept_returns_parsed_json(tmp_path: Path) -> None:
    concept_body = b'{"units": {"USD": [{"val": 1, "end": "2026-06-30"}]}}'

    def handler(request: httpx.Request) -> httpx.Response:
        if "companyconcept" in str(request.url):
            return httpx.Response(200, content=concept_body)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    result = sec.company_concept("0000320193", "us-gaap", "EarningsPerShareDiluted")

    assert result["units"]["USD"][0]["val"] == 1


@pytest.mark.parametrize(
    "body",
    [b'"str"', b"[]", b"null", b"not json"],
    ids=["json-string", "json-list", "json-null", "non-json"],
)
def test_fr023_company_concept_malformed_body_raises_source_http_malformed(
    tmp_path: Path, body: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.company_concept("0000320193", "us-gaap", "EarningsPerShareDiluted")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "malformed response"
    assert body.decode(errors="replace") not in str(err.details)
    assert body.decode(errors="replace") not in err.message


def test_fr023_company_concept_invalid_taxonomy_raises_invalid_identifier_zero_requests(
    tmp_path: Path,
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"{}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.company_concept("0000320193", "../x", "EarningsPerShareDiluted")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "invalid identifier"
    assert calls == []


_MALFORMED_BODIES = [b"\xff\xfe", b"not json", b"[]", b"null", b'"s"']
_MALFORMED_IDS = ["invalid-utf8", "non-json", "json-list", "json-null", "json-string"]


@pytest.mark.parametrize("body", _MALFORMED_BODIES, ids=_MALFORMED_IDS)
def test_fr021_lookup_ticker_map_malformed_body_raises_source_http_malformed(
    tmp_path: Path, body: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://www.sec.gov/files/company_tickers.json":
            return httpx.Response(200, content=body)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.lookup("AAPL")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "malformed response"
    decoded = body.decode(errors="replace")
    assert decoded not in str(err.details)
    assert decoded not in err.message


@pytest.mark.parametrize("body", _MALFORMED_BODIES, ids=_MALFORMED_IDS)
def test_fr021_submissions_malformed_body_raises_source_http_malformed(
    tmp_path: Path, body: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://www.sec.gov/files/company_tickers.json":
            return httpx.Response(200, content=_COMPANY_TICKERS)
        if url == "https://data.sec.gov/submissions/CIK0000320193.json":
            return httpx.Response(200, content=body)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.lookup("aapl")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "malformed response"
    decoded = body.decode(errors="replace")
    assert decoded not in str(err.details)
    assert decoded not in err.message

    with pytest.raises(FathomError) as excinfo2:
        sec.filings("0000320193")

    err2 = excinfo2.value
    assert err2.code == Code.SOURCE_HTTP
    assert err2.details["reason"] == "malformed response"


@pytest.mark.parametrize("body", _MALFORMED_BODIES, ids=_MALFORMED_IDS)
def test_fr021_filings_older_page_malformed_body_raises_source_http_malformed(
    tmp_path: Path, body: bytes
) -> None:
    submissions = {
        "name": "Sparse Filer Inc",
        "exchanges": ["Nasdaq"],
        "sicDescription": "Testing",
        "fiscalYearEnd": "1231",
        "filings": {
            "recent": {
                "form": ["4"],
                "filingDate": ["2026-09-01"],
                "reportDate": [""],
                "accessionNumber": ["0000000005-26-000001"],
                "primaryDocument": ["form4.xml"],
            },
            "files": [{"name": "CIK0000000005-submissions-001.json"}],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://data.sec.gov/submissions/CIK0000000005.json":
            return httpx.Response(200, content=json.dumps(submissions).encode())
        if url == "https://data.sec.gov/submissions/CIK0000000005-submissions-001.json":
            return httpx.Response(200, content=body)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = LiveHttp(cache_dir=tmp_path, user_agent="Fathom/0.1.0 (t@example.com)", client=client)
    sec = SecClient(http=http, contact="t@example.com")

    with pytest.raises(FathomError) as excinfo:
        sec.filings("0000000005")

    err = excinfo.value
    assert err.code == Code.SOURCE_HTTP
    assert err.details["reason"] == "malformed response"
    decoded = body.decode(errors="replace")
    assert decoded not in str(err.details)
    assert decoded not in err.message


def test_fr021_fuzz_mutated_submissions_and_ticker_map_raise_only_fathom_error(
    tmp_path: Path,
) -> None:
    """Seeded 200-iteration random-byte mutation fuzz (T-024 AC2): only `FathomError` allowed."""
    rng = random.Random(20240024)

    def mutate(data: bytes) -> bytes:
        mutable = bytearray(data)
        for _ in range(rng.randint(1, 8)):
            idx = rng.randrange(len(mutable))
            mutable[idx] = rng.randrange(256)
        return bytes(mutable)

    for i in range(200):
        mutate_ticker_map = i % 2 == 0
        ticker_body = mutate(_COMPANY_TICKERS) if mutate_ticker_map else _COMPANY_TICKERS
        submissions_body = _AAPL_SUBMISSIONS if mutate_ticker_map else mutate(_AAPL_SUBMISSIONS)

        def handler(
            request: httpx.Request, tb: bytes = ticker_body, sb: bytes = submissions_body
        ) -> httpx.Response:
            url = str(request.url)
            if url == "https://www.sec.gov/files/company_tickers.json":
                return httpx.Response(200, content=tb)
            if url == "https://data.sec.gov/submissions/CIK0000320193.json":
                return httpx.Response(200, content=sb)
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        http = LiveHttp(
            cache_dir=tmp_path / f"iter{i}",
            user_agent="Fathom/0.1.0 (t@example.com)",
            client=client,
        )
        sec = SecClient(http=http, contact="t@example.com")

        try:
            sec.lookup("AAPL")
        except FathomError:
            pass

        try:
            sec.filings("0000320193")
        except FathomError:
            pass


# --- Structural fuzz (T-024 attempt-3 AC2): mutate the *parsed* structure, not raw bytes -------

_STRUCTURAL_REPLACEMENTS: list[object] = [{}, [], None, "x", 0, True, [1], {"a": 1}]

_YAHOO_CHART = json.loads((FIXTURES / "yahoo_chart_aapl.json").read_bytes())
_CONCEPT_TAXONOMY = {
    "EntityCommonStockSharesOutstanding": "dei",
    "EarningsPerShareDiluted": "us-gaap",
    "StockholdersEquity": "us-gaap",
    "CommonStockDividendsPerShareDeclared": "us-gaap",
}
_CONCEPT_FIXTURE_NAMES = {
    "EntityCommonStockSharesOutstanding": "aapl_shares_outstanding.json",
    "EarningsPerShareDiluted": "aapl_eps_diluted.json",
    "StockholdersEquity": "aapl_stockholders_equity.json",
    "CommonStockDividendsPerShareDeclared": "aapl_dividends_per_share.json",
}
_CONCEPTS = {
    concept: json.loads((FIXTURES / name).read_bytes())
    for concept, name in _CONCEPT_FIXTURE_NAMES.items()
}


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


def test_fr024_structural_fuzz_mutated_fixture_nodes_raise_only_fathom_error(
    tmp_path: Path,
) -> None:
    """Structural (parsed-node) fuzz, 300 iterations, seeded (T-024 attempt-3 AC2).

    Complements `test_fr021_fuzz_mutated_submissions_and_ticker_map_raise_only_fathom_error`
    above, which mutates raw bytes and mostly produces bodies that fail to decode at all. This
    fuzzer instead mutates the *parsed* JSON structure (any node at any depth becomes one of
    `{}`/`[]`/`None`/`"x"`/`0`/`True`/`[1]`/`{"a": 1}`, or a dict key is deleted) and
    re-serialises, so every mutated body is still valid JSON — exactly the
    "decoded-but-field-corrupted" class of defect that the attempt-2 finding
    (`submissions["exchanges"]` as a non-list truthy value crashing `lookup()`) fell into.
    Exercises `lookup`, `filings`, `company_concept`, `snapshot` and `daily_bars`; each call must
    either raise `FathomError` or return a structurally valid result — never an uncaught
    `KeyError`/`TypeError`/`IndexError`/etc.
    """
    rng = random.Random(24024)
    tickers = json.loads(_COMPANY_TICKERS)
    submissions = json.loads(_AAPL_SUBMISSIONS)
    concept_names = list(_CONCEPTS)
    targets = ["tickers", "submissions", *concept_names, "yahoo"]

    for i in range(300):
        target = targets[i % len(targets)]
        mutated_tickers = _structural_mutate(tickers, rng) if target == "tickers" else tickers
        mutated_submissions = (
            _structural_mutate(submissions, rng) if target == "submissions" else submissions
        )
        mutated_concepts = dict(_CONCEPTS)
        if target in concept_names:
            mutated_concepts[target] = _structural_mutate(_CONCEPTS[target], rng)
        mutated_chart = _structural_mutate(_YAHOO_CHART, rng) if target == "yahoo" else _YAHOO_CHART

        def handler(
            request: httpx.Request,
            mt: object = mutated_tickers,
            ms: object = mutated_submissions,
            mcpt: dict[str, object] = mutated_concepts,
            mch: object = mutated_chart,
        ) -> httpx.Response:
            url = str(request.url)
            if url == "https://www.sec.gov/files/company_tickers.json":
                return httpx.Response(200, content=json.dumps(mt).encode())
            if url == "https://data.sec.gov/submissions/CIK0000320193.json":
                return httpx.Response(200, content=json.dumps(ms).encode())
            if "companyconcept" in url:
                for concept, body in mcpt.items():
                    if url.endswith(f"/{concept}.json"):
                        return httpx.Response(200, content=json.dumps(body).encode())
                return httpx.Response(404)
            if url.startswith("https://query1.finance.yahoo.com/v8/finance/chart/"):
                return httpx.Response(200, content=json.dumps(mch).encode())
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        http = LiveHttp(
            cache_dir=tmp_path / f"struct{i}",
            user_agent="Fathom/0.1.0 (t@example.com)",
            client=client,
            sleeper=lambda _seconds: None,  # no real sleep: the per-host throttle is irrelevant
        )
        sec = SecClient(http=http, contact="t@example.com")

        try:
            company = sec.lookup("AAPL")
            assert isinstance(company, SecCompany)
        except FathomError:
            pass

        try:
            filings = sec.filings("0000320193")
            assert all(isinstance(f, SecFiling) for f in filings)
        except FathomError:
            pass

        for concept, taxonomy in _CONCEPT_TAXONOMY.items():
            try:
                result = sec.company_concept("0000320193", taxonomy, concept)
                assert isinstance(result, dict)
            except FathomError:
                pass

        try:
            snap = compute_snapshot(sec, "0000320193", 100.0, datetime(2026, 9, 1, tzinfo=UTC))
            assert isinstance(snap, dict)
        except FathomError:
            pass

        try:
            bars = PriceClient(http, primary="yahoo").daily_bars("AAPL")
            assert list(bars.columns) == [
                "symbol",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        except FathomError:
            pass
