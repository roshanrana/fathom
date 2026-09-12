"""LLM providers behind one protocol (LLD §2.7): Portkey, Anthropic, Offline (§6.3)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from fathom.config import Settings
from fathom.errors import Code, FathomError

logger = logging.getLogger("fathom")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKEN = re.compile(r"\w+")


class ProviderResult(BaseModel):
    """A completion result, normalised across providers."""

    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class Provider(Protocol):
    """One interchangeable LLM backend."""

    name: str
    model: str

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult: ...


class OfflineProvider:
    """Deterministic extractive provider requiring no network access (LLD §6.3)."""

    name = "offline"
    model = "extractive-v1"

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        start = time.monotonic()
        text = _offline_complete(user)
        latency_ms = int((time.monotonic() - start) * 1000)
        return ProviderResult(
            text=text, input_tokens=None, output_tokens=None, latency_ms=latency_ms
        )


class PortkeyProvider:
    """OpenAI-compatible chat completions via the Portkey gateway."""

    name = "portkey"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._client = client if client is not None else httpx.Client(timeout=timeout_s)

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        headers = {"x-portkey-api-key": self._api_key, "content-type": "application/json"}
        url = f"{self._base_url}/chat/completions"
        start = time.monotonic()
        try:
            response = self._client.post(url, json=body, headers=headers, timeout=self._timeout_s)
        except httpx.TimeoutException as exc:
            raise FathomError(
                Code.PROVIDER_TIMEOUT, "portkey request timed out", {"provider": self.name}
            ) from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        if not (200 <= response.status_code < 300):
            raise FathomError(
                Code.PROVIDER_HTTP,
                f"portkey returned status {response.status_code}",
                {"status": response.status_code, "provider": self.name},
            )
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage")
        input_tokens = usage.get("prompt_tokens") if usage else None
        output_tokens = usage.get("completion_tokens") if usage else None
        return ProviderResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )


class AnthropicProvider:
    """Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._client = client if client is not None else httpx.Client(timeout=timeout_s)

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        body = {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max_tokens,
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        start = time.monotonic()
        try:
            response = self._client.post(
                ANTHROPIC_URL, json=body, headers=headers, timeout=self._timeout_s
            )
        except httpx.TimeoutException as exc:
            raise FathomError(
                Code.PROVIDER_TIMEOUT, "anthropic request timed out", {"provider": self.name}
            ) from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        if not (200 <= response.status_code < 300):
            raise FathomError(
                Code.PROVIDER_HTTP,
                f"anthropic returned status {response.status_code}",
                {"status": response.status_code, "provider": self.name},
            )
        payload = response.json()
        text = payload["content"][0]["text"]
        usage = payload.get("usage")
        input_tokens = usage.get("input_tokens") if usage else None
        output_tokens = usage.get("output_tokens") if usage else None
        return ProviderResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )


def make_provider(settings: Settings, client: httpx.Client | None = None) -> Provider:
    """Build the provider named by `settings.llm_provider`.

    A missing API key raises `PROVIDER_CONFIG` naming the environment variable before any
    client is constructed.
    """
    provider: Provider
    if settings.llm_provider == "offline":
        provider = OfflineProvider()
    elif settings.llm_provider == "portkey":
        if not settings.portkey_api_key:
            raise FathomError(
                Code.PROVIDER_CONFIG,
                "PORTKEY_API_KEY is not set",
                {"var": "PORTKEY_API_KEY"},
            )
        provider = PortkeyProvider(
            base_url=settings.portkey_base_url,
            api_key=settings.portkey_api_key,
            model=settings.portkey_model,
            timeout_s=settings.http_timeout_s,
            client=client,
        )
    elif settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise FathomError(
                Code.PROVIDER_CONFIG,
                "ANTHROPIC_API_KEY is not set",
                {"var": "ANTHROPIC_API_KEY"},
            )
        provider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout_s=settings.http_timeout_s,
            client=client,
        )
    else:  # pragma: no cover - Settings.llm_provider is a Literal already validated upstream
        raise FathomError(
            Code.PROVIDER_CONFIG,
            f"unknown llm_provider {settings.llm_provider!r}",
            {"var": "FATHOM_LLM_PROVIDER"},
        )
    logger.info("provider selected name=%s model=%s", provider.name, provider.model)
    return provider


# --- Offline extractive algorithm (LLD §6.3) --------------------------------------------------


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _numeric_token_count(sentence: str) -> int:
    return sum(1 for tok in _TOKEN.findall(sentence) if tok[0].isdigit())


def _qualifies(sentence: str) -> bool:
    words = sentence.split()
    if not (8 <= len(words) <= 60):
        return False
    if sentence.isupper():
        return False
    return _numeric_token_count(sentence) < 4


def _qualifying_sentences(text: str) -> list[str]:
    return [s for s in _sentences(text) if _qualifies(s)]


def _claim(excerpt: dict[str, Any], sentence: str) -> dict[str, Any]:
    return {
        "text": sentence,
        "accession": excerpt["accession"],
        "section_id": excerpt["section_id"],
        "quote": sentence,
    }


def _claims_from(excerpt: dict[str, Any] | None, limit: int) -> list[dict[str, Any]]:
    if excerpt is None:
        return []
    sentences = _qualifying_sentences(excerpt["text"])[:limit]
    return [_claim(excerpt, sentence) for sentence in sentences]


def _excerpt_for_section(
    section_id: str,
    excerpts: list[dict[str, Any]],
    filings_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [e for e in excerpts if e.get("section_id") == section_id]
    if not candidates:
        return None

    def _filing_date(excerpt: dict[str, Any]) -> str:
        filing = filings_by_accession.get(excerpt["accession"], {})
        return str(filing.get("filing_date", ""))

    candidates.sort(key=_filing_date, reverse=True)
    return candidates[0]


def _liquidity_claims(excerpt: dict[str, Any] | None) -> list[dict[str, Any]]:
    if excerpt is None:
        return []
    qualifying = _qualifying_sentences(excerpt["text"])
    keyword_sentences = [s for s in qualifying if "liquidity" in s.lower() or "cash" in s.lower()][
        :3
    ]
    if keyword_sentences:
        return [_claim(excerpt, sentence) for sentence in keyword_sentences]
    return [_claim(excerpt, sentence) for sentence in qualifying[:2]]


def _talking_points(
    excerpts: list[dict[str, Any] | None],
    filings_by_accession: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for excerpt in excerpts:
        if excerpt is None:
            continue
        qualifying = _qualifying_sentences(excerpt["text"])
        if not qualifying:
            continue
        sentence = qualifying[0]
        filing = filings_by_accession.get(excerpt["accession"], {})
        text = (
            f"From {excerpt['title']} ({filing.get('form')} filed {filing.get('filing_date')}): "
            f"{sentence}"
        )
        points.append(
            {
                "text": text,
                "accession": excerpt["accession"],
                "section_id": excerpt["section_id"],
                "quote": sentence,
            }
        )
    return points


def _offline_briefing(payload: dict[str, Any]) -> dict[str, Any]:
    filings_by_accession: dict[str, dict[str, Any]] = {
        f["accession"]: f for f in payload.get("filings", [])
    }
    excerpts: list[dict[str, Any]] = payload.get("excerpts", [])

    def excerpt_for(section_id: str) -> dict[str, Any] | None:
        return _excerpt_for_section(section_id, excerpts, filings_by_accession)

    business = excerpt_for("10-K:1")
    latest_results = excerpt_for("10-Q:I.2") or excerpt_for("10-K:7")
    risks = excerpt_for("10-K:1A")
    liquidity_source = excerpt_for("10-Q:I.2") or excerpt_for("10-K:7")
    cyber = excerpt_for("10-K:1C")
    legal_10k = excerpt_for("10-K:3")
    legal_10q = excerpt_for("10-Q:II.1")

    notable: list[dict[str, Any]] = []
    for excerpt in (cyber, legal_10k, legal_10q):
        notable.extend(_claims_from(excerpt, 1))

    return {
        "business_snapshot": _claims_from(business, 3),
        "latest_results": _claims_from(latest_results, 4),
        "risks": _claims_from(risks, 4),
        "liquidity_capital": _liquidity_claims(liquidity_source),
        "notable_disclosures": notable,
        "talking_points": _talking_points(
            [business, latest_results, risks, liquidity_source], filings_by_accession
        ),
    }


def _offline_ask(payload: dict[str, Any]) -> dict[str, Any]:
    excerpts: list[dict[str, Any]] = payload.get("excerpts", [])[:3]
    claims: list[dict[str, Any]] = []
    for excerpt in excerpts:
        qualifying = _qualifying_sentences(excerpt.get("text", ""))
        if not qualifying:
            continue
        claims.append(_claim(excerpt, qualifying[0]))
    return {"claims": claims, "not_found": len(claims) == 0}


def _offline_complete(user: str) -> str:
    payload: dict[str, Any] = json.loads(user)
    if payload.get("ping") is True:
        return "pong"
    if payload.get("task") == "ask":
        return json.dumps(_offline_ask(payload))
    return json.dumps(_offline_briefing(payload))
