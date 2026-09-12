"""Tests for fathom.providers (RTM: FR-010, NFR-005, NFR-010)."""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.prompts import SYSTEM_BRIEFING, SYSTEM_PROBE
from fathom.providers import (
    AnthropicProvider,
    OfflineProvider,
    ProviderResult,
    make_provider,
)

SECRET_PORTKEY_KEY = "portkey-super-secret-key-value"
SECRET_ANTHROPIC_KEY = "anthropic-super-secret-key-value"


# --- AC1: PortkeyProvider request/response shape ------------------------------------------------


def test_fr010_portkey_provider_posts_expected_request_and_parses_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello from portkey"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 34},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(llm_provider="portkey", portkey_api_key=SECRET_PORTKEY_KEY)
    provider = make_provider(settings, client=client)

    result = provider.complete_json("system text", "user text", 4000)

    assert len(captured) == 1
    request = captured[0]
    assert str(request.url) == "https://portkeygateway.perficient.com/v1/chat/completions"
    assert request.headers["x-portkey-api-key"] == SECRET_PORTKEY_KEY
    assert request.headers["content-type"] == "application/json"

    body = json.loads(request.content)
    assert body["model"] == settings.portkey_model
    assert body["messages"] == [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "user text"},
    ]
    assert body["max_tokens"] == 4000
    assert body["temperature"] == 0.1

    assert isinstance(result, ProviderResult)
    assert result.text == "hello from portkey"
    assert result.input_tokens == 12
    assert result.output_tokens == 34
    assert result.latency_ms >= 0


def test_fr010_portkey_provider_missing_usage_yields_none_tokens() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(llm_provider="portkey", portkey_api_key="k")
    provider = make_provider(settings, client=client)

    result = provider.complete_json("s", "u", 100)

    assert result.input_tokens is None
    assert result.output_tokens is None


# --- AC2: AnthropicProvider request/response shape -----------------------------------------------


def test_fr010_anthropic_provider_posts_expected_request_and_parses_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hello from anthropic"}],
                "usage": {"input_tokens": 5, "output_tokens": 7},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(llm_provider="anthropic", anthropic_api_key=SECRET_ANTHROPIC_KEY)
    provider = make_provider(settings, client=client)
    assert isinstance(provider, AnthropicProvider)

    result = provider.complete_json("system text", "user text", 1500)

    assert len(captured) == 1
    request = captured[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == SECRET_ANTHROPIC_KEY
    assert request.headers["anthropic-version"] == "2023-06-01"

    body = json.loads(request.content)
    assert body["system"] == "system text"
    assert body["messages"] == [{"role": "user", "content": "user text"}]
    assert body["max_tokens"] == 1500

    assert result.text == "hello from anthropic"
    assert result.input_tokens == 5
    assert result.output_tokens == 7
    assert result.latency_ms >= 0


# --- AC3: non-2xx -> PROVIDER_HTTP; timeout -> PROVIDER_TIMEOUT; no leakage ----------------------


def test_nfr005_portkey_500_raises_provider_http_without_leaking_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal failure", "body": "leaky detail"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(llm_provider="portkey", portkey_api_key=SECRET_PORTKEY_KEY)
    provider = make_provider(settings, client=client)

    with pytest.raises(FathomError) as excinfo:
        provider.complete_json("s", "u", 100)

    error = excinfo.value
    assert error.code == Code.PROVIDER_HTTP
    assert error.details == {"status": 500, "provider": "portkey"}
    assert SECRET_PORTKEY_KEY not in error.message
    assert SECRET_PORTKEY_KEY not in json.dumps(error.details)
    assert "leaky detail" not in error.message
    assert "leaky detail" not in json.dumps(error.details)
    assert "?" not in error.message


def test_nfr005_anthropic_read_timeout_raises_provider_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(llm_provider="anthropic", anthropic_api_key="k")
    provider = make_provider(settings, client=client)

    with pytest.raises(FathomError) as excinfo:
        provider.complete_json("s", "u", 100)

    assert excinfo.value.code == Code.PROVIDER_TIMEOUT


# --- AC4: PROVIDER_CONFIG raised before any client is built --------------------------------------


def test_nfr005_make_provider_missing_portkey_key_raises_before_client_used() -> None:
    calls: list[httpx.Request] = []

    def failing_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("transport must never be called")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    settings = Settings(llm_provider="portkey", portkey_api_key=None)

    with pytest.raises(FathomError) as excinfo:
        make_provider(settings, client=client)

    assert excinfo.value.code == Code.PROVIDER_CONFIG
    assert "PORTKEY_API_KEY" in excinfo.value.message
    assert calls == []


def test_nfr005_make_provider_missing_anthropic_key_raises_before_client_used() -> None:
    calls: list[httpx.Request] = []

    def failing_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("transport must never be called")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    settings = Settings(llm_provider="anthropic", anthropic_api_key=None)

    with pytest.raises(FathomError) as excinfo:
        make_provider(settings, client=client)

    assert excinfo.value.code == Code.PROVIDER_CONFIG
    assert "ANTHROPIC_API_KEY" in excinfo.value.message
    assert calls == []


def test_fr010_make_provider_offline_needs_no_key() -> None:
    settings = Settings(llm_provider="offline")

    provider = make_provider(settings)

    assert isinstance(provider, OfflineProvider)
    assert provider.name == "offline"
    assert provider.model == "extractive-v1"


# --- AC7: log line format; key never logged ------------------------------------------------------


def test_nfr010_provider_selected_log_line_format(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="fathom")
    settings = Settings(llm_provider="offline")

    make_provider(settings)

    fathom_records = [r for r in caplog.records if r.name == "fathom"]
    assert len(fathom_records) == 1
    record = fathom_records[0]
    assert record.levelno == logging.INFO
    assert record.msg == "provider selected name=%s model=%s"
    assert record.args == ("offline", "extractive-v1")
    assert record.getMessage() == "provider selected name=offline model=extractive-v1"


def test_nfr010_provider_selected_log_never_contains_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="fathom")

    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must never be called")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    settings = Settings(llm_provider="portkey", portkey_api_key=SECRET_PORTKEY_KEY)

    make_provider(settings, client=client)

    for record in caplog.records:
        assert SECRET_PORTKEY_KEY not in record.getMessage()


# --- AC5/AC6: OfflineProvider extractive algorithm (§6.3) ----------------------------------------

_BUSINESS_S1 = (
    "The Company designs, develops, and sells consumer electronics and related software and "
    "services worldwide through its retail stores."
)
_BUSINESS_S2 = (
    "The Company also offers a variety of subscription based services including cloud storage, "
    "streaming media, and device protection plans."
)
_BUSINESS_S3 = (
    "Products are distributed through the Company's retail and online stores as well as through "
    "third party cellular network carriers and resellers."
)
_BUSINESS_S4 = (
    "The Company believes that its ongoing investment in research and development is critical to "
    "the development of innovative products and services."
)
_TEXT_10K_1 = " ".join([_BUSINESS_S1, _BUSINESS_S2, _BUSINESS_S3, _BUSINESS_S4])

_RISK_ALLCAPS = (
    "OUR BUSINESS FACES SUBSTANTIAL COMPETITIVE PRESSURE FROM LARGER RIVALS IN EVERY MARKET WE "
    "SERVE TODAY."
)
_RISK_TABLEROW = (
    "Revenue by segment for fiscal 2025 2024 2023 2022 was 120 110 105 95 respectively across all "
    "regions we operate in today."
)
_RISK_R1 = (
    "Our operations may be adversely affected by evolving regulatory requirements across the "
    "jurisdictions in which we operate."
)
_RISK_R2 = (
    "Changes in consumer preferences could reduce demand for our products and materially harm our "
    "reported operating results."
)
_RISK_R3 = (
    "We face intense competition from companies that may have greater financial and technical "
    "resources than we do."
)
_RISK_R4 = (
    "Disruptions in our supply chain could delay product launches and increase the costs of "
    "components we purchase."
)
_TEXT_10K_1A = " ".join([_RISK_ALLCAPS, _RISK_TABLEROW, _RISK_R1, _RISK_R2, _RISK_R3, _RISK_R4])

_CYBER_C1 = (
    "The Company maintains a comprehensive cybersecurity program designed to identify, assess, "
    "and manage risks from information security threats."
)
_LEGAL_10K_L1 = (
    "The Company is involved in various legal proceedings arising in the ordinary course of "
    "business that it does not believe are material."
)
_MDNA_10K_M1 = (
    "Management discusses the results of operations and the factors that affected performance "
    "during the fiscal year in this section."
)

_RESULTS_Q1 = (
    "Net sales increased during the quarter driven by strong demand across all of the Company's "
    "reportable segments."
)
_RESULTS_Q2 = (
    "Operating expenses rose modestly as the Company continued to invest in research and "
    "development initiatives."
)
_RESULTS_Q3_CASH = (
    "The Company believes its cash and cash equivalents will be sufficient to meet operating "
    "requirements for at least the next twelve months."
)
_RESULTS_Q4_LIQUIDITY = (
    "Liquidity needs are generally met through cash generated from operations and access to "
    "capital markets when required."
)
_RESULTS_Q5_CASH = (
    "Cash provided by operating activities remained strong and supported continued investment in "
    "the business during the period."
)
_TEXT_10Q_I2_NEW = " ".join(
    [_RESULTS_Q1, _RESULTS_Q2, _RESULTS_Q3_CASH, _RESULTS_Q4_LIQUIDITY, _RESULTS_Q5_CASH]
)
_TEXT_10Q_I2_OLD = (
    "This outdated quarterly filing describes results from an earlier period that should not be "
    "selected by the offline provider."
)
_LEGAL_10Q_LQ1 = (
    "The Company is party to certain legal matters that arose during the quarter and does not "
    "expect a material adverse effect."
)

_FILINGS = [
    {
        "accession": "AC-10K",
        "form": "10-K",
        "filing_date": "2025-10-31",
        "period_end": "2025-09-27",
    },
    {
        "accession": "AC-10Q-OLD",
        "form": "10-Q",
        "filing_date": "2025-07-31",
        "period_end": "2025-06-28",
    },
    {
        "accession": "AC-10Q-NEW",
        "form": "10-Q",
        "filing_date": "2026-01-30",
        "period_end": "2025-12-27",
    },
]

_EXCERPTS = [
    {"accession": "AC-10K", "section_id": "10-K:1", "title": "Business", "text": _TEXT_10K_1},
    {
        "accession": "AC-10K",
        "section_id": "10-K:1A",
        "title": "Risk Factors",
        "text": _TEXT_10K_1A,
    },
    {
        "accession": "AC-10K",
        "section_id": "10-K:1C",
        "title": "Cybersecurity",
        "text": _CYBER_C1,
    },
    {
        "accession": "AC-10K",
        "section_id": "10-K:3",
        "title": "Legal Proceedings",
        "text": _LEGAL_10K_L1,
    },
    {
        "accession": "AC-10K",
        "section_id": "10-K:7",
        "title": "Management's Discussion and Analysis",
        "text": _MDNA_10K_M1,
    },
    {
        "accession": "AC-10Q-OLD",
        "section_id": "10-Q:I.2",
        "title": "Management's Discussion and Analysis",
        "text": _TEXT_10Q_I2_OLD,
    },
    {
        "accession": "AC-10Q-NEW",
        "section_id": "10-Q:I.2",
        "title": "Management's Discussion and Analysis",
        "text": _TEXT_10Q_I2_NEW,
    },
    {
        "accession": "AC-10Q-NEW",
        "section_id": "10-Q:II.1",
        "title": "Legal Proceedings",
        "text": _LEGAL_10Q_LQ1,
    },
]

_BRIEFING_PAYLOAD = {
    "task": "briefing",
    "ticker": "AAPL",
    "company": "Apple Inc.",
    "as_of": "2026-01-31",
    "filings": _FILINGS,
    "excerpts": _EXCERPTS,
}

_TEXT_BY_ACCESSION_SECTION = {(e["accession"], e["section_id"]): e["text"] for e in _EXCERPTS}


def _run_offline_briefing() -> dict[str, list[dict[str, object]]]:
    provider = OfflineProvider()
    result = provider.complete_json(SYSTEM_BRIEFING, json.dumps(_BRIEFING_PAYLOAD), 4000)
    draft: dict[str, list[dict[str, object]]] = json.loads(result.text)
    return draft


def test_fr010_offline_briefing_has_six_keys_with_expected_claim_counts() -> None:
    draft = _run_offline_briefing()

    assert set(draft) == {
        "business_snapshot",
        "latest_results",
        "risks",
        "liquidity_capital",
        "notable_disclosures",
        "talking_points",
    }
    assert len(draft["business_snapshot"]) == 3
    assert len(draft["latest_results"]) == 4
    assert len(draft["risks"]) == 4
    assert len(draft["liquidity_capital"]) <= 3
    assert len(draft["notable_disclosures"]) <= 3
    assert len(draft["talking_points"]) <= 4


def test_fr010_offline_briefing_business_snapshot_takes_first_three_sentences() -> None:
    draft = _run_offline_briefing()

    texts = [c["text"] for c in draft["business_snapshot"]]
    assert texts == [_BUSINESS_S1, _BUSINESS_S2, _BUSINESS_S3]
    for claim in draft["business_snapshot"]:
        assert claim["quote"] == claim["text"]
        assert claim["accession"] == "AC-10K"
        assert claim["section_id"] == "10-K:1"


def test_fr010_offline_briefing_latest_results_uses_newest_10q_not_old() -> None:
    draft = _run_offline_briefing()

    texts = [c["text"] for c in draft["latest_results"]]
    assert texts == [_RESULTS_Q1, _RESULTS_Q2, _RESULTS_Q3_CASH, _RESULTS_Q4_LIQUIDITY]
    for claim in draft["latest_results"]:
        assert claim["accession"] == "AC-10Q-NEW"
        assert claim["section_id"] == "10-Q:I.2"


def test_fr010_offline_briefing_risks_skips_allcaps_and_tablerow_sentences() -> None:
    draft = _run_offline_briefing()

    texts = [c["text"] for c in draft["risks"]]
    assert texts == [_RISK_R1, _RISK_R2, _RISK_R3, _RISK_R4]
    assert _RISK_ALLCAPS not in texts
    assert _RISK_TABLEROW not in texts


def test_fr010_offline_briefing_liquidity_prefers_cash_and_liquidity_sentences() -> None:
    draft = _run_offline_briefing()

    texts = [c["text"] for c in draft["liquidity_capital"]]
    assert texts == [_RESULTS_Q3_CASH, _RESULTS_Q4_LIQUIDITY, _RESULTS_Q5_CASH]


def test_fr010_offline_briefing_notable_disclosures_one_per_section() -> None:
    draft = _run_offline_briefing()

    by_section = {c["section_id"]: c for c in draft["notable_disclosures"]}
    assert by_section["10-K:1C"]["text"] == _CYBER_C1
    assert by_section["10-K:3"]["text"] == _LEGAL_10K_L1
    assert by_section["10-Q:II.1"]["text"] == _LEGAL_10Q_LQ1
    assert by_section["10-Q:II.1"]["accession"] == "AC-10Q-NEW"


def test_fr010_offline_briefing_talking_points_are_from_prefixed_and_grounded() -> None:
    draft = _run_offline_briefing()

    assert len(draft["talking_points"]) == 4
    for claim in draft["talking_points"]:
        assert claim["text"].startswith("From ")
        assert claim["quote"] != claim["text"]
        source_text = _TEXT_BY_ACCESSION_SECTION[(claim["accession"], claim["section_id"])]
        assert claim["quote"] in source_text


def test_fr010_offline_briefing_every_claim_quote_is_substring_of_its_excerpt() -> None:
    draft = _run_offline_briefing()

    for key, claims in draft.items():
        for claim in claims:
            source_text = _TEXT_BY_ACCESSION_SECTION[(claim["accession"], claim["section_id"])]
            assert claim["quote"] in source_text
            if key != "talking_points":
                assert claim["quote"] == claim["text"]


def test_fr010_offline_ask_returns_at_most_three_claims() -> None:
    payload = {
        "task": "ask",
        "question": "What are the company's main risks?",
        "excerpts": [
            {
                "accession": "AC-A",
                "section_id": "10-K:1A",
                "title": "Risk Factors",
                "text": _RISK_R1,
            },
            {
                "accession": "AC-B",
                "section_id": "10-K:1A",
                "title": "Risk Factors",
                "text": _RISK_R2,
            },
            {
                "accession": "AC-C",
                "section_id": "10-K:1A",
                "title": "Risk Factors",
                "text": _RISK_R3,
            },
        ],
    }
    provider = OfflineProvider()

    result = provider.complete_json(SYSTEM_BRIEFING, json.dumps(payload), 1500)
    draft = json.loads(result.text)

    assert len(draft["claims"]) == 3
    assert draft["not_found"] is False
    assert draft["claims"][0]["text"] == _RISK_R1
    assert draft["claims"][0]["quote"] == draft["claims"][0]["text"]


def test_fr010_offline_ask_no_qualifying_sentence_returns_not_found() -> None:
    payload = {
        "task": "ask",
        "question": "irrelevant",
        "excerpts": [
            {"accession": "AC-A", "section_id": "10-K:1A", "title": "Risk Factors", "text": "No."},
            {
                "accession": "AC-B",
                "section_id": "10-K:1A",
                "title": "Risk Factors",
                "text": "TOO SHORT ALL CAPS.",
            },
        ],
    }
    provider = OfflineProvider()

    result = provider.complete_json(SYSTEM_BRIEFING, json.dumps(payload), 1500)
    draft = json.loads(result.text)

    assert draft == {"claims": [], "not_found": True}


def test_fr010_offline_probe_returns_pong() -> None:
    provider = OfflineProvider()

    result = provider.complete_json(SYSTEM_PROBE, json.dumps({"ping": True}), 100)

    assert result.text == "pong"
