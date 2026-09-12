"""Tests for fathom.mcp_server (LLD §4, MCP tools). RTM: FR-019.

Uses `mcp.shared.memory.create_connected_server_and_client_session` against the low-level
`Server` inside the `FastMCP` instance for the in-process tool-listing check (AC3) — this avoids
spawning a real stdio subprocess, which is unreliable on Windows. The per-tool contract checks
(AC2) call the underlying tool functions directly, the same way `fathom.cli` and `fathom.api`
call their flow functions, since FastMCP's `@server.tool()` decorator returns the original
callable unchanged.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402

from fathom import mcp_server  # noqa: E402
from fathom.config import Settings  # noqa: E402
from fathom.contracts import Answer, Briefing, Claim  # noqa: E402
from fathom.filings import Filing  # noqa: E402
from fathom.quotes import QuoteCard  # noqa: E402

_EXPECTED_TOOL_NAMES = {"get_quote", "list_filings", "get_briefing", "ask_filings"}


def _run[T](coro: Callable[[], Awaitable[T]]) -> T:
    return asyncio.run(coro())


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, data_dir: Path, tmp_path: Path) -> None:
    """Point every tool call at the real fixtures but an isolated, tmp_path audit log."""
    monkeypatch.setenv("FATHOM_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FATHOM_AUDIT_PATH", str(tmp_path / "audit" / "fathom-audit.jsonl"))
    monkeypatch.setenv("FATHOM_LLM_PROVIDER", "offline")


# --- AC1: tool names and disclaimer-terminated descriptions -------------------------------------


def test_fr019_lists_exactly_four_tools() -> None:
    async def body() -> set[str]:
        async with create_connected_server_and_client_session(
            mcp_server.server._mcp_server
        ) as session:
            await session.initialize()
            listed = await session.list_tools()
            return {tool.name for tool in listed.tools}

    names = _run(body)
    assert names == _EXPECTED_TOOL_NAMES


def test_fr019_every_tool_description_ends_with_disclaimer() -> None:
    async def body() -> dict[str, str | None]:
        async with create_connected_server_and_client_session(
            mcp_server.server._mcp_server
        ) as session:
            await session.initialize()
            listed = await session.list_tools()
            return {tool.name: tool.description for tool in listed.tools}

    descriptions = _run(body)
    disclaimer = Settings().disclaimer
    assert descriptions.keys() == _EXPECTED_TOOL_NAMES
    for name, description in descriptions.items():
        assert description is not None
        assert description.endswith(disclaimer), f"{name} description missing disclaimer"


# --- AC2: direct tool calls validate against the frozen contracts (offline settings) ------------


def test_fr019_get_quote_validates_as_quote_card() -> None:
    payload = mcp_server.get_quote("AAPL")

    QuoteCard.model_validate_json(payload)


def test_fr019_list_filings_has_five_items() -> None:
    payload = mcp_server.list_filings("AAPL")

    rows = json.loads(payload)
    assert len(rows) == 5
    for row in rows:
        Filing.model_validate(row)


def test_fr019_get_briefing_validates_as_briefing() -> None:
    payload = mcp_server.get_briefing("AAPL")

    Briefing.model_validate_json(payload)


def test_fr019_ask_filings_validates_as_answer() -> None:
    payload = mcp_server.ask_filings("AAPL", "main risk factors")

    answer = Answer.model_validate_json(payload)
    assert isinstance(answer.claims, list)
    for claim in answer.claims:
        assert isinstance(claim, Claim)


def test_fr019_get_quote_unknown_ticker_returns_error_envelope() -> None:
    payload = mcp_server.get_quote("ZZZZ")

    body = json.loads(payload)
    assert body["ok"] is False
    assert body["error"]["code"] == "UNKNOWN_TICKER"
    assert "message" in body["error"]


# --- AC3 (extra): a full in-process session can also call a tool and get the same JSON ----------


def test_fr019_session_call_tool_get_quote_matches_direct_call() -> None:
    async def body() -> str:
        async with create_connected_server_and_client_session(
            mcp_server.server._mcp_server
        ) as session:
            await session.initialize()
            result = await session.call_tool("get_quote", {"ticker": "AAPL"})
            assert not result.isError
            text: str = result.content[0].text
            return text

    payload = _run(body)
    QuoteCard.model_validate_json(payload)
