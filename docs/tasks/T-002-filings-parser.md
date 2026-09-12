---
id: T-002
title: Filings list and section parser
milestone: M1
risk: low
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-000]
rtm: [FR-004, FR-005]
status: todo
---
# T-002 — Filings list and section parser

## Goal
`fathom.filings` lists a ticker's filings newest first with EDGAR links and parses every
filing into the canonical SEC sections, dropping table-of-contents occurrences, with a test that
proves coverage over all 97 fixture filings.

## Spec references
`03-lld.md §2.5` — signatures:
```python
class Filing(BaseModel): ticker: str; cik: str; company_name: str; form: Literal["10-K","10-Q"]; filing_date: date; period_end: date | None; accession: str; edgar_url: str; n_chars: int
class Section(BaseModel): accession: str; section_id: str; title: str; text: str; char_start: int; char_end: int
def filings_for(ticker: str, data_dir: Path) -> list[Filing]              # newest first
def edgar_url(cik: str, accession: str) -> str   # https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-','')}/
@functools.cache
def sections_for(accession: str, data_dir: Path) -> list[Section]         # canonical sections only, document order
def parse_sections(text: str, form: str) -> list[Section]                  # pure; accession filled by caller
def period_end(text: str) -> date | None
```
Canonical ids/titles: 10-K → `10-K:1` Business, `10-K:1A` Risk Factors, `10-K:1C` Cybersecurity,
`10-K:3` Legal Proceedings, `10-K:7` Management's Discussion and Analysis, `10-K:7A` Market Risk,
`10-K:9A` Controls and Procedures; 10-Q → `10-Q:I.2` MD&A, `10-Q:I.3` Market Risk, `10-Q:I.4`
Controls and Procedures, `10-Q:II.1` Legal Proceedings, `10-Q:II.1A` Risk Factors. Define the table
in `fathom/filings.py` as `CANONICAL_SECTIONS: dict[str, str]` (id → title, in the order above).
(T-004 defines the same constant in `fathom/prompts.py` for the prompt layer; T-006 asserts the
two are equal. Do not create or touch `prompts.py` in this task.)
Parser algorithm (frozen, LLD §2.5 steps 1–6): replace `\xa0`; `HEADER =
re.compile(r"^[ \t]*item[ \t]+(\d{1,2}[a-c]?)[ \t]*[.:\-—–]?[ \t]*([^\n]{0,120})$", re.I | re.M)`;
`PART = re.compile(r"^[ \t]*part[ \t]+(i{1,2})\b", re.I | re.M)` (10-Q only, default part I);
body = end of header line → next header; group by `(part, item.upper())`; keep the occurrence
with the longest body; emit canonical ids in document order; zero canonical sections →
`PARSE_FAILED`. `period_end`: first 4 000 chars, `re.compile(r"for the (?:fiscal|quarterly)?\s*(?:year|period)\s+ended\s+([A-Z][a-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})", re.I | re.S)`.

## Scope (files this task may touch)
- fathom/filings.py
- tests/test_filings.py

## Acceptance criteria
- AC1: `filings_for("AAPL", data_dir)` returns 5 filings newest first; the first is the 10-Q filed 2026-05-01; the 10-K has accession `0000320193-25-000079`, `edgar_url == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/"`, `period_end == date(2025, 9, 27)`.
- AC2: On a synthetic text containing a table of contents ("Item 1A. Risk Factors 5") followed by a real "Item 1A. Risk Factors" body, the parser returns the body occurrence with `char_start` at the body header.
- AC3: On a synthetic 10-Q with "PART I … Item 2 … Item 4 … PART II … Item 1 … Item 1A", ids are exactly `10-Q:I.2`, `10-Q:I.4`, `10-Q:II.1`, `10-Q:II.1A` in that order; a 10-Q whose Part II Item 1A says only "None." still yields the section with that text.
- AC4: Coverage over the fixtures: every 10-K yields `10-K:1A` and `10-K:7`; every 10-Q yields `10-Q:I.2`; the test iterates all 97 accessions (it may take several seconds; keep it one test). If a fixture genuinely lacks a section, the test may list that accession in an explicit allowlist with a one-line reason — the allowlist must be empty or documented in the handoff.
- AC5: `sections_for` is cached and returns the same object on repeated calls; `Section.text` slices equal `normalised_text[char_start:char_end]`.
- AC6: `period_end` handles "For the fiscal year ended\nSeptember 27\n, 2025" and "For the quarterly period ended March 29, 2025"; returns None when absent.
- AC7: mypy strict clean; tests named `test_fr004_*`, `test_fr005_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_filings.py -q`
- `uv run ruff check fathom/filings.py tests/test_filings.py && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] error taxonomy used (PARSE_FAILED)
- [ ] no filing text logged
- [ ] tests named with RTM IDs
- [ ] no new dependencies
- [ ] allowlist in AC4 empty or justified

## Threat-model boundary touched
B3 (fixture text is untrusted data; the parser never evaluates it).

## Handoff (Implementer fills, ≤10 lines)
