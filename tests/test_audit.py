"""Audit writer tests (LLD §2.9). RTM: FR-011, NFR-006."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from fathom.audit import AuditRecord, record
from fathom.config import Settings
from fathom.contracts import Claim, Source
from fathom.errors import Code, FathomError
from fathom.guard import is_advice, scrub_claims, verify_claim


def _settings(tmp_path: Path, *, audit_bodies: bool) -> Settings:
    return Settings(
        audit_path=tmp_path / "audit" / "fathom-audit.jsonl",
        audit_bodies=audit_bodies,
    )


def _record(**overrides: Any) -> AuditRecord:
    fields: dict[str, Any] = {
        "ts": datetime(2024, 11, 2, 12, 0, 0),
        "ticker": "AAPL",
        "purpose": "brief",
        "provider": "offline",
        "model": "offline-fixture",
        "latency_ms": 42,
        "input_tokens": 100,
        "output_tokens": 50,
        "prompt_sha256": "a" * 64,
        "response_sha256": "b" * 64,
        "claims_total": 6,
        "claims_verified": 6,
        "guard_hits": 0,
        "prompt": None,
        "response": None,
    }
    fields.update(overrides)
    return AuditRecord(**fields)


def test_fr011_record_writes_one_json_line_per_call_and_creates_parents(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, audit_bodies=False)
    assert not settings.audit_path.parent.exists()

    record(settings, _record())
    record(settings, _record(ticker="MSFT"))

    lines = settings.audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["ticker"] == "AAPL"
    assert json.loads(lines[1])["ticker"] == "MSFT"


def test_fr011_record_drops_bodies_when_audit_bodies_false(tmp_path: Path) -> None:
    settings = _settings(tmp_path, audit_bodies=False)

    record(settings, _record(prompt="secret prompt body", response="secret response body"))

    line = settings.audit_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload.get("prompt") is None
    assert payload.get("response") is None
    assert "secret prompt body" not in line
    assert "secret response body" not in line


def test_fr011_record_keeps_bodies_when_audit_bodies_true(tmp_path: Path) -> None:
    settings = _settings(tmp_path, audit_bodies=True)

    record(settings, _record(prompt="visible prompt body", response="visible response body"))

    line = settings.audit_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["prompt"] == "visible prompt body"
    assert payload["response"] == "visible response body"


def test_fr011_record_raises_audit_write_for_unwritable_path(tmp_path: Path) -> None:
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("i am a file, not a directory", encoding="utf-8")
    target = blocked / "fathom-audit.jsonl"
    settings = Settings(audit_path=target, audit_bodies=False)

    with pytest.raises(FathomError) as exc_info:
        record(settings, _record())

    assert exc_info.value.code == Code.AUDIT_WRITE
    assert str(target) in exc_info.value.message
    assert exc_info.value.details["path"] == str(target)


def test_nfr006_never_logs_secrets_bodies_or_question_text(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="fathom")
    settings = _settings(tmp_path, audit_bodies=True)
    question_text = "Should I buy TSLA before earnings, sk-ant-q1?"
    secret_prompt = "PORTKEY key=sk-ant-p1 this prompt mentions " + question_text
    secret_response = "response body sk-ant-r1 PORTKEY " + question_text

    record(settings, _record(prompt=secret_prompt, response=secret_response))

    section_text = "Net sales increased 5% year over year across all regions covered by the filing."
    claim = Claim(
        text=question_text,
        source=Source(accession="acc-1", section_id="10-K:7"),
        quote="Net sales increased 5% year over year across all regions.",
    )
    is_advice(question_text)
    verify_claim(claim.quote, section_text)
    scrub_claims([claim])

    for message in caplog.messages:
        assert "sk-ant-" not in message
        assert "PORTKEY" not in message
        assert secret_prompt not in message
        assert question_text not in message
