"""Tests for fathom.ask (LLD §2.10, §3, §6.2, §6.5, §9). RTM: FR-009."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest

from fathom.ask import ask
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.filings import filings_for, sections_for
from fathom.providers import ProviderResult
from fathom.retrieval import Chunk, Hit

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ScriptedProvider:
    """A `Provider` that replays `texts` in order, recording every call it receives."""

    name = "scripted"
    model = "scripted-v1"

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[tuple[str, str, int]] = []

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        self.calls.append((system, user, max_tokens))
        index = len(self.calls) - 1
        text = self._texts[index] if index < len(self._texts) else self._texts[-1]
        return ProviderResult(text=text, input_tokens=10, output_tokens=5, latency_ms=1)


class FailingProvider:
    """A `Provider` that fails the test if it is ever called."""

    name = "failing"
    model = "failing-v1"

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        raise AssertionError("provider must not be called on this path")


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    fields: dict[str, Any] = {"audit_path": tmp_path / "audit" / "fathom-audit.jsonl"}
    fields.update(overrides)
    return Settings(**fields)


def _pick_qualifying_sentence(text: str) -> str:
    """A real sentence from `text` with 6-60 words, per `guard.verify_claim`'s bounds."""
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        words = sentence.split()
        if 6 <= len(words) <= 60:
            return sentence
    raise AssertionError("no qualifying sentence found in fixture text")


def _aapl_10k_accession(data_dir: Path) -> str:
    for filing in filings_for("AAPL", data_dir):
        if filing.form == "10-K":
            return filing.accession
    raise AssertionError("no AAPL 10-K fixture found")


def _audit_lines(settings: Settings) -> list[dict[str, Any]]:
    if not settings.audit_path.exists():
        return []
    return [json.loads(line) for line in settings.audit_path.read_text("utf-8").splitlines()]


def test_fr009_ask_advice_question_short_circuits_guard(tmp_path: Path) -> None:
    """AC1: an advice-shaped question never calls the provider or retrieval."""
    settings = _settings(tmp_path)

    answer = ask("AAPL", "Should I buy Apple?", settings, provider=FailingProvider())

    assert answer.guard_hits == 1
    assert len(answer.claims) == 1
    claim = answer.claims[0]
    assert claim.guarded is True
    assert claim.verified is False
    assert answer.not_found is False
    assert answer.provider == "guard"
    assert answer.model == "-"

    lines = _audit_lines(settings)
    assert len(lines) == 1
    assert lines[0]["provider"] == "guard"
    assert lines[0]["model"] == "-"
    assert lines[0]["guard_hits"] == 1
    assert lines[0]["purpose"] == "ask"


def test_fr009_ask_zero_hits_returns_not_found_without_calling_provider(
    tmp_path: Path, data_dir: Path
) -> None:
    """AC2: a query matching no corpus terms short-circuits retrieval; no provider call."""
    settings = _settings(tmp_path, data_dir=data_dir)

    answer = ask("AAPL", "zqxjv wvutsr", settings, provider=FailingProvider())

    assert answer.not_found is True
    assert answer.claims == []
    assert answer.provider == "none"
    assert answer.model == "-"
    assert answer.guard_hits == 0

    lines = _audit_lines(settings)
    assert len(lines) == 1
    assert lines[0]["provider"] == "none"
    assert lines[0]["model"] == "-"


def test_fr009_ask_offline_risk_factors_returns_verified_claims(
    tmp_path: Path, data_dir: Path
) -> None:
    """AC3: offline end-to-end over real AAPL fixtures yields >=1 verified claim."""
    settings = _settings(tmp_path, data_dir=data_dir)

    answer = ask("AAPL", "What are the main risk factors?", settings)

    assert answer.not_found is False
    assert len(answer.claims) >= 1
    for claim in answer.claims:
        assert claim.verified is True
        assert claim.source.section_id in (
            "10-K:1",
            "10-K:1A",
            "10-K:1C",
            "10-K:3",
            "10-K:7",
            "10-K:7A",
            "10-K:9A",
            "10-Q:I.2",
            "10-Q:I.3",
            "10-Q:I.4",
            "10-Q:II.1",
            "10-Q:II.1A",
        )
    assert answer.provider == "offline"


def test_fr009_ask_verifies_against_full_section_not_retrieved_chunk(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a quote absent from the retrieved chunk but present in the full section verifies."""
    accession = _aapl_10k_accession(data_dir)
    risk_section = next(s for s in sections_for(accession, data_dir) if s.section_id == "10-K:1A")
    quote = _pick_qualifying_sentence(risk_section.text)

    chunk_text = "Placeholder retrieved excerpt text unrelated to the quoted sentence."
    assert quote not in chunk_text
    assert quote in risk_section.text

    fake_hit = Hit(
        chunk=Chunk(
            doc_id=f"{accession}#10-K:1A#0",
            accession=accession,
            section_id="10-K:1A",
            text=chunk_text,
            ordinal=0,
        ),
        score=1.0,
    )
    monkeypatch.setattr("fathom.retrieval.search", lambda ticker, query, k, data_dir: [fake_hit])

    draft_json = json.dumps(
        {
            "claims": [
                {
                    "text": "The filing describes a risk factor.",
                    "accession": accession,
                    "section_id": "10-K:1A",
                    "quote": quote,
                }
            ],
            "not_found": False,
        }
    )
    fenced = f"```json\n{draft_json}\n```"
    scripted = ScriptedProvider([fenced])
    settings = _settings(tmp_path, data_dir=data_dir)

    answer = ask("AAPL", "What risks does the filing describe?", settings, provider=scripted)

    assert len(scripted.calls) == 1
    assert len(answer.claims) == 1
    assert answer.claims[0].verified is True
    assert answer.claims[0].quote == quote


def test_fr009_ask_repairs_once_on_invalid_json_then_succeeds(
    tmp_path: Path, data_dir: Path
) -> None:
    """AC5: an invalid-then-valid provider response succeeds via the one repair retry."""
    valid_draft = json.dumps(
        {
            "claims": [
                {
                    "text": "Some claim text.",
                    "accession": "unknown-accession",
                    "section_id": "10-K:1A",
                    "quote": "This quote cites an accession unknown to this fixture set today.",
                }
            ],
            "not_found": False,
        }
    )
    scripted = ScriptedProvider(["not valid json{", valid_draft])
    settings = _settings(tmp_path, data_dir=data_dir)

    answer = ask("AAPL", "What are the risk factors?", settings, provider=scripted, k=6)

    assert len(scripted.calls) == 2
    assert "repair" not in json.loads(scripted.calls[0][1])
    assert json.loads(scripted.calls[1][1])["repair"]
    assert len(answer.claims) == 1
    assert answer.claims[0].verified is False  # unknown accession
    assert answer.not_found is False


def test_fr009_ask_raises_contract_invalid_after_two_bad_responses(
    tmp_path: Path, data_dir: Path
) -> None:
    """AC5: two consecutive invalid responses raise CONTRACT_INVALID with attempt=2."""
    scripted = ScriptedProvider(["not json at all", "still not json{"])
    settings = _settings(tmp_path, data_dir=data_dir)

    with pytest.raises(FathomError) as exc_info:
        ask("AAPL", "What are the risk factors?", settings, provider=scripted, k=6)

    assert exc_info.value.code == Code.CONTRACT_INVALID
    assert exc_info.value.details["attempt"] == 2
    assert len(scripted.calls) == 2


def test_fr009_ask_never_logs_or_audits_question_text(
    tmp_path: Path, data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC6: no log record or audit line contains the raw question text."""
    caplog.set_level(logging.DEBUG, logger="fathom")
    nonce = "xqzzyfnnbraqzzqvtx"
    settings = _settings(tmp_path, data_dir=data_dir, audit_bodies=True)

    ask("AAPL", f"Should I buy shares, {nonce}?", settings, provider=FailingProvider())
    ask("AAPL", f"zqxjv wvutsr {nonce}", settings, provider=FailingProvider())

    for message in caplog.messages:
        assert nonce not in message

    audit_text = settings.audit_path.read_text(encoding="utf-8")
    assert nonce not in audit_text
