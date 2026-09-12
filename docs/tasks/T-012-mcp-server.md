---
id: T-012
title: MCP server (Could)
milestone: M3
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-006, T-007]
rtm: [FR-019]
status: done
---
# T-012 — MCP server (Could)

## Goal
`fathom mcp` runs a stdio MCP server exposing `get_quote`, `list_filings`, `get_briefing`,
`ask_filings`, returning the frozen JSON contracts; tool descriptions end with the disclaimer.

## Spec references
`03-lld.md §4` (verbatim): MCP tools (optional): `get_quote(ticker)`, `list_filings(ticker)`,
`get_briefing(ticker)`, `ask_filings(ticker, question)` → JSON of the contracts above;
descriptions end with the disclaimer. Optional dependency group `mcp` (`mcp>=1.9,<2`), already
declared in `pyproject.toml` by T-000. Use `mcp.server.fastmcp.FastMCP("fathom")`; each tool
returns `model_dump_json()` of the contract; `FathomError` → return
`{"ok": false, "error": {"code", "message"}}` as JSON text (tools never raise). Entry:
`fathom/mcp_server.py: main() -> None` running `server.run()`; `cli.py` already dispatches
`fathom mcp` to `fathom.mcp_server.main` lazily (T-009).

## Scope (files this task may touch)
- fathom/mcp_server.py
- tests/test_mcp.py
- docs/mcp.md (how to register with Claude Desktop / Claude Code: command `uv`, args `["run", "fathom", "mcp"]`, cwd = repo)

## Acceptance criteria
- AC1: The four tools are registered with the names above; each description ends with `Settings().disclaimer`.
- AC2: Calling the tool functions directly (offline settings): `get_quote("AAPL")` JSON validates as `QuoteCard`; `list_filings("AAPL")` has 5 items; `get_briefing("AAPL")` validates as `Briefing`; `ask_filings("AAPL", "main risk factors")` validates as `Answer`; `get_quote("ZZZZ")` returns the error envelope with `UNKNOWN_TICKER`.
- AC3: An in-process MCP client session (`mcp.client.stdio` or the FastMCP test helpers) lists the four tools — if stdio spawning is unreliable on Windows, the test may instead exercise `server._tool_manager.list_tools()` and note it in the handoff.
- AC4: mypy strict clean (the `mcp` package is typed); tests named `test_fr019_*`; the test module skips cleanly if `mcp` is not installed.

## Validation commands (targeted)
- `uv run pytest tests/test_mcp.py -q`
- `uv run ruff check fathom/mcp_server.py tests/test_mcp.py && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] tools never raise; error envelope used
- [ ] disclaimer on every description
- [ ] tests named with RTM IDs
- [ ] no new dependencies beyond the declared `mcp` group

## Threat-model boundary touched
B1 (tool input is untrusted; goes through the same guard via `ask`).

## Handoff (Implementer fills, ≤10 lines)

Delivered `fathom/mcp_server.py` (FastMCP("fathom"), 4 tools: get_quote/list_filings/get_briefing/ask_filings,
each returns JSON text — `model_dump_json()`/dumped list, never raises, catches `FathomError` into
`{"ok": false, "error": {...}}`; descriptions end with `Settings().disclaimer`), `tests/test_mcp.py`
(8 tests, `test_fr019_*`, `pytest.importorskip("mcp")`), and `docs/mcp.md`. AC1-AC4 met.
AC3: used in-process `mcp.shared.memory.create_connected_server_and_client_session` (Windows-stable,
same pattern as lodestar's template) rather than real stdio spawn — noted here per the AC's fallback clause.
Targeted tests/ruff/mypy all green. Full gate (`uv run python scripts/check.py`): 1 failure,
`tests/test_cli.py::test_fr013_mcp_reports_not_available_before_t012_ships` — pre-existing stub test
(cli.py/test_cli.py are in T-013's scope, not mine) that calls `runner.invoke(app, ["mcp"])`; now that
`fathom.mcp_server` exists, `main()`/`server.run()` runs for real under CliRunner's captured stdio and
raises before reaching its own `if exit_code == 0: pytest.skip(...)` guard. Everything else (226 other
tests) passes; this is the only failure and it's outside my scope — flagging for T-013/cli owner to
update the test (e.g. skip/mock `server.run()` when invoking `mcp` under CliRunner).
