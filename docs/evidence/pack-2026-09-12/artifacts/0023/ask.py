"""Grounded Q&A flow (LLD §2.10, §3, §6.2, §6.5, §9).

`ask()` runs the input guard first (an advice-shaped question never reaches retrieval or the
provider), then BM25 retrieval, then the provider, verifying every returned claim against the
full cited section text (not just the retrieved chunk) before scrubbing and auditing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fathom import guard, retrieval
from fathom.audit import AuditRecord, record
from fathom.config import Settings
from fathom.contracts import Answer, AnswerDraft, Claim, DraftClaim, Source
from fathom.errors import Code, FathomError
from fathom.filings import filings_for, sections_for
from fathom.live import data_dir_for
from fathom.prompts import CANONICAL_SECTIONS, SYSTEM_ASK
from fathom.providers import Provider, make_provider

logger = logging.getLogger("fathom")

_REPAIR_MESSAGE_MAX_CHARS = 300
_JSON_FENCE_PREFIX = "```json"
_JSON_FENCE_SUFFIX = "```"
_INPUT_VALUE_SEGMENT = re.compile(r"input_value=.*?(?=, input_type=)", re.S)
_CLAIM_TEXT_CAP = 600
_CLAIM_TEXT_TRUNCATED_LEN = 599
_CLAIM_QUOTE_CAP = 2000
_ELLIPSIS = "…"


def _repair_error_text(exc: Exception) -> str:
    """Build the `"repair"` error string from `exc`'s class/location only (T-006 F2).

    `str(ValidationError)` can embed a (possibly truncated) `repr()` of the offending
    `input_value`, echoing the model's own prior output back into the retry prompt. Strip any
    `input_value=...` segment before truncating, so the repair message never carries it.
    """
    sanitized = _INPUT_VALUE_SEGMENT.sub("input_value=<removed>", str(exc))
    return f"{type(exc).__name__}: {sanitized[:_REPAIR_MESSAGE_MAX_CHARS]}"


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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_json_fence(text: str) -> str:
    """Strip a leading ```json fence (and matching trailing fence) if present."""
    stripped = text.strip()
    if stripped.startswith(_JSON_FENCE_PREFIX):
        stripped = stripped[len(_JSON_FENCE_PREFIX) :].strip()
        if stripped.endswith(_JSON_FENCE_SUFFIX):
            stripped = stripped[: -len(_JSON_FENCE_SUFFIX)].strip()
    return stripped


def _parse_answer_draft(text: str) -> AnswerDraft:
    """Parse a provider completion into an `AnswerDraft`; raises on any failure."""
    payload = json.loads(_strip_json_fence(text))
    return AnswerDraft.model_validate(payload)


def _guarded_answer(ticker: str, question_sha256: str, settings: Settings) -> Answer:
    claim = Claim(
        text=guard.GUARD_NOTICE,
        source=Source(accession="", section_id=""),
        quote="",
        verified=False,
        guarded=True,
    )
    return Answer(
        ticker=ticker,
        question_sha256=question_sha256,
        generated_at=datetime.now(UTC),
        provider="guard",
        model="-",
        claims=[claim],
        not_found=False,
        guard_hits=1,
        disclaimer=settings.disclaimer,
    )


def _not_found_answer(ticker: str, question_sha256: str, settings: Settings) -> Answer:
    return Answer(
        ticker=ticker,
        question_sha256=question_sha256,
        generated_at=datetime.now(UTC),
        provider="none",
        model="-",
        claims=[],
        not_found=True,
        guard_hits=0,
        disclaimer=settings.disclaimer,
    )


def _audit_no_call(
    settings: Settings,
    *,
    ticker: str,
    provider: str,
    latency_ms: int,
    claims_total: int,
    claims_verified: int,
    guard_hits: int,
) -> None:
    """Audit a no-provider-call path (guard or zero-hit) with empty prompt/response hashes."""
    record(
        settings,
        AuditRecord(
            ts=datetime.now(UTC),
            ticker=ticker,
            purpose="ask",
            provider=provider,
            model="-",
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            prompt_sha256=_sha256(""),
            response_sha256=_sha256(""),
            claims_total=claims_total,
            claims_verified=claims_verified,
            guard_hits=guard_hits,
        ),
    )


def _log_ask(ticker: str, provider: str, hits: int, not_found: bool, latency_ms: int) -> None:
    logger.info(
        "ask ticker=%s provider=%s hits=%d not_found=%s latency_ms=%d",
        ticker,
        provider,
        hits,
        not_found,
        latency_ms,
    )


def _section_text_index(accessions: set[str], data_dir: Path) -> dict[tuple[str, str], str]:
    """Map (accession, section_id) -> full section text for verification.

    An accession with no parseable/known sections (e.g. `DATA_MISSING`) is simply skipped;
    claims citing it fall through to `verified = False`.
    """
    index: dict[tuple[str, str], str] = {}
    for accession in accessions:
        try:
            sections = sections_for(accession, data_dir)
        except FathomError:
            continue
        for section in sections:
            index[(accession, section.section_id)] = section.text
    return index


def _claims_from_draft(
    draft_claims: list[DraftClaim], section_text_by_key: dict[tuple[str, str], str]
) -> list[Claim]:
    claims: list[Claim] = []
    for draft_claim in draft_claims:
        text, quote = _truncate_claim_fields(draft_claim.text, draft_claim.quote)
        section_text = section_text_by_key.get((draft_claim.accession, draft_claim.section_id))
        verified = section_text is not None and guard.verify_claim(quote, section_text)
        claims.append(
            Claim(
                text=text,
                source=Source(accession=draft_claim.accession, section_id=draft_claim.section_id),
                quote=quote,
                verified=verified,
                guarded=False,
            )
        )
    return claims


class _DraftResult:
    """The outcome of `_complete_answer_draft`: the parsed draft plus what to audit."""

    def __init__(
        self,
        draft: AnswerDraft,
        prompt_json: str,
        response_text: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        self.draft = draft
        self.prompt_json = prompt_json
        self.response_text = response_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def _complete_answer_draft(
    active_provider: Provider, user_payload: dict[str, Any], max_tokens: int
) -> _DraftResult:
    """Call the provider for an `AnswerDraft`, with one repair retry (LLD §2.10)."""
    user_json = json.dumps(user_payload)
    result = active_provider.complete_json(SYSTEM_ASK, user_json, max_tokens)
    try:
        draft = _parse_answer_draft(result.text)
        return _DraftResult(
            draft, user_json, result.text, result.input_tokens, result.output_tokens
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        repair_payload = {**user_payload, "repair": _repair_error_text(exc)}
        repair_user_json = json.dumps(repair_payload)
        repair_result = active_provider.complete_json(SYSTEM_ASK, repair_user_json, max_tokens)
        try:
            draft = _parse_answer_draft(repair_result.text)
            return _DraftResult(
                draft,
                repair_user_json,
                repair_result.text,
                repair_result.input_tokens,
                repair_result.output_tokens,
            )
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise FathomError(
                Code.CONTRACT_INVALID,
                "provider returned an invalid AnswerDraft after one repair attempt",
                {"attempt": 2},
            ) from exc2


def ask(
    ticker: str,
    question: str,
    settings: Settings,
    provider: Provider | None = None,
    k: int = 6,
) -> Answer:
    """Answer `question` about `ticker`'s filings, grounded in retrieved excerpts (LLD §2.10).

    The question text itself is never logged or audited; only its sha256 appears on the
    returned `Answer`.
    """
    start = time.monotonic()
    question_sha256 = _sha256(question)

    if guard.is_advice(question):
        answer = _guarded_answer(ticker, question_sha256, settings)
        latency_ms = int((time.monotonic() - start) * 1000)
        _audit_no_call(
            settings,
            ticker=ticker,
            provider="guard",
            latency_ms=latency_ms,
            claims_total=1,
            claims_verified=0,
            guard_hits=1,
        )
        _log_ask(ticker, "guard", 0, False, latency_ms)
        return answer

    data_dir = data_dir_for(ticker, settings)
    hits = retrieval.search(ticker, question, k, data_dir)
    if not hits:
        answer = _not_found_answer(ticker, question_sha256, settings)
        latency_ms = int((time.monotonic() - start) * 1000)
        _audit_no_call(
            settings,
            ticker=ticker,
            provider="none",
            latency_ms=latency_ms,
            claims_total=0,
            claims_verified=0,
            guard_hits=0,
        )
        _log_ask(ticker, "none", 0, True, latency_ms)
        return answer

    company = filings_for(ticker, data_dir)[0].company_name
    excerpts = [
        {
            "accession": hit.chunk.accession,
            "section_id": hit.chunk.section_id,
            "title": CANONICAL_SECTIONS.get(hit.chunk.section_id, hit.chunk.section_id),
            "text": hit.chunk.text,
        }
        for hit in hits
    ]
    user_payload: dict[str, Any] = {
        "task": "ask",
        "ticker": ticker,
        "company": company,
        "question": question,
        "excerpts": excerpts,
    }

    active_provider = provider if provider is not None else make_provider(settings)
    draft_result = _complete_answer_draft(active_provider, user_payload, settings.max_tokens_ask)

    accessions = {hit.chunk.accession for hit in hits}
    section_text_by_key = _section_text_index(accessions, data_dir)
    claims = _claims_from_draft(draft_result.draft.claims, section_text_by_key)
    scrubbed_claims, guard_hits = guard.scrub_claims(claims)

    claims_total = len(scrubbed_claims)
    claims_verified = sum(1 for claim in scrubbed_claims if claim.verified)
    latency_ms = int((time.monotonic() - start) * 1000)

    record(
        settings,
        AuditRecord(
            ts=datetime.now(UTC),
            ticker=ticker,
            purpose="ask",
            provider=active_provider.name,
            model=active_provider.model,
            latency_ms=latency_ms,
            input_tokens=draft_result.input_tokens,
            output_tokens=draft_result.output_tokens,
            prompt_sha256=_sha256(draft_result.prompt_json),
            response_sha256=_sha256(draft_result.response_text),
            claims_total=claims_total,
            claims_verified=claims_verified,
            guard_hits=guard_hits,
            prompt=draft_result.prompt_json if settings.audit_bodies else None,
            response=draft_result.response_text if settings.audit_bodies else None,
        ),
    )

    _log_ask(ticker, active_provider.name, len(hits), draft_result.draft.not_found, latency_ms)

    return Answer(
        ticker=ticker,
        question_sha256=question_sha256,
        generated_at=datetime.now(UTC),
        provider=active_provider.name,
        model=active_provider.model,
        claims=scrubbed_claims,
        not_found=draft_result.draft.not_found,
        guard_hits=guard_hits,
        disclaimer=settings.disclaimer,
    )
