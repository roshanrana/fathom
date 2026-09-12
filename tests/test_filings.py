"""Tests for fathom.filings (RTM: FR-004, FR-005)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fathom.errors import Code, FathomError
from fathom.filings import (
    CANONICAL_SECTIONS,
    Section,
    edgar_url,
    filings_for,
    parse_sections,
    period_end,
    sections_for,
)

# AC4 allowlist: fixture accessions genuinely lacking a required canonical section,
# with a one-line reason each. Must stay empty unless a real fixture gap is found.
AC4_ALLOWLIST: dict[str, str] = {}


def test_fr004_filings_for_lists_aapl_newest_first(data_dir: Path) -> None:
    """AC1: filings_for("AAPL", ...) returns 5 filings newest first with expected fields."""
    filings = filings_for("AAPL", data_dir)

    assert len(filings) == 5
    assert filings[0].form == "10-Q"
    assert filings[0].filing_date == date(2026, 5, 1)
    assert [f.filing_date for f in filings] == sorted(
        (f.filing_date for f in filings), reverse=True
    )

    ten_k = next(f for f in filings if f.form == "10-K")
    assert ten_k.accession == "0000320193-25-000079"
    assert ten_k.edgar_url == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/"
    assert ten_k.period_end == date(2025, 9, 27)


def test_fr004_filings_for_unknown_ticker_raises(data_dir: Path) -> None:
    """filings_for raises UNKNOWN_TICKER for a ticker outside the universe."""
    with pytest.raises(FathomError) as exc_info:
        filings_for("ZZZZ", data_dir)
    assert exc_info.value.code == Code.UNKNOWN_TICKER


def test_fr004_edgar_url_strips_cik_zero_padding_and_dashes() -> None:
    """edgar_url formats the CIK as an int and strips dashes from the accession."""
    url = edgar_url("0000320193", "0000320193-25-000079")
    assert url == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/"


def test_fr005_parse_sections_prefers_body_over_table_of_contents() -> None:
    """AC2: a TOC entry is dropped in favor of the real (longer) section body."""
    toc = "Table of Contents\nItem 1A. Risk Factors 5\nItem 1B. Other stuff 6\n"
    body = (
        "Item 1A. Risk Factors\n"
        "This is the real risk factors body with lots of detail about risks facing "
        "the company.\n"
        "Item 1B. Other stuff\nOther content here.\n"
    )
    text = toc + ("x" * 50) + "\n" + body
    body_header_start = text.index("Item 1A. Risk Factors\nThis is the real")

    sections = parse_sections(text, "10-K")

    risk_factors = next(s for s in sections if s.section_id == "10-K:1A")
    assert risk_factors.char_start == body_header_start
    assert risk_factors.text.startswith("Item 1A. Risk Factors\nThis is the real")


def test_fr005_parse_sections_10q_parts_and_short_body_kept() -> None:
    """AC3: 10-Q Part/Item ids come out in document order; a short real body survives."""
    text = (
        "PART I\n"
        "Item 2. Management Discussion\n"
        "Real MD&A content goes here, quite long, describing results of operations "
        "in detail.\n"
        "Item 4. Controls and Procedures\n"
        "Controls content here describing disclosure controls and procedures "
        "effectiveness.\n"
        "PART II\n"
        "Item 1. Legal Proceedings\n"
        "Legal proceedings content describing pending litigation matters in some "
        "detail.\n"
        "Item 1A. Risk Factors\n"
        "None.\n"
    )

    sections = parse_sections(text, "10-Q")

    assert [s.section_id for s in sections] == [
        "10-Q:I.2",
        "10-Q:I.4",
        "10-Q:II.1",
        "10-Q:II.1A",
    ]
    risk_factors = next(s for s in sections if s.section_id == "10-Q:II.1A")
    assert risk_factors.text == "Item 1A. Risk Factors\nNone.\n"


def test_fr005_parse_sections_no_headers_raises_parse_failed() -> None:
    """A filing with zero canonical sections raises PARSE_FAILED."""
    with pytest.raises(FathomError) as exc_info:
        parse_sections("no item headers anywhere in this text", "10-K")
    assert exc_info.value.code == Code.PARSE_FAILED


def test_fr005_sections_for_all_fixtures_cover_required_sections(data_dir: Path) -> None:
    """AC4: every 10-K yields 1A/7; every 10-Q yields I.2, across all 97 fixtures."""
    frame = pd.read_parquet(data_dir / "filings.parquet")
    assert len(frame) == 97

    failures: list[str] = []
    for _, row in frame.iterrows():
        accession = str(row["accession"])
        form = str(row["form"])
        if accession in AC4_ALLOWLIST:
            continue
        try:
            section_ids = {s.section_id for s in sections_for(accession, data_dir)}
        except FathomError as error:
            failures.append(f"{accession} ({form}): parse error {error.code}")
            continue

        required = {"10-K:1A", "10-K:7"} if form == "10-K" else {"10-Q:I.2"}
        missing = required - section_ids
        if missing:
            failures.append(f"{accession} ({form}): missing {sorted(missing)}")

    assert not failures, "\n".join(failures)


def test_fr005_sections_for_is_cached_and_slices_match(data_dir: Path) -> None:
    """AC5: sections_for is cached (same object) and Section.text matches the slice."""
    accession = "0000320193-25-000079"
    first = sections_for(accession, data_dir)
    second = sections_for(accession, data_dir)
    assert first is second

    frame = pd.read_parquet(data_dir / "filings.parquet")
    row = frame[frame["accession"] == accession].iloc[0]
    normalised = str(row["text"]).replace("\xa0", " ")
    for section in first:
        assert section.text == normalised[section.char_start : section.char_end]
        assert section.accession == accession


def test_fr005_period_end_handles_fiscal_and_quarterly_phrasing() -> None:
    """AC6: period_end parses fiscal-year and quarterly phrasing; None when absent."""
    assert period_end("For the fiscal year ended\nSeptember\xa027\n, 2025") == date(2025, 9, 27)
    assert period_end("For the quarterly period ended March 29, 2025") == date(2025, 3, 29)
    assert period_end("This filing has no period-end phrase at all.") is None


def test_fr005_canonical_sections_table_matches_lld() -> None:
    """CANONICAL_SECTIONS defines exactly the ids/titles/order from LLD §2.5."""
    assert list(CANONICAL_SECTIONS.items()) == [
        ("10-K:1", "Business"),
        ("10-K:1A", "Risk Factors"),
        ("10-K:1C", "Cybersecurity"),
        ("10-K:3", "Legal Proceedings"),
        ("10-K:7", "Management's Discussion and Analysis"),
        ("10-K:7A", "Market Risk"),
        ("10-K:9A", "Controls and Procedures"),
        ("10-Q:I.2", "Management's Discussion and Analysis"),
        ("10-Q:I.3", "Market Risk"),
        ("10-Q:I.4", "Controls and Procedures"),
        ("10-Q:II.1", "Legal Proceedings"),
        ("10-Q:II.1A", "Risk Factors"),
    ]


def test_fr005_section_is_a_pydantic_model() -> None:
    """Sanity check that Section round-trips as a plain pydantic model."""
    section = Section(
        accession="acc",
        section_id="10-K:1A",
        title="Risk Factors",
        text="Item 1A. Risk Factors\nBody.",
        char_start=0,
        char_end=27,
    )
    assert section.model_dump()["section_id"] == "10-K:1A"
