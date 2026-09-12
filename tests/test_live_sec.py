"""Tests for fathom.live.sec (RTM: FR-021, FR-025, NFR-013)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from fathom import __version__
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.filings import parse_sections, period_end
from fathom.live.http import LiveHttp
from fathom.live.sec import SecClient, SecFiling, html_to_text

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
