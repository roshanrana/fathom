"""Tests for fathom.api (LLD §4, §7, envelope + status mapping). RTM: FR-014."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fathom.api import create_app
from fathom.config import Settings
from fathom.contracts import Answer, Briefing
from fathom.filings import Filing
from fathom.quotes import QuoteCard

_ENVELOPE_KEYS = {"ok", "data", "error", "meta"}


def _settings(data_dir: Path, tmp_path: Path, **overrides: object) -> Settings:
    fields: dict[str, object] = {
        "data_dir": data_dir,
        "audit_path": tmp_path / "audit" / "fathom-audit.jsonl",
    }
    fields.update(overrides)
    return Settings(**fields)  # type: ignore[arg-type]


def _client(
    data_dir: Path, tmp_path: Path, *, raise_server_exceptions: bool = True, **overrides: object
) -> TestClient:
    settings = _settings(data_dir, tmp_path, **overrides)
    return TestClient(create_app(settings), raise_server_exceptions=raise_server_exceptions)


# --- AC3: envelope + contract validation on the happy path -----------------------------------


def test_fr014_healthz_returns_ok_envelope(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["status"] == "ok"
    assert body["data"]["provider"] == "offline"
    assert isinstance(body["data"]["version"], str)
    assert body["meta"]["ticker"] is None


def test_fr014_get_quote_validates_as_quote_card(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    response = client.get("/api/quote/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    QuoteCard.model_validate(body["data"])


def test_fr014_get_filings_returns_five_items_validating_as_filing(
    data_dir: Path, tmp_path: Path
) -> None:
    client = _client(data_dir, tmp_path)

    response = client.get("/api/filings/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 5
    for row in body["data"]:
        Filing.model_validate(row)


def test_fr014_post_brief_validates_as_briefing(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    response = client.post("/api/brief/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    Briefing.model_validate(body["data"])


def test_fr014_post_ask_validates_as_answer(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    response = client.post("/api/ask/AAPL", json={"question": "main risk factors"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    Answer.model_validate(body["data"])


# --- Status mapping (LLD §4, §7) --------------------------------------------------------------


def test_fr014_get_quote_unknown_ticker_returns_404_unknown_ticker(
    data_dir: Path, tmp_path: Path
) -> None:
    client = _client(data_dir, tmp_path)

    response = client.get("/api/quote/ZZZZ")

    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["ok"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "UNKNOWN_TICKER"


def test_fr014_post_ask_missing_question_returns_422(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    response = client.post("/api/ask/AAPL", json={})

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["ok"] is False
    assert body["data"] is None


def test_fr014_post_ask_question_over_2000_chars_returns_422(
    data_dir: Path, tmp_path: Path
) -> None:
    """AC9 (D-008): a 2 001-character question is rejected by the bounded AskBody field."""
    client = _client(data_dir, tmp_path)

    response = client.post("/api/ask/AAPL", json={"question": "x" * 2001})

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["ok"] is False
    assert body["data"] is None


def test_fr014_post_ask_question_at_2000_chars_is_accepted(data_dir: Path, tmp_path: Path) -> None:
    """The 2 000-character boundary itself is still valid."""
    client = _client(data_dir, tmp_path)

    response = client.post("/api/ask/AAPL", json={"question": "x" * 2000})

    assert response.status_code == 200


def test_fr014_provider_config_error_returns_503_naming_the_variable(
    data_dir: Path, tmp_path: Path
) -> None:
    client = _client(data_dir, tmp_path, llm_provider="portkey", portkey_api_key=None)

    response = client.post("/api/brief/AAPL")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "PROVIDER_CONFIG"
    assert "PORTKEY_API_KEY" in body["error"]["message"]


# --- AC4: internal errors never leak; unmapped FathomError codes also fall back to 500 -------


def test_fr014_generic_exception_returns_500_internal_without_internals(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(ticker: str, data_dir: Path) -> QuoteCard:
        raise RuntimeError("boom - sentinel that must never reach the client")

    monkeypatch.setattr("fathom.api.quote_card", _boom)
    client = _client(data_dir, tmp_path, raise_server_exceptions=False)

    response = client.get("/api/quote/AAPL")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {"code": "INTERNAL", "message": "internal error"}
    assert "boom" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_fr014_unmapped_fathom_error_code_also_returns_500_internal(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fathom.errors import Code, FathomError

    def _boom(ticker: str, data_dir: Path) -> QuoteCard:
        raise FathomError(Code.DATA_MISSING, "some internal detail that must not leak")

    monkeypatch.setattr("fathom.api.quote_card", _boom)
    client = _client(data_dir, tmp_path, raise_server_exceptions=False)

    response = client.get("/api/quote/AAPL")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {"code": "INTERNAL", "message": "internal error"}
    assert "internal detail" not in response.text


# --- AC5: meta on every response ---------------------------------------------------------------


def test_fr014_meta_provider_reflects_settings_llm_provider(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    response = client.get("/api/quote/AAPL")

    body = response.json()
    assert body["meta"]["provider"] == "offline"
    assert body["meta"]["ticker"] == "AAPL"
    assert isinstance(body["meta"]["generated_at"], str)


def test_fr014_every_response_has_all_four_envelope_keys(data_dir: Path, tmp_path: Path) -> None:
    client = _client(data_dir, tmp_path)

    responses = [
        client.get("/healthz"),
        client.get("/api/quote/AAPL"),
        client.get("/api/quote/ZZZZ"),
        client.get("/api/filings/AAPL"),
        client.post("/api/brief/AAPL"),
        client.post("/api/ask/AAPL", json={"question": "main risk factors"}),
        client.post("/api/ask/AAPL", json={}),
    ]

    for response in responses:
        assert set(response.json().keys()) == _ENVELOPE_KEYS
