# Operational readiness review — Fathom (prototype release 0.1.0)

Scope: a single-user demo on the owner's laptop for the Perficient AI Prototype Challenge
interview. Items marked "hosting" are what a pilot deployment adds; they are not claimed here.

| Item | Owner | Status | Evidence |
|---|---|---|---|
| SLOs defined and dashboards live | owner | prototype: NFR budgets in `01-requirements.md`; bench KPIs in `metrics/card.md`; no dashboard (hosting) | ledger G6.3, G7 |
| Alerts routed; paging tested | owner | not applicable (single user); alert candidates listed in LLD §9 (verified share < 0.7/day, guard hits > 0, PROVIDER_* rate) | LLD §9 |
| Runbook: start/stop, common failures, escalation | owner | done | `docs/ops/runbook.md` |
| On-call rota and escalation path | owner | single owner; no rota | runbook |
| Capacity vs projected load | owner | one advisor at a time; offline briefing ≈ 40 ms; live ≈ 60–90 s per briefing (one gateway call) | bench, audit log |
| Access review complete; break-glass documented | owner | no authn in the prototype (documented gap C-08); API binds loopback by default (D-008) | threat model B1, T-013 security |
| Secrets rotation schedule | owner | Portkey key issued at the interview, held in the shell only; rotate/revoke by the gateway owner after the session | runbook |
| Log retention configured per classification | owner | audit JSONL local, gitignored; bodies off by default; delete after the interview | LLD §2.9, §8 |
| Backup/restore drill; DR | owner | fixtures and code in git; `scripts/fetch_data.py` rebuilds data; no runtime state to restore | D-002 |
| Rollback rehearsed — time taken | owner | `git checkout <tag>` + `uv sync`; rehearsed in the worktree-based verification (each verifier resyncs a pinned commit in < 2 min) | verdict files |
| Change record approved | owner | `docs/ops/change-record.md` | ledger G8 |
| Model-risk sign-off (AI components) | owner | model inventory and controls in `02-threat-model.md` AI-risk section; eval suite in the gate; live verified share reported from the audit log, not asserted | ledger G7/G8 |
