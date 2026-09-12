"""Filings listing and canonical-section parser (LLD §2.5)."""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel

from fathom.data import load_frame, require_ticker
from fathom.errors import Code, FathomError

HEADER = re.compile(
    r"^[ \t]*item[ \t]+(\d{1,2}[a-c]?)[ \t]*[.:\-—–]?[ \t]*([^\n]{0,120})$",
    re.I | re.M,
)
PART = re.compile(r"^[ \t]*part[ \t]+(i{1,2})\b", re.I | re.M)

PERIOD_END = re.compile(
    r"for the (?:fiscal|quarterly)?\s*(?:year|period)\s+ended\s+"
    r"([A-Z][a-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})",
    re.I | re.S,
)

# Group key: ("" for 10-K items, or the Part numeral "I"/"II" for 10-Q items, item id).
_NO_PART = ""

CANONICAL_SECTIONS: dict[str, str] = {
    "10-K:1": "Business",
    "10-K:1A": "Risk Factors",
    "10-K:1C": "Cybersecurity",
    "10-K:3": "Legal Proceedings",
    "10-K:7": "Management's Discussion and Analysis",
    "10-K:7A": "Market Risk",
    "10-K:9A": "Controls and Procedures",
    "10-Q:I.2": "Management's Discussion and Analysis",
    "10-Q:I.3": "Market Risk",
    "10-Q:I.4": "Controls and Procedures",
    "10-Q:II.1": "Legal Proceedings",
    "10-Q:II.1A": "Risk Factors",
}

_10K_KEY_TO_ID: dict[tuple[str, str], str] = {
    (_NO_PART, "1"): "10-K:1",
    (_NO_PART, "1A"): "10-K:1A",
    (_NO_PART, "1C"): "10-K:1C",
    (_NO_PART, "3"): "10-K:3",
    (_NO_PART, "7"): "10-K:7",
    (_NO_PART, "7A"): "10-K:7A",
    (_NO_PART, "9A"): "10-K:9A",
}
_10Q_KEY_TO_ID: dict[tuple[str, str], str] = {
    ("I", "2"): "10-Q:I.2",
    ("I", "3"): "10-Q:I.3",
    ("I", "4"): "10-Q:I.4",
    ("II", "1"): "10-Q:II.1",
    ("II", "1A"): "10-Q:II.1A",
}

# Step 7 (D-006): heading-vocabulary fallback. Title keys per canonical id (LLD §2.5 step 7);
# 10-Q ids reuse the same keys as the 10-K id with the matching title.
_FALLBACK_MIN_BODY = 400
_TITLE_KEYS: dict[str, tuple[str, ...]] = {
    "10-K:1": ("description of the business", "business summary", "business"),
    "10-K:1A": ("risk factors",),
    "10-K:1C": ("cybersecurity",),
    "10-K:3": ("legal proceedings",),
    "10-K:7": ("management's discussion and analysis", "management’s discussion and analysis"),
    "10-K:7A": ("quantitative and qualitative disclosures",),
    "10-K:9A": ("controls and procedures",),
    "10-Q:I.2": ("management's discussion and analysis", "management’s discussion and analysis"),
    "10-Q:I.3": ("quantitative and qualitative disclosures",),
    "10-Q:I.4": ("controls and procedures",),
    "10-Q:II.1": ("legal proceedings",),
    "10-Q:II.1A": ("risk factors",),
}


class Filing(BaseModel):
    """One 10-K/10-Q filing record (LLD §2.5)."""

    ticker: str
    cik: str
    company_name: str
    form: Literal["10-K", "10-Q"]
    filing_date: date
    period_end: date | None
    accession: str
    edgar_url: str
    n_chars: int


class Section(BaseModel):
    """One canonical section parsed from a filing's normalised text (LLD §2.5)."""

    accession: str
    section_id: str
    title: str
    text: str
    char_start: int
    char_end: int


def edgar_url(cik: str, accession: str) -> str:
    """Build the EDGAR filing-index URL for a CIK/accession pair."""
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"


def period_end(text: str) -> date | None:
    """Extract the fiscal period-end date from the first 4,000 characters of `text`."""
    normalised = text.replace("\xa0", " ")
    match = PERIOD_END.search(normalised[:4000])
    if match is None:
        return None
    month_name, day, year = match.groups()
    try:
        return datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y").date()
    except ValueError:
        return None


def _part_lookup(part_matches: list[re.Match[str]]) -> Callable[[int], str]:
    """Return a closure mapping a position to the nearest preceding Part numeral."""

    def lookup(pos: int) -> str:
        current = "I"
        for pm in part_matches:
            if pm.start() > pos:
                break
            current = pm.group(1).upper()
        return current

    return lookup


def _heading_vocabulary_matches(normalised: str) -> list[tuple[int, int, str]]:
    """(line_start, line_end, section_id) for every line starting with a `_TITLE_KEYS` phrase.

    `line_end` is the character offset immediately after the line's content (before its
    newline), matching how `HEADER` bodies are bounded.
    """
    matches: list[tuple[int, int, str]] = []
    pos = 0
    for raw_line in normalised.splitlines(keepends=True):
        content = raw_line.rstrip("\r\n")
        stripped = content.strip()
        if stripped and len(stripped) <= 120:
            low = stripped.lower()
            for section_id, keys in _TITLE_KEYS.items():
                if any(low.startswith(key) for key in keys):
                    matches.append((pos, pos + len(content), section_id))
                    break
        pos += len(raw_line)
    return matches


def _fallback_candidate(
    section_id: str,
    heading_matches: list[tuple[int, int, str]],
    item_header_starts: list[int],
    text_length: int,
) -> tuple[int, int] | None:
    """The longest (char_start, char_end) candidate body for `section_id`, or None."""
    boundary_starts = sorted({start for start, _, _ in heading_matches})
    best_candidate: tuple[int, int] | None = None
    for start, end, matched_id in heading_matches:
        if matched_id != section_id:
            continue
        next_boundaries = [b for b in boundary_starts if b > start]
        next_headers = [h for h in item_header_starts if h > start]
        candidate_end = min([text_length, *next_boundaries, *next_headers])
        candidate_len = candidate_end - end
        best_len = best_candidate[1] - best_candidate[0] if best_candidate is not None else -1
        if candidate_len > best_len:
            best_candidate = (end, candidate_end)
    return best_candidate


def _apply_heading_fallback(normalised: str, sections: list[Section]) -> list[Section]:
    """Step 7 (D-006): widen any canonical section whose step-4 body is < 400 chars.

    Leaves `sections` untouched (byte-identical) unless at least one section is short and a
    longer heading-vocabulary candidate is found for it.
    """
    short_ids = {s.section_id for s in sections if len(s.text) < _FALLBACK_MIN_BODY}
    if not short_ids:
        return sections

    heading_matches = _heading_vocabulary_matches(normalised)
    item_header_starts = [m.start() for m in HEADER.finditer(normalised)]
    text_length = len(normalised)

    widened: dict[str, Section] = {}
    for section in sections:
        if section.section_id not in short_ids:
            continue
        candidate = _fallback_candidate(
            section.section_id, heading_matches, item_header_starts, text_length
        )
        if candidate is None:
            continue
        char_start, char_end = candidate
        if (char_end - char_start) > len(section.text):
            widened[section.section_id] = section.model_copy(
                update={
                    "text": normalised[char_start:char_end],
                    "char_start": char_start,
                    "char_end": char_end,
                }
            )

    if not widened:
        return sections
    return [widened.get(section.section_id, section) for section in sections]


def parse_sections(text: str, form: str) -> list[Section]:
    """Parse `text` into canonical sections (pure; caller fills `Section.accession`)."""
    normalised = text.replace("\xa0", " ")
    headers = list(HEADER.finditer(normalised))
    key_to_id = _10Q_KEY_TO_ID if form == "10-Q" else _10K_KEY_TO_ID
    part_matches = list(PART.finditer(normalised)) if form == "10-Q" else []
    part_at = _part_lookup(part_matches)

    text_length = len(normalised)
    best: dict[tuple[str, str], tuple[int, int, int]] = {}  # key -> (body_len, start, end)
    for index, match in enumerate(headers):
        item = match.group(1).upper()
        header_start = match.start()
        header_end = match.end()
        next_start = headers[index + 1].start() if index + 1 < len(headers) else text_length
        body_len = next_start - header_end
        part = part_at(header_start) if form == "10-Q" else _NO_PART
        key = (part, item)
        current_best = best.get(key)
        if current_best is None or body_len > current_best[0]:
            best[key] = (body_len, header_start, next_start)

    sections = []
    for key, (_, char_start, char_end) in best.items():
        section_id = key_to_id.get(key)
        if section_id is None:
            continue
        sections.append(
            Section(
                accession="",
                section_id=section_id,
                title=CANONICAL_SECTIONS[section_id],
                text=normalised[char_start:char_end],
                char_start=char_start,
                char_end=char_end,
            )
        )
    sections.sort(key=lambda section: section.char_start)

    if not sections:
        raise FathomError(
            Code.PARSE_FAILED,
            f"no canonical sections found for form {form!r}",
            {"form": form},
        )

    sections = _apply_heading_fallback(normalised, sections)
    sections.sort(key=lambda section: section.char_start)
    return sections


@functools.cache
def sections_for(accession: str, data_dir: Path) -> list[Section]:
    """Return the canonical sections for one filing, cached by (accession, data_dir)."""
    frame = load_frame("filings", data_dir)
    rows = frame[frame["accession"] == accession]
    if rows.empty:
        raise FathomError(
            Code.DATA_MISSING,
            f"no filing for accession {accession!r}",
            {"accession": accession},
        )
    row = rows.iloc[0]
    sections = parse_sections(str(row["text"]), str(row["form"]))
    return [section.model_copy(update={"accession": accession}) for section in sections]


def filings_for(ticker: str, data_dir: Path) -> list[Filing]:
    """List a ticker's filings newest first."""
    symbol = require_ticker(ticker)
    frame = load_frame("filings", data_dir)
    rows = frame[frame["ticker"] == symbol]
    if rows.empty:
        raise FathomError(
            Code.DATA_MISSING,
            f"no filings for {symbol!r}",
            {"name": "filings"},
        )

    filings = []
    for _, row in rows.iterrows():
        cik = str(row["cik"])
        accession = str(row["accession"])
        form_value = str(row["form"])
        if form_value not in ("10-K", "10-Q"):
            raise FathomError(
                Code.PARSE_FAILED,
                f"unexpected form {form_value!r}",
                {"accession": accession},
            )
        form = cast(Literal["10-K", "10-Q"], form_value)
        filings.append(
            Filing(
                ticker=symbol,
                cik=cik,
                company_name=str(row["company_name"]),
                form=form,
                filing_date=row["filing_date"],
                period_end=period_end(str(row["text"])),
                accession=accession,
                edgar_url=edgar_url(cik, accession),
                n_chars=int(row["n_chars"]),
            )
        )
    filings.sort(key=lambda filing: filing.filing_date, reverse=True)
    return filings
