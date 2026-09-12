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
