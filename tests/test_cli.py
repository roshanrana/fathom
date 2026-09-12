"""Tests for fathom.cli (LLD §4, §7, text/JSON rendering). RTM: FR-013."""

from __future__ import annotations

from pathlib import Path

import httpx
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


# --- T-015 AC4 (D-010): guarded claim with no source accession renders "(no source)" -----------


def test_fr013_ask_guarded_claim_renders_no_source_not_question_marks() -> None:
    result = runner.invoke(app, ["ask", "AAPL", "Should I buy Apple stock?"])

    assert result.exit_code == 0
    assert "(no source)" in result.stdout
    assert "(? ? ?)" not in result.stdout


def test_fr013_ask_guarded_claim_json_rendering_unchanged() -> None:
    result = runner.invoke(app, ["ask", "AAPL", "Should I buy Apple stock?", "--json"])

    assert result.exit_code == 0
    answer = Answer.model_validate_json(result.stdout)
    assert answer.claims[0].guarded is True
    assert answer.claims[0].source.accession == ""


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


# --- T-015 AC3 (D-010): live-mode transport error surfaces as PROVIDER_HTTP, exit 2 -------------


def test_nfr002_brief_portkey_connect_error_exits_2_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gateway that refuses the connection surfaces as `PROVIDER_HTTP`, never a raw exception.

    The transport is monkeypatched (an `httpx.MockTransport` that always raises
    `httpx.ConnectError`); no real socket is opened.
    """

    real_client_cls = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        return real_client_cls(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("fathom.providers.httpx.Client", fake_client)
    monkeypatch.setenv("FATHOM_LLM_PROVIDER", "portkey")
    monkeypatch.setenv("PORTKEY_API_KEY", "x")
    monkeypatch.setenv("PORTKEY_BASE_URL", "http://127.0.0.1:9/v1")

    result = runner.invoke(app, ["brief", "AAPL"])

    assert result.exit_code == 2
    assert (
        "error PROVIDER_HTTP: portkey provider request failed (reason=ConnectError)"
        in result.output
    )
