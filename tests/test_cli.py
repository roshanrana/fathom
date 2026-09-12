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


# --- bench/mcp: lazy-imported commands, now that T-010/T-012 have shipped ----------------------
#
# Scope note accepted from Orchestrator: T-012 landed fathom/mcp_server.py, so invoking `mcp`
# under CliRunner used to run the real stdio server (I/O on closed stdio -> failure). These now
# monkeypatch the lazily-imported module's entry point rather than exercising the real bench
# run / stdio server, so they stay fast and hermetic while still covering the CLI wiring.


def test_fr013_bench_command_invokes_run_bench_with_out_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fathom.bench as bench_module

    calls: list[Path] = []
    monkeypatch.setattr(bench_module, "run_bench", lambda out: calls.append(out))

    out_path = tmp_path / "headline.json"
    result = runner.invoke(app, ["bench", "--out", str(out_path)])

    assert result.exit_code == 0
    assert calls == [out_path]


def test_fr013_mcp_command_invokes_mcp_server_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import fathom.mcp_server as mcp_module

    calls: list[bool] = []
    monkeypatch.setattr(mcp_module, "main", lambda: calls.append(True))

    result = runner.invoke(app, ["mcp"])

    assert result.exit_code == 0
    assert calls == [True]


# --- AC9 (D-008): CLI `api --host` default and `ask` question length bound --------------------


def test_fr013_api_command_host_option_defaults_to_loopback() -> None:
    """Inspect the Typer command's own parameter default, never bind a real socket."""
    command = next(cmd for cmd in app.registered_commands if cmd.name == "api")
    assert command.callback is not None
    host_default = command.callback.__defaults__[
        command.callback.__code__.co_varnames.index("host")
    ]
    assert host_default == "127.0.0.1"


def test_fr013_ask_question_over_2000_chars_exits_2_with_invalid_question() -> None:
    result = runner.invoke(app, ["ask", "AAPL", "x" * 2001])

    assert result.exit_code == 2
    assert "error INVALID_QUESTION: question exceeds 2000 characters" in result.output


def test_fr013_ask_question_at_2000_chars_is_accepted() -> None:
    result = runner.invoke(app, ["ask", "AAPL", "x" * 2000, "--json"])

    assert result.exit_code == 0
