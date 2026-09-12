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

## Live data mode (T-021, `docs/design/05-m4-live-data.md`)

Separate from the LLM provider switch above: `FATHOM_DATA_SOURCE` controls where filings, prices
and the valuation snapshot come from.

| Variable | Default | Live data demo |
|---|---|---|
| `FATHOM_DATA_SOURCE` | `fixture` | `live` |
| `FATHOM_SEC_CONTACT` | unset | required — an operator contact address, never committed |
| `FATHOM_LIVE_CACHE_DIR` | `.cache/live` | same |
| `FATHOM_LIVE_TTL_HOURS` | `6` | same |
| `FATHOM_PRICE_SOURCE` | `yahoo` | same (`stooq` is the automatic fallback) |

Start: `FATHOM_DATA_SOURCE=live FATHOM_SEC_CONTACT=<contact> uv run fathom fetch TICKER --force`
pre-warms the cache and prints filing/bars/snapshot coverage — run this once before a live demo
to confirm the network path works. Fallback: unset `FATHOM_DATA_SOURCE` (or `--source fixture`
on any command) to return instantly to the offline 20-ticker fixture universe — no restart of the
gate or CI is ever required, since neither touches the network (NFR-013).

| Symptom | Cause | Action |
|---|---|---|
| `error SOURCE_CONFIG: FATHOM_SEC_CONTACT is required...` | live mode without a contact | export `FATHOM_SEC_CONTACT`, or drop back to `--source fixture` |
| `error SOURCE_HTTP: ...` | SEC/Yahoo/Stooq unreachable, rate-limited, or returned a non-data page (e.g. Stooq's bot-challenge HTML) | retry once; fall back to `--source fixture` for the demo |
| `error SOURCE_EMPTY: no bars for '<TICKER>'` | ticker known to EDGAR but Yahoo/Stooq have no bars, or no 10-K/10-Q in the last 24 months | try a different ticker; this is a real data gap, not a bug |
| Live fetch feels stale | inside the 6h TTL | `fathom fetch TICKER --force` bypasses it |

The opt-in network smoke test — never run by the gate or CI —
`FATHOM_NETWORK_TESTS=1 FATHOM_SEC_CONTACT=<contact> uv run pytest tests/test_live_network.py -q`
exercises this same path end to end against two real tickers (NFLX, COST) outside the fixture
universe.

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
