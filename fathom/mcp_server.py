"""FastMCP stdio server exposing four Fathom tools (LLD §4).

Each tool builds `Settings.from_env()` at call time (not at import time), so the process
environment (e.g. `FATHOM_LLM_PROVIDER`, `FATHOM_DATA_DIR`, Portkey/Anthropic keys) is honoured
the same way it is for the CLI and HTTP API. Tools never raise: a `FathomError` is caught and
turned into the JSON text `{"ok": false, "error": {"code", "message"}}`; on success a tool
returns `model_dump_json()` of the frozen contract (or, for `list_filings`, the JSON array of
`Filing.model_dump(mode="json")`). Every tool description ends with the disclaimer so an MCP
host surfaces it to the caller without an extra round trip.
"""

from __future__ import annotations

import json
from typing import Literal

from mcp.server.fastmcp import FastMCP

from fathom.ask import ask as ask_flow
from fathom.briefing import brief as brief_flow
from fathom.config import Settings
from fathom.errors import FathomError
from fathom.filings import filings_for
from fathom.live import data_dir_for
from fathom.quotes import quote_card

_DISCLAIMER = Settings().disclaimer

_GET_QUOTE_DESC = (
    "Reproducible price snapshot for a ticker in Fathom's fixed universe: last close, "
    "change, 52-week range, YTD/1y/30d performance, and valuation multiples. "
    f"{_DISCLAIMER}"
)
_LIST_FILINGS_DESC = (
    "List a ticker's 10-K/10-Q filings on file, newest first, with accession numbers and "
    f"EDGAR URLs. {_DISCLAIMER}"
)
_GET_BRIEFING_DESC = (
    "Generate an advisor briefing for a ticker from its most recent 10-K and two most recent "
    "10-Qs: business snapshot, latest results, risks, liquidity/capital, notable disclosures, "
    f"and talking points, each claim cited and verified against the filing text. {_DISCLAIMER}"
)
_ASK_FILINGS_DESC = (
    "Answer a grounded question about a ticker's filings, citing and verifying every claim "
    f"against the retrieved filing text. {_DISCLAIMER}"
)

server = FastMCP("fathom")


def _error_json(exc: FathomError) -> str:
    """The frozen error envelope for a caught `FathomError`, as JSON text."""
    return json.dumps({"ok": False, "error": {"code": exc.code.value, "message": exc.message}})


def _settings(source: Literal["fixture", "live"] | None) -> Settings:
    """`Settings.from_env()`, optionally overridden by an explicit `source` argument."""
    settings = Settings.from_env()
    if source is not None:
        settings = settings.model_copy(update={"data_source": source})
    return settings


@server.tool(description=_GET_QUOTE_DESC)
def get_quote(ticker: str, source: Literal["fixture", "live"] | None = None) -> str:
    """Return `QuoteCard.model_dump_json()` for `ticker`, or the error envelope."""
    settings = _settings(source)
    try:
        card = quote_card(ticker, data_dir_for(ticker, settings))
    except FathomError as exc:
        return _error_json(exc)
    return card.model_dump_json()


@server.tool(description=_LIST_FILINGS_DESC)
def list_filings(ticker: str, source: Literal["fixture", "live"] | None = None) -> str:
    """Return the JSON array of `Filing` records for `ticker`, or the error envelope."""
    settings = _settings(source)
    try:
        filings = filings_for(ticker, data_dir_for(ticker, settings))
    except FathomError as exc:
        return _error_json(exc)
    return json.dumps([filing.model_dump(mode="json") for filing in filings])


@server.tool(description=_GET_BRIEFING_DESC)
def get_briefing(ticker: str, source: Literal["fixture", "live"] | None = None) -> str:
    """Return `Briefing.model_dump_json()` for `ticker`, or the error envelope."""
    settings = _settings(source)
    try:
        briefing = brief_flow(ticker, settings)
    except FathomError as exc:
        return _error_json(exc)
    return briefing.model_dump_json()


@server.tool(description=_ASK_FILINGS_DESC)
def ask_filings(
    ticker: str, question: str, source: Literal["fixture", "live"] | None = None
) -> str:
    """Return `Answer.model_dump_json()` for `question` about `ticker`, or the error envelope."""
    settings = _settings(source)
    try:
        answer = ask_flow(ticker, question, settings)
    except FathomError as exc:
        return _error_json(exc)
    return answer.model_dump_json()


def main() -> None:
    """Entry point for `fathom mcp`: run the server over stdio."""
    server.run()


__all__ = ["server", "main"]
