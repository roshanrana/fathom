"""Frozen output contracts (LLD §3).

`Briefing`/`Answer` are what Fathom returns to callers; `BriefingDraft`/`AnswerDraft` are
the shapes the LLM provider must return as JSON before being turned into claims.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from fathom.filings import Filing


class Source(BaseModel):
    """Where a claim's quote came from."""

    accession: str
    section_id: str


class Claim(BaseModel):
    """One cited, guard-checked statement in a briefing or answer."""

    text: str = Field(max_length=600)
    source: Source
    quote: str
    verified: bool = False
    guarded: bool = False


class Briefing(BaseModel):
    """Output of `fathom.briefing.brief()`."""

    ticker: str
    company: str
    generated_at: datetime
    provider: str
    model: str
    filings_used: list[Filing]
    business_snapshot: list[Claim]
    latest_results: list[Claim]
    risks: list[Claim]
    liquidity_capital: list[Claim]
    notable_disclosures: list[Claim]
    talking_points: list[Claim]
    claims_total: int
    claims_verified: int
    verified_share: float
    guard_hits: int
    disclaimer: str


class Answer(BaseModel):
    """Output of `fathom.ask.ask()`."""

    ticker: str
    question_sha256: str
    generated_at: datetime
    provider: str
    model: str
    claims: list[Claim]
    not_found: bool
    guard_hits: int
    disclaimer: str


class DraftClaim(BaseModel):
    """One claim as returned by the LLM provider, before verification/guarding."""

    model_config = ConfigDict(extra="ignore")

    text: str
    accession: str
    section_id: str
    quote: str


class BriefingDraft(BaseModel):
    """The JSON shape the provider must return for `brief()`."""

    model_config = ConfigDict(extra="ignore")

    business_snapshot: list[DraftClaim]
    latest_results: list[DraftClaim]
    risks: list[DraftClaim]
    liquidity_capital: list[DraftClaim]
    notable_disclosures: list[DraftClaim]
    talking_points: list[DraftClaim]


class AnswerDraft(BaseModel):
    """The JSON shape the provider must return for `ask()`."""

    model_config = ConfigDict(extra="ignore")

    claims: list[DraftClaim]
    not_found: bool = False
