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


# --- T-020 (FR-020, FR-024): --source routing and the `fetch` command --------------------------


def test_fr020_quote_source_fixture_forces_fixture_on_live_configured_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--source fixture` on a live-configured process still reads the fixtures."""
    monkeypatch.setenv("FATHOM_DATA_SOURCE", "live")
    monkeypatch.setenv("FATHOM_SEC_CONTACT", "t@example.com")

    result = runner.invoke(app, ["quote", "AAPL", "--source", "fixture"])

    assert result.exit_code == 0
    assert "AAPL" in result.stdout


def test_fr020_quote_source_live_missing_contact_exits_2_with_source_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FATHOM_SEC_CONTACT", raising=False)

    result = runner.invoke(app, ["quote", "AAPL", "--source", "live"])

    assert result.exit_code == 2
    assert "error SOURCE_CONFIG:" in result.output
    assert "FATHOM_SEC_CONTACT" in result.output


def test_fr020_quote_source_live_routes_through_data_dir_for(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    """`--source live` must call `data_dir_for`; a monkeypatched live cache dir is honoured."""
    import fathom.cli as cli_module

    calls: list[tuple[str, object]] = []

    def fake_data_dir_for(ticker: str, settings: object) -> Path:
        calls.append((ticker, settings))
        return data_dir

    monkeypatch.setattr(cli_module, "data_dir_for", fake_data_dir_for)
    monkeypatch.setenv("FATHOM_SEC_CONTACT", "t@example.com")

    result = runner.invoke(app, ["quote", "AAPL", "--source", "live"])

    assert result.exit_code == 0
    assert "AAPL" in result.stdout
    assert len(calls) == 1
    assert calls[0][0] == "AAPL"


def test_fr024_fetch_command_prints_filings_bars_and_snapshot_coverage(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path, tmp_path: Path
) -> None:
    import fathom.cli as cli_module
    from fathom.live.build import LiveManifest
    from fathom.live.sec import SecFiling

    fake_manifest = LiveManifest(
        ticker="AAPL",
        cik="0000320193",
        fetched_at="2026-09-01T00:00:00+00:00",
        data_dir=str(data_dir),
        filings=[
            SecFiling(
                cik="0000320193",
                accession="0000320193-25-000079",
                form="10-K",
                filing_date="2025-10-31",
                report_date="2025-09-27",
                primary_document="aapl-20250927.htm",
                url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
            )
        ],
        bars_source="yahoo via .cache/live/AAPL/bars.parquet",
        bars_from="2025-09-01",
        bars_to="2026-09-01",
        snapshot_source="SEC XBRL companyconcept (shares, EPS TTM, equity, DPS TTM) x yahoo close",
        sections_coverage={"0000320193-25-000079": ["10-K:1A", "10-K:7"]},
    )

    def fake_materialize(ticker: str, settings: object, force: bool = False) -> LiveManifest:
        return fake_manifest

    monkeypatch.setattr(cli_module, "materialize", fake_materialize)

    result = runner.invoke(app, ["fetch", "AAPL"])

    assert result.exit_code == 0
    assert "cik=0000320193" in result.stdout
    assert "10-K 2025-10-31 0000320193-25-000079 sections=10-K:1A,10-K:7" in result.stdout
    assert "bars 2025-09-01..2026-09-01 source=yahoo via .cache/live/AAPL/bars.parquet" in (
        result.stdout
    )
    assert "snapshot=" in result.stdout
    assert "fields_present=" in result.stdout


def test_fr024_fetch_command_propagates_source_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FATHOM_SEC_CONTACT", raising=False)

    result = runner.invoke(app, ["fetch", "AAPL"])

    assert result.exit_code == 2
    assert "error SOURCE_CONFIG:" in result.output
