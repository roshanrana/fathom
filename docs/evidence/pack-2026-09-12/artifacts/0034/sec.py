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


def _malformed_response_error(source: str) -> FathomError:
    """Build the SOURCE_HTTP "malformed response" error (never echoes body/URL text).

    Shared by `_decode_json` (whole-body decode guard) and every per-entry structure guard
    below (`ticker_map`, `filings`, `_to_filing`) so a structurally corrupted-but-valid-JSON
    payload fails the same way as an undecodable one (T-024 attempt-1 finding).
    """
    return FathomError(
        Code.SOURCE_HTTP,
        f"{source} response could not be parsed",
        {"source": source, "status": 200, "reason": "malformed response"},
    )


def _str_field(obj: object, key: str) -> str | None:
    """`obj[key]` if `obj` is a `dict` and the value is a `str`, else `None` (T-024 attempt-3).

    Shared typed accessor: every SEC payload field read across `sec.py`, `facts.py` and
    `prices.py` goes through one of these four helpers instead of a raw subscript/`.get()`, so a
    wrongly-typed (but valid-JSON) value can never reach a raw index/attribute op unguarded — the
    systemic version of the attempt-2 `submissions["exchanges"]` finding (a `cast()` has no
    runtime effect; a truthy non-list value slipped through `exchanges[0]`).
    """
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    return value if isinstance(value, str) else None


def _int_field(obj: object, key: str) -> int | None:
    """`obj[key]` if `obj` is a `dict` and the value is an `int` (bool excluded), else `None`."""
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _list_field(obj: object, key: str) -> list[object]:
    """`obj[key]` if `obj` is a `dict` and the value is a `list`, else `[]`."""
    if not isinstance(obj, dict):
        return []
    value = obj.get(key)
    return value if isinstance(value, list) else []


def _dict_field(obj: object, key: str) -> dict[str, object]:
    """`obj[key]` if `obj` is a `dict` and the value is itself a `dict`, else `{}`."""
    if not isinstance(obj, dict):
        return {}
    value = obj.get(key)
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _decode_json(body: bytes, source: str) -> dict[str, object]:
    """Decode a JSON-object body from `source` (05-m4-live-data.md §4 SOURCE_HTTP guard, frozen).

    Every SEC JSON response — the ticker map, submissions documents (including paginated
    older-filing pages), and companyconcept — is routed through this one helper. UTF-8 decoding
    and JSON parsing happen inside a single `except Exception`, and a non-dict top-level value
    is rejected the same way, so a corrupted or unexpected body never reaches a caller as a bare
    `UnicodeDecodeError`/`JSONDecodeError` (T-023 attempt-4/attempt-5 findings). Raises
    `SOURCE_HTTP` reason "malformed response" with no body/URL text in message or details.

    Note: this only guarantees the *top-level* body parsed as JSON and is a `dict` — it says
    nothing about the shape of entries nested inside (per-ticker or per-filing rows). Callers
    that index into nested entries must validate those separately (see `ticker_map`, `filings`,
    `_to_filing`; T-024 attempt-1 finding).
    """
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise TypeError(f"{source} payload is not a JSON object")
    except Exception as exc:  # noqa: BLE001 - whole-body parse guard, see docstring
        raise _malformed_response_error(source) from exc
    return cast(dict[str, object], payload)


_RECENT_TABLE_KEYS = ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument")


def _valid_table_rows(table: object) -> list[dict[str, object]]:
    """Validate and reconstruct rows from an EDGAR parallel-array table (T-024 attempt-1 fix).

    `table` (e.g. `filings.recent`, or an older-filings page) must be a `dict` of equal-length
    lists covering every key in `_RECENT_TABLE_KEYS`. Any structural problem — not a dict,
    a missing/non-list key, or unequal-length lists — yields zero rows rather than raising;
    callers treat zero rows as "nothing qualifies" (SOURCE_EMPTY further up the call chain),
    never a crash. A row is included only if every expected key holds a `str` value at that
    index; rows with a non-string value (a mutated int/null/list in place of a form/accession/
    document/date string) are silently skipped rather than indexed unguarded.
    """
    if not isinstance(table, dict):
        return []
    lists: dict[str, list[object]] = {}
    for key in _RECENT_TABLE_KEYS:
        value = table.get(key)
        if not isinstance(value, list):
            return []
        lists[key] = value
    length = len(lists[_RECENT_TABLE_KEYS[0]])
    if any(len(values) != length for values in lists.values()):
        return []
    rows: list[dict[str, object]] = []
    for i in range(length):
        row = {key: lists[key][i] for key in _RECENT_TABLE_KEYS}
        if all(isinstance(value, str) for value in row.values()):
            rows.append(row)
    return rows


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
        """The SEC ticker -> CIK map, keyed by upper-cased ticker (e.g. "BRK-B").

        Each raw entry is validated before being indexed (T-024 attempt-1 fix): only entries
        that are `dict`s with a string `ticker`, a string `title`, and an `int` `cik_str` are
        kept; anything else (a mutated key/value that still parses as JSON) is silently
        skipped. If validation leaves zero entries, the whole response is treated as malformed
        (`SOURCE_HTTP` reason "malformed response") rather than returning an empty map.
        """
        body = self._http.get(_TICKER_MAP_URL, ttl_hours=_TICKER_MAP_TTL_HOURS, source="sec")
        raw = _decode_json(body, "sec")
        result: dict[str, dict[str, object]] = {}
        for entry in raw.values():
            if not isinstance(entry, dict):
                continue
            ticker = _str_field(entry, "ticker")
            title = _str_field(entry, "title")
            cik_str = _int_field(entry, "cik_str")
            if ticker is not None and title is not None and cik_str is not None:
                result[ticker.upper()] = entry
        if not result:
            raise _malformed_response_error("sec")
        return result

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

        # Defense in depth: `entry` already passed `ticker_map`'s per-entry validation, but never
        # index a payload-derived dict without a guard (T-024 attempt-2 finding: `cast()` has no
        # runtime effect, so a value that only *looks* right to the type checker can still be
        # wrongly-typed at runtime).
        cik_str = _int_field(entry, "cik_str")
        entry_ticker = _str_field(entry, "ticker")
        if cik_str is None or entry_ticker is None:
            raise _invalid_edgar_field_error()
        cik = f"{cik_str:010d}"
        submissions = self._submissions(cik)

        exchanges = _list_field(submissions, "exchanges")
        first_exchange = exchanges[0] if exchanges else None
        exchange = first_exchange if isinstance(first_exchange, str) and first_exchange else None
        sic_description = _str_field(submissions, "sicDescription")
        fiscal_year_end = _str_field(submissions, "fiscalYearEnd")
        name = _str_field(submissions, "name") or _str_field(entry, "title") or ""
        return SecCompany(
            ticker=entry_ticker.upper(),
            cik=cik,
            name=name,
            exchange=exchange,
            sic_description=sic_description,
            fiscal_year_end=fiscal_year_end,
        )

    def filings(self, cik: str) -> list[SecFiling]:
        """The latest 10-K plus up to four 10-Qs filed within 730 days, newest first."""
        submissions = self._submissions(cik)
        filings_block = _dict_field(submissions, "filings")
        entries = _valid_table_rows(filings_block.get("recent"))

        candidates = [entry for entry in entries if _str_field(entry, "form") in _QUALIFYING_FORMS]

        if len(candidates) < _MIN_QUALIFYING_BEFORE_OLDER_PAGES:
            for page in _list_field(filings_block, "files"):
                name = _str_field(page, "name")
                if not name:
                    continue
                _validate_safe_name(name)
                page_url = _SUBMISSIONS_PAGE_URL.format(name=name)
                body = self._http.get(page_url, ttl_hours=_SUBMISSIONS_TTL_HOURS, source="sec")
                page_table = _decode_json(body, "sec")
                page_entries = _valid_table_rows(page_table)
                candidates.extend(
                    entry
                    for entry in page_entries
                    if _str_field(entry, "form") in _QUALIFYING_FORMS
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
        # Defense in depth: `entry` should already be a `_valid_table_rows` row (all of
        # form/accessionNumber/primaryDocument present as `str`), but never index an
        # untrusted-derived entry without a guard (T-024 attempt-1/attempt-3 findings).
        form_raw = _str_field(entry, "form")
        accession = _str_field(entry, "accessionNumber")
        primary_document = _str_field(entry, "primaryDocument")
        if form_raw not in _QUALIFYING_FORMS or accession is None or primary_document is None:
            raise _malformed_response_error("sec")
        form = cast(Literal["10-K", "10-Q"], form_raw)
        _validate_accession(accession)
        _validate_safe_name(primary_document)
        filing_date = _parse_date(_str_field(entry, "filingDate") or "")
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
            report_date=_parse_date(_str_field(entry, "reportDate") or ""),
            primary_document=primary_document,
            url=_document_url(cik, accession, primary_document),
        )
