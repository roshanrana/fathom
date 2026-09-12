---
id: T-009
title: CLI and HTTP API
milestone: M3
risk: medium
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-001, T-006, T-007]
rtm: [FR-013, FR-014]
status: todo
---
# T-009 — CLI and HTTP API

## Goal
`fathom` Typer CLI and the FastAPI app exposing the frozen contracts through the LLD envelope;
`fathom probe` for interview-day gateway checks.

## Spec references
`03-lld.md §4` (verbatim): CLI: `fathom quote T`, `fathom filings T`, `fathom brief T [--json]`,
`fathom ask T "question" [--json]`, `fathom bench [--out metrics/headline.json]`, `fathom probe`
(sends `{"ping": true}` with `SYSTEM_PROBE`, prints provider, model, latency, first 80 chars of
the reply), `fathom app` (streamlit run app/main.py), `fathom api [--port 8000]`, `fathom mcp`.
`FathomError` → stderr `error <CODE>: <message>` and exit 2. API:

| Method | Path | Response `data` |
|---|---|---|
| GET | `/healthz` | `{"status": "ok", "provider": name, "version": str}` |
| GET | `/api/quote/{ticker}` | `QuoteCard` |
| GET | `/api/filings/{ticker}` | `list[Filing]` |
| POST | `/api/brief/{ticker}` | `Briefing` |
| POST | `/api/ask/{ticker}` body `{"question": str}` | `Answer` |

Envelope: `{"ok": bool, "data": object | null, "error": {"code": str, "message": str} | null,
"meta": {"ticker": str | null, "provider": str, "generated_at": iso}}`. Status: 200;
`UNKNOWN_TICKER` → 404; `PROVIDER_CONFIG` → 503; `PROVIDER_HTTP`/`PROVIDER_TIMEOUT` → 502;
`CONTRACT_INVALID` → 502; validation → 422; anything else → 500 with `{"code": "INTERNAL",
"message": "internal error"}`. `create_app(settings: Settings | None = None) -> FastAPI`.
`bench` and `mcp` commands: import lazily (`from fathom.bench import run_bench` inside the
command) and, if the module is missing, print `error NOT_AVAILABLE: bench arrives in T-010` /
`… mcp arrives in T-012` and exit 2 — T-010/T-012 will not need to edit cli.py beyond nothing
(they provide the modules). Non-JSON `brief`/`ask` output: a readable text rendering (section
headers, "- text [verified|unverified|removed] (form date section)").

## Scope (files this task may touch)
- fathom/cli.py, fathom/api.py
- pyproject.toml (add `[project.scripts] fathom = "fathom.cli:app"` only)
- tests/test_cli.py, tests/test_api.py

## Acceptance criteria
- AC1: `CliRunner().invoke(app, ["quote", "AAPL"])` exit 0 and output contains "AAPL" and the last close; `["brief", "AAPL", "--json"]` outputs JSON that `Briefing.model_validate_json` accepts; `["ask", "AAPL", "main risk factors", "--json"]` validates as `Answer`; `["quote", "ZZZZ"]` exit 2 with `error UNKNOWN_TICKER:` on stderr.
- AC2: `["probe"]` with `FATHOM_LLM_PROVIDER=offline` prints "offline", "extractive-v1" and "pong".
- AC3: `TestClient(create_app())`: `/healthz` ok envelope; `/api/quote/AAPL` data validates as `QuoteCard`; `/api/filings/AAPL` returns 5 items; `/api/brief/AAPL` (POST) validates as `Briefing`; `/api/ask/AAPL` with `{"question": "main risk factors"}` validates as `Answer`; `/api/quote/ZZZZ` → 404 with `error.code == "UNKNOWN_TICKER"`; POST `/api/ask/AAPL` with `{}` → 422.
- AC4: A route that raises a generic `RuntimeError` (monkeypatched `quote_card`) returns 500 with `{"code": "INTERNAL", "message": "internal error"}` and no traceback text; `PROVIDER_CONFIG` → 503 with the variable name in the message.
- AC5: `meta.provider` reflects `Settings.llm_provider`; every response has all four envelope keys.
- AC6: mypy strict clean for both modules; tests named `test_fr013_*`, `test_fr014_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_cli.py tests/test_api.py -q`
- `uv run ruff check fathom/cli.py fathom/api.py tests && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] error taxonomy mapped exactly as the table
- [ ] 500 body has no internals
- [ ] tests named with RTM IDs
- [ ] no new dependencies (fastapi/uvicorn/typer already declared)

## Threat-model boundary touched
B1 (HTTP input validation; error disclosure) — Security Reviewer at T2.

## Handoff (Implementer fills, ≤10 lines)
