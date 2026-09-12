"""Contract round-trip tests (LLD §3, frozen). RTM: FR-007."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from fathom.contracts import (
    Answer,
    AnswerDraft,
    Briefing,
    BriefingDraft,
    Claim,
    DraftClaim,
    Source,
)
from fathom.filings import Filing


def _filing() -> Filing:
    return Filing(
        ticker="AAPL",
        cik="320193",
        company_name="Apple Inc.",
        form="10-K",
        filing_date=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        accession="0000320193-24-000123",
        edgar_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/",
        n_chars=123456,
    )


def _claim() -> Claim:
    return Claim(
        text="Net sales increased 5% year over year.",
        source=Source(accession="0000320193-24-000123", section_id="10-K:7"),
        quote="Net sales increased 5% year over year.",
        verified=True,
        guarded=False,
    )


def test_fr007_briefing_round_trips_through_json() -> None:
    briefing = Briefing(
        ticker="AAPL",
        company="Apple Inc.",
        generated_at=datetime(2024, 11, 2, 12, 0, 0),
        provider="offline",
        model="offline-fixture",
        filings_used=[_filing()],
        business_snapshot=[_claim()],
        latest_results=[_claim()],
        risks=[_claim()],
        liquidity_capital=[_claim()],
        notable_disclosures=[_claim()],
        talking_points=[_claim()],
        claims_total=6,
        claims_verified=6,
        verified_share=1.0,
        guard_hits=0,
        disclaimer="disclaimer text",
    )
    restored = Briefing.model_validate_json(briefing.model_dump_json())
    assert restored == briefing


def test_fr007_answer_round_trips_through_json() -> None:
    answer = Answer(
        ticker="AAPL",
        question_sha256="a" * 64,
        generated_at=datetime(2024, 11, 2, 12, 0, 0),
        provider="offline",
        model="offline-fixture",
        claims=[_claim()],
        not_found=False,
        guard_hits=0,
        disclaimer="disclaimer text",
    )
    restored = Answer.model_validate_json(answer.model_dump_json())
    assert restored == answer


def test_fr007_briefing_draft_round_trips_through_json() -> None:
    draft_claim = DraftClaim(
        text="Net sales increased.",
        accession="0000320193-24-000123",
        section_id="10-K:7",
        quote="Net sales increased 5% year over year.",
    )
    draft = BriefingDraft(
        business_snapshot=[draft_claim],
        latest_results=[],
        risks=[],
        liquidity_capital=[],
        notable_disclosures=[],
        talking_points=[],
    )
    restored = BriefingDraft.model_validate_json(draft.model_dump_json())
    assert restored == draft


def test_fr007_answer_draft_round_trips_through_json() -> None:
    draft = AnswerDraft(claims=[], not_found=True)
    restored = AnswerDraft.model_validate_json(draft.model_dump_json())
    assert restored == draft


def test_fr007_briefing_draft_ignores_extra_keys() -> None:
    draft = BriefingDraft.model_validate(
        {
            "business_snapshot": [],
            "latest_results": [],
            "risks": [],
            "liquidity_capital": [],
            "notable_disclosures": [],
            "talking_points": [],
            "extra": 1,
        }
    )
    assert draft.business_snapshot == []
    assert draft.talking_points == []


def test_fr007_briefing_draft_missing_required_list_fails_validation() -> None:
    with pytest.raises(ValidationError):
        BriefingDraft.model_validate(
            {
                "business_snapshot": [],
                "latest_results": [],
                "risks": [],
                "liquidity_capital": [],
                "notable_disclosures": [],
                # talking_points intentionally omitted
            }
        )
