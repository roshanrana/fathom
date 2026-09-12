"""SEC EDGAR client: ticker lookup, filings selection, document text (05-m4-live-data.md §4).

Endpoints (User-Agent `Fathom/<__version__> (<contact>)`, `Accept-Encoding: gzip`, all via
`LiveHttp` for caching/throttling):

- `https://www.sec.gov/files/company_tickers.json` (ticker -> CIK map, TTL 24h)
- `https://data.sec.gov/submissions/CIK<10>.json` (company facts + recent filings, TTL 6h)
- `https://www.sec.gov/Archives/edgar/data/<cik int>/<accession no dashes>/<primary_document>`
  (primary document, cached forever)
- `https://data.sec.gov/api/xbrl/companyconcept/CIK<10>/<taxonomy>/<concept>.json` (TTL 6h;
  exposed for T-019's `snapshot()`)
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta
from typing import Literal, cast

from pydantic import BaseModel

from fathom import __version__
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.live.http import LiveHttp

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
_COMPANY_CONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json"
)

_TICKER_MAP_TTL_HOURS = 24.0
_SUBMISSIONS_TTL_HOURS = 6.0
_FACTS_TTL_HOURS = 6.0
_DOCUMENT_TTL_HOURS: float | None = None  # forever

_QUALIFYING_FORMS = ("10-K", "10-Q")
_MAX_WINDOW_DAYS = 730
_MAX_10Q_COUNT = 4
_MIN_QUALIFYING_BEFORE_OLDER_PAGES = 5


class SecCompany(BaseModel):
    """A resolved SEC-registered company (05-m4-live-data.md §4, frozen)."""

    ticker: str
    cik: str
    name: str
    exchange: str | None
    sic_description: str | None
    fiscal_year_end: str | None


class SecFiling(BaseModel):
    """One 10-K/10-Q filing as listed by EDGAR submissions (05-m4-live-data.md §4, frozen)."""

    cik: str
    accession: str
    form: Literal["10-K", "10-Q"]
    filing_date: date
    report_date: date | None
    primary_document: str
    url: str


_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_CONCEPT_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _invalid_edgar_field_error() -> FathomError:
    """Build the SOURCE_HTTP error for a malformed EDGAR JSON field (never echoes the value)."""
    return FathomError(
        Code.SOURCE_HTTP,
        "sec response contained an invalid edgar field",
        {"source": "sec", "status": 0, "reason": "invalid edgar field"},
    )


def _validate_accession(accession: str) -> None:
    if not _ACCESSION_RE.match(accession):
        raise _invalid_edgar_field_error()


def _validate_safe_name(name: str) -> None:
    if ".." in name or not _SAFE_NAME_RE.match(name):
        raise _invalid_edgar_field_error()


def _invalid_concept_identifier_error() -> FathomError:
    """SOURCE_HTTP for a `taxonomy`/`concept` that fails the safe-identifier pattern."""
    return FathomError(
        Code.SOURCE_HTTP,
        "invalid taxonomy/concept identifier supplied to company_concept",
        {"source": "sec", "status": 0, "reason": "invalid identifier"},
    )


def _validate_concept_identifier(value: str) -> None:
    if not _CONCEPT_IDENTIFIER_RE.fullmatch(value):
        raise _invalid_concept_identifier_error()


def _decode_json(body: bytes, source: str) -> dict[str, object]:
    """Decode a JSON-object body from `source` (05-m4-live-data.md §4 SOURCE_HTTP guard, frozen).

    Every SEC JSON response — the ticker map, submissions documents (including paginated
    older-filing pages), and companyconcept — is routed through this one helper. UTF-8 decoding
    and JSON parsing happen inside a single `except Exception`, and a non-dict top-level value
    is rejected the same way, so a corrupted or unexpected body never reaches a caller as a bare
    `UnicodeDecodeError`/`JSONDecodeError` (T-023 attempt-4/attempt-5 findings). Raises
    `SOURCE_HTTP` reason "malformed response" with no body/URL text in message or details.
    """
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise TypeError(f"{source} payload is not a JSON object")
    except Exception as exc:  # noqa: BLE001 - whole-body parse guard, see docstring
        raise FathomError(
            Code.SOURCE_HTTP,
            f"{source} response could not be parsed",
            {"source": source, "status": 200, "reason": "malformed response"},
        ) from exc
    return cast(dict[str, object], payload)


def _document_url(cik: str, accession: str, primary_document: str) -> str:
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{primary_document}"
    )


def _parse_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


_STRIP_BLOCK_RE = re.compile(r"<(script|style|head|ix:header)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>", re.S)
_BR_RE = re.compile(r"^<\s*br\b", re.I)
_CLOSE_NEWLINE_RE = re.compile(r"^</\s*(p|div|tr|li|h[1-6]|table|section)\b", re.I)
_SPACE_RUN_RE = re.compile(r"[ \t]+")
_BLANK_LINE_RUN_RE = re.compile(r"\n(?:[ \t]*\n)+")


def _tag_replacement(match: re.Match[str]) -> str:
    tag = match.group(0)
    if _BR_RE.match(tag) or _CLOSE_NEWLINE_RE.match(tag):
        return "\n"
    return " "


def html_to_text(html_content: str) -> str:
    """Convert filing HTML to parser-ready text (05-m4-live-data.md §4, frozen algorithm).

    Drops `<script>`/`<style>`/`<head>`/XBRL `ix:header`; `<br>` and the close of
    `p, div, tr, li, h1-h6, table, section` become "\\n"; every other tag becomes " ";
    entities are unescaped; `\\xa0` becomes a space; space/tab runs collapse to one space;
    blank-line runs collapse to one "\\n". Stdlib `html` + `re` only.
    """
    stripped = _STRIP_BLOCK_RE.sub("", html_content)
    spaced = _TAG_RE.sub(_tag_replacement, stripped)
    unescaped = html.unescape(spaced)
    normalised = unescaped.replace("\xa0", " ")
    collapsed = _SPACE_RUN_RE.sub(" ", normalised)
    collapsed = _BLANK_LINE_RUN_RE.sub("\n", collapsed)
    return collapsed.strip()


def _entries_from_table(table: dict[str, list[object]]) -> list[dict[str, object]]:
    keys = list(table.keys())
    length = len(table[keys[0]]) if keys else 0
    return [{key: table[key][i] for key in keys} for i in range(length)]


class SecClient:
    """SEC EDGAR access: ticker resolution, filings listing, document text."""

    def __init__(self, http: LiveHttp, contact: str) -> None:
        self._http = http
        self._contact = contact

    @classmethod
    def from_settings(cls, settings: Settings, http: LiveHttp | None = None) -> SecClient:
        """Build a client from `Settings`; raises `SOURCE_CONFIG` without a contact e-mail."""
        if not settings.sec_contact:
            raise FathomError(
                Code.SOURCE_CONFIG,
                "FATHOM_SEC_CONTACT is required to contact SEC EDGAR in live mode",
                {"var": "FATHOM_SEC_CONTACT"},
            )
        live_http = http
        if live_http is None:
            user_agent = f"Fathom/{__version__} ({settings.sec_contact})"
            live_http = LiveHttp(cache_dir=settings.live_cache_dir, user_agent=user_agent)
        return cls(http=live_http, contact=settings.sec_contact)

    def ticker_map(self) -> dict[str, dict[str, object]]:
        """The SEC ticker -> CIK map, keyed by upper-cased ticker (e.g. "BRK-B")."""
        body = self._http.get(_TICKER_MAP_URL, ttl_hours=_TICKER_MAP_TTL_HOURS, source="sec")
        raw = cast(dict[str, dict[str, object]], _decode_json(body, "sec"))
        return {str(entry["ticker"]).upper(): entry for entry in raw.values()}

    def lookup(self, ticker: str) -> SecCompany:
        """Resolve a ticker to its `SecCompany`; normalises "." <-> "-" (e.g. BRK.B/BRK-B)."""
        upper = ticker.upper()
        candidates = [upper]
        if "." in upper:
            candidates.append(upper.replace(".", "-"))
        if "-" in upper:
            candidates.append(upper.replace("-", "."))

        mapping = self.ticker_map()
        entry = next((mapping[candidate] for candidate in candidates if candidate in mapping), None)
        if entry is None:
            raise FathomError(Code.UNKNOWN_TICKER, f"unknown ticker {upper!r}", {"ticker": upper})

        cik = f"{int(cast(int, entry['cik_str'])):010d}"
        submissions = self._submissions(cik)
        exchanges = cast(list[object], submissions.get("exchanges") or [])
        exchange = str(exchanges[0]) if exchanges and exchanges[0] else None
        sic_description = submissions.get("sicDescription")
        fiscal_year_end = submissions.get("fiscalYearEnd")
        return SecCompany(
            ticker=str(entry["ticker"]).upper(),
            cik=cik,
            name=str(submissions.get("name", entry.get("title", ""))),
            exchange=exchange,
            sic_description=str(sic_description) if sic_description else None,
            fiscal_year_end=str(fiscal_year_end) if fiscal_year_end else None,
        )

    def filings(self, cik: str) -> list[SecFiling]:
        """The latest 10-K plus up to four 10-Qs filed within 730 days, newest first."""
        submissions = self._submissions(cik)
        filings_block = cast(dict[str, object], submissions.get("filings", {}))
        recent = cast(dict[str, list[object]], filings_block.get("recent", {}))
        entries = _entries_from_table(recent)

        candidates = [entry for entry in entries if entry.get("form") in _QUALIFYING_FORMS]

        if len(candidates) < _MIN_QUALIFYING_BEFORE_OLDER_PAGES:
            for page in cast(list[dict[str, object]], filings_block.get("files", [])):
                name = str(page.get("name", ""))
                if not name:
                    continue
                _validate_safe_name(name)
                page_url = _SUBMISSIONS_PAGE_URL.format(name=name)
                body = self._http.get(page_url, ttl_hours=_SUBMISSIONS_TTL_HOURS, source="sec")
                page_table = cast(dict[str, list[object]], _decode_json(body, "sec"))
                page_entries = _entries_from_table(page_table)
                candidates.extend(
                    entry for entry in page_entries if entry.get("form") in _QUALIFYING_FORMS
                )

        parsed = [self._to_filing(cik, entry) for entry in candidates]
        parsed.sort(key=lambda filing: filing.filing_date, reverse=True)
        if not parsed:
            raise FathomError(
                Code.SOURCE_EMPTY,
                f"no 10-K/10-Q filings found for CIK {cik!r}",
                {"cik": cik},
            )

        newest_date = parsed[0].filing_date
        cutoff = newest_date - timedelta(days=_MAX_WINDOW_DAYS)
        within_window = [filing for filing in parsed if filing.filing_date >= cutoff]

        latest_10k = next((filing for filing in within_window if filing.form == "10-K"), None)
        latest_10qs = [filing for filing in within_window if filing.form == "10-Q"][:_MAX_10Q_COUNT]

        selected = ([latest_10k] if latest_10k is not None else []) + latest_10qs
        if not selected:
            raise FathomError(
                Code.SOURCE_EMPTY,
                f"no 10-K/10-Q filings within {_MAX_WINDOW_DAYS} days for CIK {cik!r}",
                {"cik": cik},
            )
        selected.sort(key=lambda filing: filing.filing_date, reverse=True)
        return selected

    def document_text(self, filing: SecFiling) -> str:
        """Fetch a filing's primary document and convert it to parser-ready text.

        Documents are cached forever (`ttl_hours=None`): a second call for the same filing
        makes zero transport calls.
        """
        body = self._http.get(filing.url, ttl_hours=_DOCUMENT_TTL_HOURS, source="sec")
        return html_to_text(body.decode("utf-8", errors="replace"))

    def company_concept(self, cik: str, taxonomy: str, concept: str) -> dict[str, object]:
        """Raw XBRL companyconcept facts for `cik`/`taxonomy`/`concept` (used by T-019).

        Validates `taxonomy`/`concept` against a safe-identifier pattern before building the
        URL (`SOURCE_HTTP` reason "invalid identifier", zero requests on failure). The response
        body is decoded inside a guard: anything that fails to parse into a JSON object (a
        non-dict top-level value, or non-JSON text) raises `SOURCE_HTTP` reason "malformed
        response", with no body/URL text in the error (T-023 attempt 4 HIGH).
        """
        _validate_concept_identifier(taxonomy)
        _validate_concept_identifier(concept)
        url = _COMPANY_CONCEPT_URL.format(cik=cik, taxonomy=taxonomy, concept=concept)
        body = self._http.get(url, ttl_hours=_FACTS_TTL_HOURS, source="sec")
        return _decode_json(body, "sec")

    def _submissions(self, cik: str) -> dict[str, object]:
        url = _SUBMISSIONS_URL.format(cik=cik)
        body = self._http.get(url, ttl_hours=_SUBMISSIONS_TTL_HOURS, source="sec")
        return _decode_json(body, "sec")

    def _to_filing(self, cik: str, entry: dict[str, object]) -> SecFiling:
        form = cast(Literal["10-K", "10-Q"], entry["form"])
        accession = str(entry["accessionNumber"])
        primary_document = str(entry["primaryDocument"])
        _validate_accession(accession)
        _validate_safe_name(primary_document)
        filing_date = _parse_date(str(entry.get("filingDate", "")))
        if filing_date is None:
            raise FathomError(
                Code.CONTRACT_INVALID,
                f"filing {accession!r} has an unparsable filingDate",
                {"accession": accession},
            )
        return SecFiling(
            cik=cik,
            accession=accession,
            form=form,
            filing_date=filing_date,
            report_date=_parse_date(str(entry.get("reportDate", ""))),
            primary_document=primary_document,
            url=_document_url(cik, accession, primary_document),
        )
