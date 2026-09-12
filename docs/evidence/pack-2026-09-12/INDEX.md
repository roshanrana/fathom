# Evidence pack

Generated 2026-09-12T22:11:06.200045+00:00
Entries: 42  Chain: valid

| Seq | Kind | Ref | Role | Tier | Approver role | Artifacts |
|---|---|---|---|---|---|---|
| 1 | gate | G0 | Architect | T3 | delivery_lead | 00-problem-brief.md, decisions.md (CHANGED since ledger) |
| 2 | gate | G1 | Architect | T3 | delivery_lead | 01-requirements.md |
| 3 | gate | G2 | Architect | T3 | architecture_review | 02-hld.md, 02-threat-model.md (CHANGED since ledger), decisions.md (CHANGED since ledger), model-routing.yaml |
| 4 | gate | G3 | Architect | T3 | architecture_lead | 03-lld.md (CHANGED since ledger) |
| 5 | gate | G4 | Planner | T3 | delivery_lead | 04-execution-plan.md (CHANGED since ledger), T-000-foundation-skeleton.md (CHANGED since ledger), T-006-briefing.md (CHANGED since ledger) |
| 6 | task | FOUNDATION-DATA | Orchestrator | T0 | ci | fetch_data.py, SOURCES.md |
| 7 | task | T-001 | Verifier | T2 | ci | T-001.verdict.md, quotes.py (CHANGED since ledger) |
| 8 | task | T-000 | Verifier | T2 | ci | T-000.verdict.md, pyproject.toml (CHANGED since ledger), check.py (CHANGED since ledger) |
| 9 | task | T-002 | Verifier | T2 | ci | T-002.verdict.md, filings.py (CHANGED since ledger) |
| 10 | task | T-004 | Verifier | T2 | ci | T-004.verdict.md, T-004.security.md, providers.py (CHANGED since ledger) |
| 11 | task | T-003 | Verifier | T2 | ci | T-003.verdict.md, retrieval.py (CHANGED since ledger) |
| 12 | gate | G5 | Evidence | T0 | ci | check.py (CHANGED since ledger), check.yml, SOURCES.md |
| 13 | task | T-005 | Verifier | T2 | ci | T-005.verdict.md, T-005.security.md, guard.py (CHANGED since ledger), contracts.py, audit.py |
| 14 | gate | G3-reentry | Architect | T3 | architecture_lead | 03-lld.md (CHANGED since ledger), decisions.md (CHANGED since ledger), T-013-polish-parser-guard.md (CHANGED since ledger) |
| 15 | task | T-007 | Verifier | T2 | ci | T-007.verdict.md, T-007.security.md, ask.py (CHANGED since ledger) |
| 16 | task | T-008 | Verifier | T2 | ci | T-008.verdict.md, main.py (CHANGED since ledger) |
| 17 | task | T-014 | Verifier | T2 | ci | T-014.verdict.md, T-014.security.md |
| 18 | task | T-006 | Verifier | T2 | ci | T-006.verdict.md, T-006.security.md, briefing.py (CHANGED since ledger) |
| 19 | task | T-009 | Verifier | T2 | ci | T-009.verdict.md, T-009.security.md, api.py (CHANGED since ledger), cli.py (CHANGED since ledger) |
| 20 | gate | G3-reentry-2 | Architect | T3 | architecture_lead | 03-lld.md (CHANGED since ledger), decisions.md (CHANGED since ledger), T-013-polish-parser-guard.md (CHANGED since ledger) |
| 21 | task | T-010 | Verifier | T2 | ci | T-010.verdict.md, bench.py (CHANGED since ledger), headline.json (CHANGED since ledger) |
| 22 | gate | G6.1 | Evidence | T0 | ci | quotes.py (CHANGED since ledger), filings.py (CHANGED since ledger), retrieval.py (CHANGED since ledger) |
| 23 | gate | G6.2 | Evidence | T0 | ci | briefing.py (CHANGED since ledger), ask.py (CHANGED since ledger), providers.py (CHANGED since ledger), guard.py (CHANGED since ledger) |
| 24 | task | T-012 | Verifier | T2 | ci | T-012.verdict.md, mcp_server.py (CHANGED since ledger) |
| 25 | task | T-013 | Verifier | T2 | ci | T-013.verdict.md, T-013.security.md, filings.py (CHANGED since ledger), guard.py, headline.json (CHANGED since ledger) |
| 26 | task | T-016 | Verifier | T2 | ci | T-016.verdict.md, providers.py, rendering.py (CHANGED since ledger) |
| 27 | task | T-015 | Verifier | T2 | ci | T-015.verdict.md, T-015.security.md, providers.py, cli.py (CHANGED since ledger) |
| 28 | task | T-017 | Verifier | T2 | ci | T-017.verdict.md, rendering.py (CHANGED since ledger) |
| 29 | task | T-011 | Verifier | T2 | ci | T-011.verdict.md, README.md (CHANGED since ledger), SHOWCASE.md (CHANGED since ledger) |
| 30 | gate | G6.3 | Evidence | T0 | ci | card.md, SHOWCASE.md (CHANGED since ledger) |
| 31 | gate | G7 | Architect | T3 | delivery_lead | assurance-report.md (CHANGED since ledger) |
| 32 | gate | G8 | Evidence | T0 | release_manager | orr.md (CHANGED since ledger), change-record.md (CHANGED since ledger), runbook.md (CHANGED since ledger), fathom-pitch.pptx |
| 33 | gate | G4-M4 | Planner | T3 | delivery_lead | 05-m4-live-data.md (CHANGED since ledger), decisions.md (CHANGED since ledger), T-020-live-materialize-wiring.md (CHANGED since ledger) |
| 34 | task | T-018 | Verifier | T2 | ci | T-018.verdict.md, T-018.security.md, sec.py (CHANGED since ledger), http.py (CHANGED since ledger) |
| 35 | task | T-022 | Verifier | T2 | ci | T-022.verdict.md, T-022.security.md, http.py, sec.py (CHANGED since ledger) |
| 36 | task | T-020 | Verifier | T2 | ci | T-020.verdict.md, T-020.security.md, build.py, data.py |
| 37 | task | T-021 | Verifier | T2 | ci | T-021.verdict.md, test_live_network.py, README.md |
| 38 | task | T-019 | Verifier | T2 | ci | T-019.verdict.md, T-019.security.md, prices.py (CHANGED since ledger), facts.py (CHANGED since ledger) |
| 39 | task | T-023 | Verifier | T2 | ci | T-023.verdict.md, T-023.security.md, prices.py (CHANGED since ledger), facts.py (CHANGED since ledger) |
| 40 | task | T-024 | Verifier | T2 | ci | T-024.verdict.md, T-024.security.md, sec.py |
| 41 | gate | G6.4 | Evidence | T0 | ci | build.py, sec.py, prices.py, facts.py |
| 42 | gate | G7-M4 | Architect | T3 | delivery_lead | assurance-report.md |
