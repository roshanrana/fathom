# Runbook — Fathom (prototype)

## Start / stop

| Action | Command |
|---|---|
| Install | `uv sync --all-extras` |
| Gate (everything) | `uv run python scripts/check.py` |
| Advisor page | `uv run fathom app` (Streamlit, http://localhost:8501) |
| HTTP API | `uv run fathom api --port 8000` (binds 127.0.0.1; `--host 0.0.0.0` only behind SSO) |
| MCP server | `uv run fathom mcp` (stdio; see `docs/mcp.md`) |
| CLI briefing | `uv run fathom brief AAPL` / `--json` |
| Gateway check | `uv run fathom probe` |
| Stop | Ctrl+C in the terminal that started the process; nothing runs in the background |

## Modes

| Variable | Default | Live demo |
|---|---|---|
| `FATHOM_LLM_PROVIDER` | `offline` | `portkey` |
| `PORTKEY_API_KEY` | unset | issued at the interview; set in the shell only, never in a file |
| `PORTKEY_BASE_URL` | `https://portkeygateway.perficient.com/v1` | same |
| `PORTKEY_MODEL` | `@aws-bedrock-use2/us.anthropic.claude-sonnet-4-5-20250929-v1:0` | same |
| `FATHOM_AUDIT_PATH` | `audit/fathom-audit.jsonl` | same |
| `FATHOM_AUDIT_BODIES` | `0` | `1` only if the panel asks to see prompts |

Switching modes is an environment change followed by a restart of the surface.

## Common failures

| Symptom | Cause | Action |
|---|---|---|
| `error PROVIDER_CONFIG: missing required environment variable PORTKEY_API_KEY` | live mode without a key | export the key, or set `FATHOM_LLM_PROVIDER=offline` |
| `error PROVIDER_HTTP: portkey provider returned HTTP 401/403` | wrong key or model catalogue name | check the key; confirm `PORTKEY_MODEL` with the gateway owner; `fathom probe` |
| `error PROVIDER_TIMEOUT` | gateway slow or outbound HTTPS blocked | retry once; fall back to offline for the demo |
| `error CONTRACT_INVALID` after a repair retry | model returned non-JSON twice | rerun; if persistent, fall back to offline and note it |
| `error UNKNOWN_TICKER` | ticker outside the 20-ticker universe | choose a listed ticker (message lists them) |
| Briefing shows "⚠️ unverified" claims | model paraphrased instead of quoting | expected in live mode; the badge is the control; the audit line records the share |
| Bench drift step fails in the gate | `metrics/headline.json` changed | run `uv run python -m fathom.bench && uv run python metrics/render.py` and commit if the change is intended |

## Escalation

Single-owner prototype: Roshan Rana. No on-call. Hosting would add SSO, a tamper-evident audit sink and alerting on verified share and guard hits (see `docs/ops/orr.md`).

## Data refresh

`uv run --with pandas --with pyarrow python scripts/fetch_data.py` rebuilds `data/` from the four
Hugging Face datasets and rewrites `data/SOURCES.md` (anchors change; T-001 tests must be updated
to the new anchors).
