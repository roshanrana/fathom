"""Fathom Typer CLI (LLD §4).

Commands: `quote`, `filings`, `brief`, `ask`, `bench`, `probe`, `app`, `api`, `mcp`. Every
`FathomError` is surfaced the same way: `error <CODE>: <message>` on stderr, exit code 2
(LLD §7). `bench` and `mcp` depend on modules shipped by later tasks (T-010, T-012); they are
imported lazily so this module works before those modules exist.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from fathom.ask import ask as ask_flow
from fathom.audit import AuditRecord, record
from fathom.briefing import brief as brief_flow
from fathom.config import Settings
from fathom.contracts import Answer, Briefing, Claim
from fathom.errors import FathomError
from fathom.filings import Filing, filings_for
from fathom.prompts import CANONICAL_SECTIONS, SYSTEM_PROBE
from fathom.providers import make_provider
from fathom.quotes import quote_card

app = typer.Typer(add_completion=False, no_args_is_help=True)

_PROBE_PING = '{"ping": true}'
_PROBE_MAX_TOKENS = 16

JsonOption = Annotated[bool, typer.Option("--json", help="Emit the raw JSON contract.")]
PortOption = Annotated[int, typer.Option("--port", help="Port for the HTTP API.")]
OutOption = Annotated[Path, typer.Option("--out", help="Where to write the headline metrics.")]


def _fail(exc: FathomError) -> NoReturn:
    """Render a `FathomError` the frozen way and exit 2 (LLD §7)."""
    typer.echo(f"error {exc.code}: {exc.message}", err=True)
    raise typer.Exit(2)


@app.command()
def quote(ticker: str) -> None:
    """Show a reproducible quote snapshot for TICKER."""
    settings = Settings.from_env()
    try:
        card = quote_card(ticker, settings.data_dir)
    except FathomError as exc:
        _fail(exc)
    typer.echo(
        f"{card.ticker} last close {card.last_close:.2f} "
        f"({card.change_pct:+.2f}%) as of {card.as_of}"
    )


@app.command()
def filings(ticker: str) -> None:
    """List TICKER's 10-K/10-Q filings, newest first."""
    settings = Settings.from_env()
    try:
        rows = filings_for(ticker, settings.data_dir)
    except FathomError as exc:
        _fail(exc)
    for filing in rows:
        typer.echo(f"{filing.accession} {filing.form} {filing.filing_date} {filing.edgar_url}")


def _filings_by_accession(ticker: str, data_dir: Path) -> dict[str, Filing]:
    """Best-effort accession -> `Filing` lookup for text rendering; empty on failure."""
    try:
        return {row.accession: row for row in filings_for(ticker, data_dir)}
    except FathomError:
        return {}


def _claim_state(claim: Claim) -> str:
    if claim.guarded:
        return "removed"
    return "verified" if claim.verified else "unverified"


def _claim_line(claim: Claim, filings_by_accession: dict[str, Filing]) -> str:
    """One line of the readable rendering: `- text [state] (form date section)`."""
    filing = filings_by_accession.get(claim.source.accession)
    form = filing.form if filing is not None else "?"
    filing_date = filing.filing_date.isoformat() if filing is not None else "?"
    section = CANONICAL_SECTIONS.get(claim.source.section_id, claim.source.section_id or "?")
    return f"- {claim.text} [{_claim_state(claim)}] ({form} {filing_date} {section})"


def _render_briefing(briefing: Briefing) -> str:
    filings_by_accession = {row.accession: row for row in briefing.filings_used}
    sections: list[tuple[str, list[Claim]]] = [
        ("Business Snapshot", briefing.business_snapshot),
        ("Latest Results", briefing.latest_results),
        ("Risks", briefing.risks),
        ("Liquidity & Capital", briefing.liquidity_capital),
        ("Notable Disclosures", briefing.notable_disclosures),
        ("Talking Points", briefing.talking_points),
    ]
    lines = [f"{briefing.ticker} — {briefing.company}", ""]
    for header, claims in sections:
        lines.append(f"{header}:")
        for claim in claims:
            lines.append(_claim_line(claim, filings_by_accession))
        lines.append("")
    lines.append(briefing.disclaimer)
    return "\n".join(lines)


def _render_answer(answer: Answer, filings_by_accession: dict[str, Filing]) -> str:
    lines = [answer.ticker, ""]
    if answer.not_found:
        lines.append("(no answer found in the filings)")
    for claim in answer.claims:
        lines.append(_claim_line(claim, filings_by_accession))
    lines.append("")
    lines.append(answer.disclaimer)
    return "\n".join(lines)


@app.command()
def brief(ticker: str, json_output: JsonOption = False) -> None:
    """Produce an advisor briefing for TICKER."""
    settings = Settings.from_env()
    try:
        result = brief_flow(ticker, settings)
    except FathomError as exc:
        _fail(exc)
    if json_output:
        typer.echo(result.model_dump_json())
    else:
        typer.echo(_render_briefing(result))


@app.command()
def ask(ticker: str, question: str, json_output: JsonOption = False) -> None:
    """Ask a grounded question about TICKER's filings."""
    settings = Settings.from_env()
    try:
        result = ask_flow(ticker, question, settings)
    except FathomError as exc:
        _fail(exc)
    if json_output:
        typer.echo(result.model_dump_json())
    else:
        filings_by_accession = _filings_by_accession(ticker, settings.data_dir)
        typer.echo(_render_answer(result, filings_by_accession))


@app.command()
def probe() -> None:
    """Ping the configured LLM provider and report provider, model, latency and reply."""
    settings = Settings.from_env()
    try:
        provider = make_provider(settings)
        result = provider.complete_json(SYSTEM_PROBE, _PROBE_PING, _PROBE_MAX_TOKENS)
    except FathomError as exc:
        _fail(exc)

    generated_at = datetime.now(UTC)
    record(
        settings,
        AuditRecord(
            ts=generated_at,
            ticker="",
            purpose="probe",
            provider=provider.name,
            model=provider.model,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            prompt_sha256=hashlib.sha256(SYSTEM_PROBE.encode()).hexdigest(),
            response_sha256=hashlib.sha256(result.text.encode()).hexdigest(),
            claims_total=0,
            claims_verified=0,
            guard_hits=0,
        ),
    )
    typer.echo(f"provider={provider.name} model={provider.model} latency_ms={result.latency_ms}")
    typer.echo(result.text[:80])


@app.command(name="app")
def run_app() -> None:
    """Launch the Streamlit UI (`streamlit run app/main.py`) as a subprocess."""
    repo_root = Path(__file__).resolve().parent.parent
    main_path = repo_root / "app" / "main.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(main_path)], check=False)


@app.command(name="api")
def run_api(port: PortOption = 8000) -> None:
    """Run the FastAPI app (`fathom.api:create_app`) with uvicorn."""
    import uvicorn

    uvicorn.run("fathom.api:create_app", factory=True, host="0.0.0.0", port=port)


@app.command()
def bench(out: OutOption = Path("metrics/headline.json")) -> None:
    """Run the offline benchmark and write the headline metrics (arrives in T-010)."""
    try:
        bench_module = import_module("fathom.bench")
    except ModuleNotFoundError:
        typer.echo("error NOT_AVAILABLE: bench arrives in T-010", err=True)
        raise typer.Exit(2) from None
    bench_module.run_bench(out)


@app.command()
def mcp() -> None:
    """Run the MCP stdio server (arrives in T-012)."""
    try:
        mcp_module = import_module("fathom.mcp_server")
    except ModuleNotFoundError:
        typer.echo("error NOT_AVAILABLE: mcp arrives in T-012", err=True)
        raise typer.Exit(2) from None
    mcp_module.main()


if __name__ == "__main__":
    app()
