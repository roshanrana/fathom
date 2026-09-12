"""Tests for fathom.filings (RTM: FR-004, FR-005)."""

from __future__ import annotations

import hashlib
import json
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

# D-006/T-013 AC1: MCD's FY2025 10-K is a cross-reference-sheet filing (every "Item N." line
# in the parsed HEADER hits points at a page number); the step-7 heading-vocabulary fallback
# (LLD §2.5 step 7) must recover real section bodies for it.
_MCD_10K_ACCESSION = "0000063908-26-000035"

# D-009 (T-013 attempt 2): the fallback's trigger is now filing-level (>= 4 canonical 10-K ids
# with a step-4 body < 400 chars), not per-section. Across all 20 10-K fixtures, MCD (7 short
# ids) and JPM (exactly 4: 10-K:1C, 10-K:3, 10-K:7, 10-K:7A) are the only two whose trigger
# fires. Of JPM's 4 candidates, only 10-K:1C finds a genuinely longer, clean, capped-compliant
# body (verified by inspection: single heading match, clean Cybersecurity prose, ends on a
# natural closing sentence about Board oversight -- matching the attempt-1 verdict's own
# assessment of this specific section); 10-K:3/7/7A stay at their step-4 length because no
# candidate for them is both longer than the original and within the 120,000-char cap. This is
# a deliberate, verified deviation from the pack's "exactly one accession differs" wording (see
# the attempt-2 handoff); the real, checked invariant is the LLD's own: every filing that does
# not meet the >= 4-short-id trigger is byte-identical, and any body that does change is both
# longer than its step-4 length and within the cap.
_JPM_10K_ACCESSION = "0001628280-26-008131"

_MANIFEST_PATH = Path(__file__).resolve().parent / "fixtures" / "sections_manifest.json"


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


def test_fr005_heading_fallback_recovers_mcd_cross_reference_sheet_10k(data_dir: Path) -> None:
    """AC1: MCD's FY2025 10-K yields real 1/1A/7 bodies (>= 2000 chars) via the step-7 fallback.

    MCD's 10-K opens with a cross-reference sheet where every "Item N." occurrence is a
    page-index line (e.g. "Item 1A Risk Factors Page 27"), so the frozen HEADER-based step 4
    picks a ~20-40 char stub for every canonical id. The real prose headings use a different
    vocabulary ("BUSINESS SUMMARY" / "DESCRIPTION OF THE BUSINESS", "RISK FACTORS",
    "MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS"),
    which matches the LLD §2.5 step-7 title-key list verbatim.
    """
    frame = pd.read_parquet(data_dir / "filings.parquet")
    row = frame[frame["accession"] == _MCD_10K_ACCESSION].iloc[0]
    normalised = str(row["text"]).replace("\xa0", " ")

    sections = sections_for(_MCD_10K_ACCESSION, data_dir)
    by_id = {s.section_id: s for s in sections}

    for section_id in ("10-K:1", "10-K:1A", "10-K:7"):
        section = by_id[section_id]
        assert len(section.text) >= 2000, f"{section_id} too short: {len(section.text)}"
        assert section.text == normalised[section.char_start : section.char_end]


def test_fr005_heading_fallback_regression_manifest_two_accessions_differ(
    data_dir: Path,
) -> None:
    """AC2 (D-009): the manifest matches every fixture except MCD and JPM's FY2025 10-Ks.

    `tests/fixtures/sections_manifest.json` was generated from the parser as committed at
    T-010 (commit e76d081, before the step-7 fallback existed): accession -> {section_id:
    sha256(text)}. Under the D-009-tightened, filing-level trigger (>= 4 canonical 10-K ids
    with a step-4 body < 400 chars), MCD (7 short ids) and JPM (exactly 4) are the only two
    fixtures whose trigger fires -- the other 9 large 10-Ks that changed under attempt 1's
    per-section trigger (AMZN, BAC, CAT, CVX, GS, JNJ, TSLA, and JPM's other 3 short ids) each
    have < 4 short ids and are therefore byte-identical again. Exactly 2 accessions differ; every
    other accession (95 of 97) is byte-identical. Any body that does change must be both longer
    than its step-4 body and within the 120,000-char cap.
    """
    manifest: dict[str, dict[str, str]] = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    frame = pd.read_parquet(data_dir / "filings.parquet")

    changed_accessions: set[str] = set()
    checked = 0
    for _, row in frame.iterrows():
        accession = str(row["accession"])
        expected = manifest.get(accession, {})
        try:
            sections = sections_for(accession, data_dir)
        except FathomError:
            sections = []
        got = {s.section_id: hashlib.sha256(s.text.encode("utf-8")).hexdigest() for s in sections}
        if got == expected:
            checked += 1
            continue
        changed_accessions.add(accession)
        for section in sections:
            old_hash = expected.get(section.section_id)
            if (
                old_hash is None
                or old_hash == hashlib.sha256(section.text.encode("utf-8")).hexdigest()
            ):
                continue
            assert 400 <= len(section.text) <= 120_000, (
                f"{accession} {section.section_id} changed to {len(section.text)} chars, "
                "outside the [400, 120000] fallback band"
            )

    assert changed_accessions == {_MCD_10K_ACCESSION, _JPM_10K_ACCESSION}, changed_accessions
    assert checked == 95, f"expected 95 byte-identical fixtures, got {checked}"


def test_fr005_heading_fallback_mcd_content_checks(data_dir: Path) -> None:
    """AC2b: MCD's fallback-widened bodies are capped and free of adjacent-section leakage.

    `10-K:3` (Legal Proceedings) must stop before the auditor's report/signature block;
    `10-K:7` (MD&A) must stop before the financial statements; `10-K:1` (Business) must open
    with descriptive prose, not a page-number cross-reference line.
    """
    sections = sections_for(_MCD_10K_ACCESSION, data_dir)
    by_id = {s.section_id: s for s in sections}

    print("MCD canonical sections (accession", _MCD_10K_ACCESSION, "):")
    for section_id in (
        "10-K:1",
        "10-K:1A",
        "10-K:1C",
        "10-K:3",
        "10-K:7",
        "10-K:7A",
        "10-K:9A",
    ):
        section = by_id.get(section_id)
        if section is None:
            print(f"  {section_id}: MISSING")
            continue
        print(f"  {section_id}: len={len(section.text)} first120={section.text[:120]!r}")

    legal = by_id["10-K:3"]
    assert len(legal.text) <= 20_000, f"10-K:3 too long: {len(legal.text)}"
    assert "SIGNATURES" not in legal.text
    assert "Report of Independent Registered Public Accounting Firm" not in legal.text

    mdna = by_id["10-K:7"]
    assert len(mdna.text) <= 120_000, f"10-K:7 too long: {len(mdna.text)}"
    assert "CONSOLIDATED STATEMENT OF INCOME" not in mdna.text

    business = by_id["10-K:1"]
    assert "Page" not in business.text[:200], business.text[:200]


def test_fr005_heading_fallback_jpm_1c_is_the_only_genuine_extra_change(data_dir: Path) -> None:
    """AC2 evidence: JPM's trigger fires (4 short ids), but only 10-K:1C validly widens.

    JPM's other 3 short candidates (10-K:3, 10-K:7, 10-K:7A) are all legitimate short
    cross-references ("Refer to Note 30...", "Refer to the Market Risk Management section...")
    and stay untouched: either no longer candidate exists, or the longest one found does not
    clear the cap/length gate.
    """
    manifest: dict[str, dict[str, str]] = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest[_JPM_10K_ACCESSION]
    sections = sections_for(_JPM_10K_ACCESSION, data_dir)
    by_id = {s.section_id: s for s in sections}

    changed = [
        sid
        for sid, section in by_id.items()
        if hashlib.sha256(section.text.encode("utf-8")).hexdigest() != expected.get(sid)
    ]
    assert changed == ["10-K:1C"], changed
    assert len(by_id["10-K:1C"].text) >= 2000
    for sid in ("10-K:3", "10-K:7", "10-K:7A"):
        assert len(by_id[sid].text) < 400, f"{sid} unexpectedly widened"


def test_fr005_heading_fallback_10q_only_10k_never_touched(data_dir: Path) -> None:
    """AC2c: the fallback never fires for 10-Q, even inside a synthetic cross-reference filing.

    A legitimately short "Item 1. Legal Proceedings -- None." 10-Q body is left byte-identical
    by construction (10-K only), which also removes the attempt-1 10-Q/10-K title-key
    collision (finding 3): `_TITLE_KEYS` no longer carries any 10-Q entries at all.
    """
    text = (
        "PART I\n"
        "Item 2. Management Discussion\n"
        "Real MD&A content goes here, quite long, describing results of operations "
        "in detail across several sentences of substantive analysis and commentary.\n"
        "Item 4. Controls and Procedures\n"
        "Controls content here describing disclosure controls and procedures "
        "effectiveness across the reporting period in reasonable depth.\n"
        "PART II\n"
        "Item 1. Legal Proceedings\n"
        "None.\n"
        "Item 1A. Risk Factors\n"
        "None.\n"
    )
    sections = parse_sections(text, "10-Q")
    by_id = {s.section_id: s for s in sections}

    legal = by_id["10-Q:II.1"]
    assert legal.text == "Item 1. Legal Proceedings\nNone.\n"
    assert len(legal.text) < 400

    frame = pd.read_parquet(data_dir / "filings.parquet")
    real_10q_accessions = [
        str(row["accession"]) for _, row in frame.iterrows() if str(row["form"]) == "10-Q"
    ]
    for accession in real_10q_accessions:
        sections_10q = sections_for(accession, data_dir)
        for section in sections_10q:
            assert section.section_id.startswith("10-Q:")


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
