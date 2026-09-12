# Change record — Fathom release 0.1.0

| Field | Value |
|---|---|
| Requested by | Roshan Rana (owner), for the Perficient AI Prototype Challenge, scenario 2 (Finance) |
| Implemented by | Sonnet Implementer agents, one task pack each (T-000 … T-014) |
| Verified by | Fresh-context Sonnet Verifier per task in a git worktree pinned to the task's commit; Sonnet Security Reviewer for every `risk: medium` task |
| Approved by | Roshan Rana under standing autonomous authorisation (D-000); gates G0–G8 ledgered in `docs/evidence/ledger.jsonl` |
| Description | New prototype: advisor stock briefing (quote card, recent SEC filings, verified-citation AI briefing, grounded Q&A) with Streamlit page, CLI, HTTP API and MCP server; offline / Portkey / Anthropic providers |
| Business justification | Demonstrate a viable, compliance-aware AI solution for the client scenario in a live interview |
| Systems affected | None in production. New repository `roshanrana/fathom`; outbound HTTPS to the Portkey gateway in live mode only |
| Risk assessment | Low: public data only, no PII, single user, loopback API; residual risks listed in `02-threat-model.md` and accepted by the owner |
| Implementation steps | `git clone`, `uv sync --all-extras`, `uv run python scripts/check.py`, `uv run fathom app` (see runbook) |
| Verification steps | Gate green locally and in CI; bench KPIs in `metrics/card.md`; all task verdicts PASS; security reviews CLEAR or findings closed (T-014, T-013) |
| Rollback plan and trigger | Any failure on the demo laptop: `FATHOM_LLM_PROVIDER=offline` restores a working demo without network or key; code rollback is `git checkout <previous tag>` |
| Schedule / window | Interview date set by Perficient; no production window |
| Communication plan | README, OVERVIEW, SHOWCASE and the pitch slide are the communication artefacts |
| Evidence pack | `docs/evidence/pack-2026-09-12/` (exported at G8) |

# Change record — Fathom release 0.2.0 (live data, M4)

| Field | Value |
|---|---|
| Requested by | Roshan Rana (owner): "make this project so it can work with data from live (but free) sources" |
| Implemented by | Sonnet Implementer agents, packs T-018 … T-024 |
| Verified by | Fresh-context Verifiers in pinned worktrees; fresh Security Reviewers per round (T-018/19/20/22/23/24) |
| Approved by | Roshan Rana under standing autonomous authorisation (D-000); G1–G4 re-entry for M4 (seq 33), G6.4/G7/G8 addenda |
| Description | Live mode: SEC EDGAR filings and XBRL facts, Yahoo/Stooq daily bars, materialized per ticker into the fixture schema; `fathom fetch`; `--source live` on CLI/API/MCP/page |
| Business justification | Any US-listed ticker, not only the 20 demo tickers, with no API keys |
| Systems affected | Outbound HTTPS to sec.gov, data.sec.gov, query1.finance.yahoo.com, stooq.com in live mode only |
| Risk assessment | Medium: new trust boundary B6; four security rounds hardened payload parsing; fixture mode unchanged; gate stays offline |
| Rollback | `FATHOM_DATA_SOURCE=fixture` (default) or `git checkout v0.1.0` |
| Verification | Real runs: NFLX, COST, BRK.B; network smoke test; gate 456 tests |
