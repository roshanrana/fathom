"""Briefing pipeline: capped context -> provider draft -> verified `Briefing` (LLD §2.10, §6.1-6.2).

Flow (frozen): context -> `provider.complete_json(SYSTEM_BRIEFING, user_json, max_tokens)` ->
`json.loads` (stripping a leading ```json fence if present) -> `BriefingDraft.model_validate` ->
on either failure, one retry whose user message adds `{"repair": "<error text>"}` -> second
failure raises `CONTRACT_INVALID` -> draft claims -> `Claim` with `verified = verify_claim(...)`
(unknown accession/section_id -> verified False) -> `scrub_claims` -> counts -> `audit.record` ->
`Briefing`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from fathom.audit import AuditRecord, record
from fathom.config import Settings
from fathom.contracts import Briefing, BriefingDraft, Claim, DraftClaim, Source
from fathom.data import company, load_frame, require_ticker
from fathom.errors import Code, FathomError
from fathom.filings import Filing, filings_for, sections_for
from fathom.guard import scrub_claims, verify_claim
from fathom.live import data_dir_for
from fathom.prompts import SECTION_CAPS, SYSTEM_BRIEFING
from fathom.providers import Provider, ProviderResult, make_provider

logger = logging.getLogger("fathom")

_CODE_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_INPUT_VALUE_SEGMENT = re.compile(r"input_value=.*?(?=, input_type=)", re.S)
_REPAIR_ERROR_MAX = 300
_FULL_TEXT_CAP = 8000
_MAX_REPAIR_ATTEMPTS = 2
_CLAIM_TEXT_CAP = 600
_CLAIM_TEXT_TRUNCATED_LEN = 599
_CLAIM_QUOTE_CAP = 2000
_ELLIPSIS = "…"

_DRAFT_FIELDS: tuple[str, ...] = (
    "business_snapshot",
    "latest_results",
    "risks",
    "liquidity_capital",
    "notable_disclosures",
    "talking_points",
)


class Excerpt(BaseModel):
    """One capped filing-section excerpt included in the briefing prompt (LLD §6.2)."""

    accession: str
    section_id: str
    title: str
    text: str


class BriefingContext(BaseModel):
    """The capped context assembled for one `brief()` call (LLD §2.10, §6.2)."""

    ticker: str
    company: str
    as_of: date
    filings: list[Filing]
    excerpts: list[Excerpt]

    def to_user_json(self) -> str:
        """Serialise to the exact `{"task":"briefing", ...}` shape from LLD §6.2."""
        payload = {
            "task": "briefing",
            "ticker": self.ticker,
            "company": self.company,
            "as_of": self.as_of.isoformat(),
            "filings": [
                {
                    "accession": filing.accession,
                    "form": filing.form,
                    "filing_date": filing.filing_date.isoformat(),
                    "period_end": filing.period_end.isoformat() if filing.period_end else None,
                }
                for filing in self.filings
            ],
            "excerpts": [
                {
                    "accession": excerpt.accession,
                    "section_id": excerpt.section_id,
                    "title": excerpt.title,
                    "text": excerpt.text,
                }
                for excerpt in self.excerpts
            ],
        }
        return json.dumps(payload, ensure_ascii=False)


def _cap_text(text: str, cap: int) -> str:
    """Cut `text` to at most `cap` characters, backing off to the last sentence end."""
    if len(text) <= cap:
        return text
    truncated = text[:cap]
    cut_at: int | None = None
    for match in _SENTENCE_END.finditer(truncated):
        cut_at = match.end()
    return truncated if cut_at is None else truncated[:cut_at]


def _full_text_excerpt(filing: Filing, data_dir: Path) -> Excerpt:
    """Fallback excerpt for a filing with zero canonical sections (should not happen)."""
    frame = load_frame("filings", data_dir)
    rows = frame[frame["accession"] == filing.accession]
    text = str(rows.iloc[0]["text"])
    return Excerpt(
        accession=filing.accession,
        section_id=f"{filing.form}:FULL",
        title=filing.form,
        text=text[:_FULL_TEXT_CAP],
    )


def _excerpts_for_filing(filing: Filing, data_dir: Path) -> list[Excerpt]:
    """Capped, canonical-section excerpts for one filing (LLD §6.2)."""
    try:
        sections = sections_for(filing.accession, data_dir)
    except FathomError as exc:
        if exc.code is not Code.PARSE_FAILED:
            raise
        return [_full_text_excerpt(filing, data_dir)]

    return [
        Excerpt(
            accession=filing.accession,
            section_id=section.section_id,
            title=section.title,
            text=_cap_text(section.text, SECTION_CAPS[section.section_id]),
        )
        for section in sections
    ]


def _as_of_date(ticker: str, data_dir: Path) -> date:
    """The bars' max date for `ticker` (LLD §6.2's `as_of`)."""
    bars = load_frame("bars", data_dir)
    rows = bars[bars["symbol"] == ticker]
    if rows.empty:
        raise FathomError(Code.DATA_MISSING, f"no bars for {ticker!r}", {"name": "bars"})
    max_date: date = rows["date"].max()
    return max_date


def build_context(ticker: str, data_dir: Path) -> BriefingContext:
    """Assemble the capped briefing context: the newest 10-K plus the two newest 10-Qs."""
    symbol = require_ticker(ticker)
    filings = filings_for(symbol, data_dir)  # newest first

    ten_k = next((filing for filing in filings if filing.form == "10-K"), None)
    if ten_k is None:
        raise FathomError(Code.DATA_MISSING, f"no 10-K on file for {symbol!r}", {"name": "filings"})
    ten_qs = [filing for filing in filings if filing.form == "10-Q"][:2]
    filings_used = [ten_k, *ten_qs]

    excerpts: list[Excerpt] = []
    for filing in filings_used:
        excerpts.extend(_excerpts_for_filing(filing, data_dir))

    return BriefingContext(
        ticker=symbol,
        company=company(symbol, data_dir).name,
        as_of=_as_of_date(symbol, data_dir),
        filings=filings_used,
        excerpts=excerpts,
    )


def _strip_code_fence(text: str) -> str:
    """Strip a leading/trailing ```json fence if present, otherwise return `text` stripped."""
    stripped = text.strip()
    match = _CODE_FENCE.match(stripped)
    return match.group(1) if match else stripped


def _parse_draft(raw_text: str) -> BriefingDraft:
    """`json.loads` (fence-stripped) then `BriefingDraft.model_validate`."""
    payload = json.loads(_strip_code_fence(raw_text))
    return BriefingDraft.model_validate(payload)


def _repair_error_text(exc: Exception) -> str:
    """Build the `"repair"` error string from `exc`'s class/location only (T-006 F2).

    `str(ValidationError)` can embed a (possibly truncated) `repr()` of the offending
    `input_value`, echoing the model's own prior output back into the retry prompt. Strip any
    `input_value=...` segment before truncating, so the repair message never carries it.
    """
    sanitized = _INPUT_VALUE_SEGMENT.sub("input_value=<removed>", str(exc))
    return f"{type(exc).__name__}: {sanitized[:_REPAIR_ERROR_MAX]}"


def _obtain_draft(
    provider: Provider, user_text: str, max_tokens: int
) -> tuple[ProviderResult, BriefingDraft, str]:
    """Call `provider`, parse/validate, retrying once with a `"repair"` message on failure.

    Returns the `ProviderResult`, the validated draft, and the user text of whichever attempt
    succeeded. Raises `CONTRACT_INVALID` (`details={"attempt": 2}`) after a second failure.
    """
    result = provider.complete_json(SYSTEM_BRIEFING, user_text, max_tokens)
    try:
        return result, _parse_draft(result.text), user_text
    except (json.JSONDecodeError, ValidationError) as exc:
        error_text = _repair_error_text(exc)

    repair_payload = json.loads(user_text)
    repair_payload["repair"] = error_text
    repair_text = json.dumps(repair_payload, ensure_ascii=False)

    result = provider.complete_json(SYSTEM_BRIEFING, repair_text, max_tokens)
    try:
        return result, _parse_draft(result.text), repair_text
    except (json.JSONDecodeError, ValidationError) as exc:
        raise FathomError(
            Code.CONTRACT_INVALID,
            "briefing draft failed contract validation after one repair attempt",
            {"attempt": _MAX_REPAIR_ATTEMPTS},
        ) from exc


def _truncate_claim_fields(text: str, quote: str) -> tuple[str, str]:
    """Cap `text`/`quote` to the `Claim` contract's bounds so conversion never raises (D-007).

    `text` over 600 characters is cut to 599 plus an ellipsis; `quote` over 2 000 characters is
    cut to 2 000 (which then fails `verify_claim`'s word-count check on its own).
    """
    if len(text) > _CLAIM_TEXT_CAP:
        text = text[:_CLAIM_TEXT_TRUNCATED_LEN] + _ELLIPSIS
    if len(quote) > _CLAIM_QUOTE_CAP:
        quote = quote[:_CLAIM_QUOTE_CAP]
    return text, quote


def _to_claim(draft_claim: DraftClaim, lookup: dict[tuple[str, str], str]) -> Claim:
    """Turn one `DraftClaim` into a `Claim`, verifying its quote against the cited excerpt."""
    text, quote = _truncate_claim_fields(draft_claim.text, draft_claim.quote)
    section_text = lookup.get((draft_claim.accession, draft_claim.section_id))
    verified = section_text is not None and verify_claim(quote, section_text)
    return Claim(
        text=text,
        source=Source(accession=draft_claim.accession, section_id=draft_claim.section_id),
        quote=quote,
        verified=verified,
    )


def _claims_from_draft(draft: BriefingDraft, context: BriefingContext) -> dict[str, list[Claim]]:
    """One `Claim` list per `BriefingDraft` field, verified against `context`'s excerpts."""
    lookup = {(excerpt.accession, excerpt.section_id): excerpt.text for excerpt in context.excerpts}
    draft_fields: dict[str, list[DraftClaim]] = {
        "business_snapshot": draft.business_snapshot,
        "latest_results": draft.latest_results,
        "risks": draft.risks,
        "liquidity_capital": draft.liquidity_capital,
        "notable_disclosures": draft.notable_disclosures,
        "talking_points": draft.talking_points,
    }
    return {
        field_name: [_to_claim(draft_claim, lookup) for draft_claim in draft_claims]
        for field_name, draft_claims in draft_fields.items()
    }


def brief(ticker: str, settings: Settings, provider: Provider | None = None) -> Briefing:
    """Build a verified, guard-scrubbed `Briefing` for `ticker` (LLD §2.10)."""
    active_provider = provider if provider is not None else make_provider(settings)
    context = build_context(ticker, data_dir_for(ticker, settings))
    user_json = context.to_user_json()

    result, draft, final_user_text = _obtain_draft(
        active_provider, user_json, settings.max_tokens_brief
    )

    claims_by_field = _claims_from_draft(draft, context)
    guard_hits_total = 0
    scrubbed_by_field: dict[str, list[Claim]] = {}
    for field_name, claims in claims_by_field.items():
        scrubbed, hits = scrub_claims(claims)
        scrubbed_by_field[field_name] = scrubbed
        guard_hits_total += hits

    claims_total = sum(len(claims) for claims in scrubbed_by_field.values())
    claims_verified = sum(
        1 for claims in scrubbed_by_field.values() for claim in claims if claim.verified
    )
    verified_share = claims_verified / claims_total if claims_total else 0.0

    generated_at = datetime.now(UTC)
    prompt_sha256 = hashlib.sha256(f"{SYSTEM_BRIEFING}\n{final_user_text}".encode()).hexdigest()
    response_sha256 = hashlib.sha256(result.text.encode()).hexdigest()

    briefing = Briefing(
        ticker=context.ticker,
        company=context.company,
        generated_at=generated_at,
        provider=active_provider.name,
        model=active_provider.model,
        filings_used=context.filings,
        business_snapshot=scrubbed_by_field["business_snapshot"],
        latest_results=scrubbed_by_field["latest_results"],
        risks=scrubbed_by_field["risks"],
        liquidity_capital=scrubbed_by_field["liquidity_capital"],
        notable_disclosures=scrubbed_by_field["notable_disclosures"],
        talking_points=scrubbed_by_field["talking_points"],
        claims_total=claims_total,
        claims_verified=claims_verified,
        verified_share=verified_share,
        guard_hits=guard_hits_total,
        disclaimer=settings.disclaimer,
    )

    record(
        settings,
        AuditRecord(
            ts=generated_at,
            ticker=context.ticker,
            purpose="brief",
            provider=active_provider.name,
            model=active_provider.model,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            prompt_sha256=prompt_sha256,
            response_sha256=response_sha256,
            claims_total=claims_total,
            claims_verified=claims_verified,
            guard_hits=guard_hits_total,
            prompt=final_user_text,
            response=result.text,
        ),
    )

    logger.info(
        "brief ticker=%s provider=%s latency_ms=%d claims=%d verified=%d guard_hits=%d",
        context.ticker,
        active_provider.name,
        result.latency_ms,
        claims_total,
        claims_verified,
        guard_hits_total,
    )

    return briefing
