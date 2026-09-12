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


def _timeout_error(name: str) -> FathomError:
    return FathomError(
        Code.PROVIDER_TIMEOUT,
        f"{name} provider request failed (reason=timeout)",
        {"provider": name},
    )


def _transport_error(name: str, exc: httpx.HTTPError) -> FathomError:
    reason = type(exc).__name__
    return FathomError(
        Code.PROVIDER_HTTP,
        f"{name} provider request failed (reason={reason})",
        {"status": 0, "provider": name, "reason": reason},
    )


def _http_status_error(name: str, status: int) -> FathomError:
    return FathomError(
        Code.PROVIDER_HTTP,
        f"{name} provider returned HTTP {status}",
        {"status": status, "provider": name},
    )


def _malformed_response_error(name: str, status: int) -> FathomError:
    return FathomError(
        Code.PROVIDER_HTTP,
        f"{name} provider request failed (reason=malformed response)",
        {"status": status, "provider": name, "reason": "malformed response"},
    )


def _coerce_int(value: Any) -> int | None:
    """A usage counter that isn't a plain int is treated as absent, not an error (T-015 AC2)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _parse_portkey_payload(
    name: str, response: httpx.Response
) -> tuple[str, dict[str, Any] | None]:
    """Decode the 2xx body and pull out the completion text; never leaks the body."""
    try:
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("top-level body is not an object")
        text = payload["choices"][0]["message"]["content"]
        if not isinstance(text, str):
            raise TypeError("content is not a string")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise _malformed_response_error(name, response.status_code) from exc
    usage = payload.get("usage")
    return text, usage if isinstance(usage, dict) else None


def _parse_anthropic_payload(
    name: str, response: httpx.Response
) -> tuple[str, dict[str, Any] | None]:
    """Decode the 2xx body and pull out the completion text; never leaks the body."""
    try:
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("top-level body is not an object")
        text = payload["content"][0]["text"]
        if not isinstance(text, str):
            raise TypeError("content text is not a string")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise _malformed_response_error(name, response.status_code) from exc
    usage = payload.get("usage")
    return text, usage if isinstance(usage, dict) else None


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
            raise _timeout_error(self.name) from exc
        except httpx.HTTPError as exc:
            raise _transport_error(self.name, exc) from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        if not (200 <= response.status_code < 300):
            raise _http_status_error(self.name, response.status_code)
        text, usage = _parse_portkey_payload(self.name, response)
        input_tokens = _coerce_int(usage.get("prompt_tokens")) if usage else None
        output_tokens = _coerce_int(usage.get("completion_tokens")) if usage else None
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
            raise _timeout_error(self.name) from exc
        except httpx.HTTPError as exc:
            raise _transport_error(self.name, exc) from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        if not (200 <= response.status_code < 300):
            raise _http_status_error(self.name, response.status_code)
        text, usage = _parse_anthropic_payload(self.name, response)
        input_tokens = _coerce_int(usage.get("input_tokens")) if usage else None
        output_tokens = _coerce_int(usage.get("output_tokens")) if usage else None
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

_ITEM_PREFIX = re.compile(r"^Item\s+\d+[A-Za-z]?\.\s*", re.IGNORECASE)

_BOILERPLATE_MARKERS = (
    "forward-looking",
    "private securities litigation reform act",
    "this item and other sections",
    "safe harbor",
    "should be read in conjunction",
)


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


def _trim_newline_tail(sentence: str) -> str:
    """D-011(a): a sentence with a newline keeps only the text after its last newline."""
    if "\n" not in sentence:
        return sentence
    return sentence.rsplit("\n", 1)[-1].strip()


def _trim_item_prefix(sentence: str) -> str:
    """D-011(d): drop a leading 'Item N.' / 'Item NA.' section-heading prefix."""
    return _ITEM_PREFIX.sub("", sentence, count=1)


def _is_boilerplate(sentence: str) -> bool:
    """D-011(b): case-insensitive forward-looking / safe-harbor boilerplate skip."""
    lowered = sentence.lower()
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _normalised_candidate(raw_sentence: str) -> str | None:
    """Apply D-011 (a) and (d), then require the result still qualifies and passes (b)."""
    sentence = _trim_item_prefix(_trim_newline_tail(raw_sentence))
    if not _qualifies(sentence):
        return None
    if _is_boilerplate(sentence):
        return None
    return sentence


def _qualifying_sentences(text: str) -> list[str]:
    candidates = (_normalised_candidate(s) for s in _sentences(text))
    return [s for s in candidates if s is not None]


def _claim(excerpt: dict[str, Any], sentence: str) -> dict[str, Any]:
    return {
        "text": sentence,
        "accession": excerpt["accession"],
        "section_id": excerpt["section_id"],
        "quote": sentence,
    }


def _claims_from(
    excerpt: dict[str, Any] | None, limit: int, used: set[str] | None = None
) -> list[dict[str, Any]]:
    """The first `limit` qualifying sentences of `excerpt`, skipping any already in `used`.

    D-011(c): a sentence already claimed elsewhere in the briefing is not reused; whatever is
    selected here is added to `used` in place. Pass `used=None` to opt out (e.g. `ask`, which
    has no shared briefing-wide state).
    """
    if excerpt is None:
        return []
    candidates = _qualifying_sentences(excerpt["text"])
    if used is not None:
        candidates = [s for s in candidates if s not in used]
    sentences = candidates[:limit]
    if used is not None:
        used.update(sentences)
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


def _liquidity_claims(excerpt: dict[str, Any] | None, used: set[str]) -> list[dict[str, Any]]:
    """D-011(c) applies here too: candidates already claimed elsewhere are excluded first."""
    if excerpt is None:
        return []
    qualifying = [s for s in _qualifying_sentences(excerpt["text"]) if s not in used]
    keyword_sentences = [s for s in qualifying if "liquidity" in s.lower() or "cash" in s.lower()][
        :3
    ]
    chosen = keyword_sentences if keyword_sentences else qualifying[:2]
    used.update(chosen)
    return [_claim(excerpt, sentence) for sentence in chosen]


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

    # D-011(c): one running set of already-claimed sentences, carried across sections in
    # briefing order; talking points are exempt and may reuse an earlier claim's sentence.
    used: set[str] = set()
    business_snapshot = _claims_from(business, 3, used)
    latest_results_claims = _claims_from(latest_results, 4, used)
    risks_claims = _claims_from(risks, 4, used)
    liquidity_claims = _liquidity_claims(liquidity_source, used)

    notable: list[dict[str, Any]] = []
    for excerpt in (cyber, legal_10k, legal_10q):
        notable.extend(_claims_from(excerpt, 1, used))

    return {
        "business_snapshot": business_snapshot,
        "latest_results": latest_results_claims,
        "risks": risks_claims,
        "liquidity_capital": liquidity_claims,
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
