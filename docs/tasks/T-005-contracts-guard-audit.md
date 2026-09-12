---
id: T-005
title: Contracts, guard and audit
milestone: M2
risk: medium
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-002]
rtm: [FR-007, FR-008, FR-011, NFR-006, NFR-008]
status: done
---
# T-005 — Contracts, guard and audit

## Goal
The frozen output contracts (`fathom.contracts`), the advice guard and citation verifier
(`fathom.guard`), and the append-only audit writer with never-log rules (`fathom.audit`).

## Spec references
`03-lld.md §3` (contracts, verbatim):
```python
from fathom.filings import Filing
class Source(BaseModel): accession: str; section_id: str
class Claim(BaseModel):
    text: str = Field(max_length=600); source: Source; quote: str; verified: bool = False; guarded: bool = False
class Briefing(BaseModel):
    ticker: str; company: str; generated_at: datetime; provider: str; model: str
    filings_used: list[Filing]
    business_snapshot: list[Claim]; latest_results: list[Claim]; risks: list[Claim]
    liquidity_capital: list[Claim]; notable_disclosures: list[Claim]; talking_points: list[Claim]
    claims_total: int; claims_verified: int; verified_share: float; guard_hits: int; disclaimer: str
class Answer(BaseModel):
    ticker: str; question_sha256: str; generated_at: datetime; provider: str; model: str
    claims: list[Claim]; not_found: bool; guard_hits: int; disclaimer: str
class DraftClaim(BaseModel): text: str; accession: str; section_id: str; quote: str
class BriefingDraft(BaseModel): business_snapshot: list[DraftClaim]; latest_results: list[DraftClaim]; risks: list[DraftClaim]; liquidity_capital: list[DraftClaim]; notable_disclosures: list[DraftClaim]; talking_points: list[DraftClaim]
class AnswerDraft(BaseModel): claims: list[DraftClaim]; not_found: bool = False
```
Drafts use `model_config = ConfigDict(extra="ignore")`. `03-lld.md §2.8` guard:
`ADVICE_PATTERNS` = the 14 regexes in LLD §6.4 (case-insensitive); `is_advice(text)`;
`normalise(text)` = casefold, map “ ” ‘ ’ to " and ', collapse whitespace, strip;
`verify_claim(quote, section_text)` = 6 ≤ words(quote) ≤ 60 and normalise(quote) in
normalise(section_text); `scrub_claims(claims)` → flagged claims get `text=GUARD_NOTICE`,
`guarded=True`, `verified=False`; returns `(claims, hits)`; `GUARD_NOTICE = "[removed:
recommendation-style language is not permitted in Fathom output]"`. `§2.9` audit:
`AuditRecord` fields ts, ticker, purpose ∈ {brief, ask, probe}, provider, model, latency_ms,
input_tokens, output_tokens, prompt_sha256, response_sha256, claims_total, claims_verified,
guard_hits, prompt: str | None = None, response: str | None = None (bodies only when
`settings.audit_bodies`); `record(settings, rec)` mkdirs, appends one JSON line, failure →
`AUDIT_WRITE` with the path. Benign phrases (must not trigger) listed in LLD §6.4.

## Scope (files this task may touch)
- fathom/contracts.py, fathom/guard.py, fathom/audit.py
- tests/test_contracts.py, tests/test_guard.py, tests/test_audit.py

## Acceptance criteria
- AC1: `Briefing`/`Answer`/drafts round-trip through `model_dump_json`/`model_validate_json`; `BriefingDraft.model_validate({"business_snapshot": [], …, "extra": 1})` ignores the extra key; a draft missing a required list fails validation.
- AC2: Every adversarial phrase in a test list of ≥ 25 (covering all 14 patterns, e.g. "You should buy this stock", "Strong buy rating", "We recommend investors purchase shares", "Price target of $300", "Overweight", "The stock is undervalued", "Is it a good investment?", "Will the stock go up?", "Bullish on the name", "Top pick", "Should I sell?") returns `is_advice == True`; every benign phrase in LLD §6.4 plus at least seven more (e.g. "Net sales increased 5% year over year.", "The Company repurchased $20 billion of common stock.", "Item 1A describes material risks.", "We hold cash and marketable securities.", "Customers may buy through resellers.", "The board sold its interest in the joint venture.", "Interest rate risk is described in Item 7A.") returns False.
- AC3: `verify_claim` is True for a quote with curly quotes and extra whitespace against a section with straight quotes and newlines; False when the quote has 5 words or 61 words; False when one word differs.
- AC4: `scrub_claims` replaces flagged claims' text with `GUARD_NOTICE`, sets `guarded=True`, `verified=False`, keeps the source, returns the hit count; unflagged claims are returned unchanged (equality) and the input list is not mutated.
- AC5: `record` writes one JSON line per call to `settings.audit_path` under a temp dir (creating parents); with `audit_bodies=False` the line contains no `prompt`/`response` keys with non-null values even if the record carried them (the writer drops them); with `audit_bodies=True` they are kept; an unwritable path (a file where a directory is needed) raises `AUDIT_WRITE` naming the path.
- AC6: Never-log test: with a capturing log handler on logger `fathom`, calling `record` and the guard functions produces no record containing the strings "sk-ant-", "PORTKEY", the prompt body, or the question text passed in.
- AC7: mypy strict clean; tests named `test_fr007_*`, `test_fr008_*`, `test_fr011_*`, `test_nfr006_*`, `test_nfr008_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_contracts.py tests/test_guard.py tests/test_audit.py -q`
- `uv run ruff check fathom/contracts.py fathom/guard.py fathom/audit.py tests && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] error taxonomy used (AUDIT_WRITE)
- [ ] never-log list honoured
- [ ] tests named with RTM IDs
- [ ] no new dependencies
- [ ] patterns match LLD §6.4 exactly (count = 14)

## Threat-model boundary touched
B1 (advice elicitation), B4 (audit contents) — Security Reviewer at T2.

## Handoff (Implementer fills, ≤10 lines)
- Implemented: `fathom/contracts.py` (Source/Claim/Briefing/Answer/DraftClaim/BriefingDraft/AnswerDraft, extra="ignore" on drafts); `fathom/guard.py` (14 frozen ADVICE_PATTERNS, is_advice, normalise, verify_claim, scrub_claims, GUARD_NOTICE, no logging); `fathom/audit.py` (AuditRecord, record() with mkdirs, body-dropping, AUDIT_WRITE on OSError, single `audit written path=%s` INFO log).
- Files changed: fathom/contracts.py, fathom/guard.py, fathom/audit.py, tests/test_contracts.py, tests/test_guard.py, tests/test_audit.py.
- Tests run: `pytest tests/test_contracts.py tests/test_guard.py tests/test_audit.py -q` → 63 passed (6 contracts, 52 guard incl. 32 adversarial + 12 benign parametrized, 5 audit). Full gate `uv run python scripts/check.py` → all checks passed (147 total tests, 97.5% coverage; contracts/guard/audit each 100%).
- Deviations: none from spec text; test names use `test_fr007_*` (contracts), `test_fr008_*`/`test_nfr008_*` (guard), `test_fr011_*`/`test_nfr006_*` (audit) per AC7.
- Open questions: none. One fix mid-task — `ruff format` reformatted 3 files (whitespace only, no logic change) and the never-log test's placeholder token had to be shortened (`sk-ant-q1` etc.) so `scripts/secrets_scan.py`'s `sk-ant-[A-Za-z0-9_-]{10,}` pattern didn't flag the fake secret in test source; behavior asserted is unchanged.
- Budget actual: ~45k input tokens, ~35 tool calls, ~30 min wall clock.
