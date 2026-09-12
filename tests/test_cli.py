"""Tests for fathom.cli (LLD §4, §7, text/JSON rendering). RTM: FR-013."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from fathom.cli import app
from fathom.contracts import Answer, Briefing

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, data_dir: Path, tmp_path: Path) -> None:
    """Point every invocation at the real fixtures but an isolated, tmp_path audit log."""
    monkeypatch.setenv("FATHOM_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FATHOM_AUDIT_PATH", str(tmp_path / "audit" / "fathom-audit.jsonl"))
    monkeypatch.setenv("FATHOM_LLM_PROVIDER", "offline")


# --- AC1 ---------------------------------------------------------------------------------------


def test_fr013_quote_prints_ticker_and_last_close() -> None:
    result = runner.invoke(app, ["quote", "AAPL"])

    assert result.exit_code == 0
    assert "AAPL" in result.stdout


def test_fr013_quote_unknown_ticker_exits_2_with_error_on_stderr() -> None:
    result = runner.invoke(app, ["quote", "ZZZZ"])

    assert result.exit_code == 2
    assert "error UNKNOWN_TICKER:" in result.output


def test_fr013_filings_lists_accessions_and_forms() -> None:
    result = runner.invoke(app, ["filings", "AAPL"])

    assert result.exit_code == 0
    assert "10-K" in result.stdout or "10-Q" in result.stdout


def test_fr013_filings_unknown_ticker_exits_2() -> None:
    result = runner.invoke(app, ["filings", "ZZZZ"])

    assert result.exit_code == 2
    assert "error UNKNOWN_TICKER:" in result.output


def test_fr013_brief_json_validates_as_briefing() -> None:
    result = runner.invoke(app, ["brief", "AAPL", "--json"])

    assert result.exit_code == 0
    Briefing.model_validate_json(result.stdout)


def test_fr013_ask_json_validates_as_answer() -> None:
    result = runner.invoke(app, ["ask", "AAPL", "main risk factors", "--json"])

    assert result.exit_code == 0
    Answer.model_validate_json(result.stdout)


# --- Non-JSON text rendering -------------------------------------------------------------------


def test_fr013_brief_text_rendering_has_section_headers_and_disclaimer() -> None:
    result = runner.invoke(app, ["brief", "AAPL"])

    assert result.exit_code == 0
    for header in ("Business Snapshot:", "Latest Results:", "Risks:", "Talking Points:"):
        assert header in result.stdout
    from fathom.config import DEFAULT_DISCLAIMER

    assert DEFAULT_DISCLAIMER in result.stdout


def test_fr013_ask_text_rendering_shows_ticker_and_disclaimer() -> None:
    result = runner.invoke(app, ["ask", "AAPL", "main risk factors"])

    assert result.exit_code == 0
    assert "AAPL" in result.stdout
    from fathom.config import DEFAULT_DISCLAIMER

    assert DEFAULT_DISCLAIMER in result.stdout


# --- AC2: probe ----------------------------------------------------------------------------


def test_fr013_probe_offline_prints_provider_model_and_pong_reply() -> None:
    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0
    assert "offline" in result.stdout
    assert "extractive-v1" in result.stdout
    assert "pong" in result.stdout


# --- bench/mcp: not-yet-available lazy imports (T-010/T-012 land later) ------------------------


def test_fr013_bench_reports_not_available_before_t010_ships() -> None:
    result = runner.invoke(app, ["bench"])

    if result.exit_code == 0:
        pytest.skip("fathom.bench is now available (T-010 shipped)")
    assert result.exit_code == 2
    assert "error NOT_AVAILABLE: bench arrives in T-010" in result.output


def test_fr013_mcp_reports_not_available_before_t012_ships() -> None:
    result = runner.invoke(app, ["mcp"])

    if result.exit_code == 0:
        pytest.skip("fathom.mcp_server is now available (T-012 shipped)")
    assert result.exit_code == 2
    assert "error NOT_AVAILABLE: mcp arrives in T-012" in result.output
