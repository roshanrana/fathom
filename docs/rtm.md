# Requirements Traceability Matrix

Regenerated 2026-09-12T15:54Z by `scripts/evidence.py rtm`.

| Req | Design § | Tasks | Tests | Evidence seq | Status |
|---|---|---|---|---|---|
| FR-001 | — | T-000(done) | tests\test_config.py, tests\test_data.py | — | covered |
| FR-002 | 02-hld.md: Critical flows | T-001(done) | tests\test_quotes.py | — | covered |
| FR-003 | — | T-001(done) | tests\test_quotes.py | — | covered |
| FR-004 | — | T-002(done) | tests\test_filings.py | — | covered |
| FR-005 | — | T-002(done), T-013(verify) | tests\test_filings.py | — | in progress |
| FR-006 | — | T-006(done), T-014(done) | tests\test_briefing.py | — | covered |
| FR-007 | — | T-005(done), T-006(done) | tests\test_briefing.py, tests\test_contracts.py | — | covered |
| FR-008 | 02-hld.md: Critical flows; 02-threat-model.md: STRIDE table | T-005(done), T-013(verify) | tests\test_guard.py | — | in progress |
| FR-009 | 02-hld.md: Critical flows | T-003(done), T-007(done), T-014(done) | tests\test_ask.py, tests\test_retrieval.py | — | covered |
| FR-010 | 02-hld.md: Critical flows | T-004(done) | tests\test_prompts.py, tests\test_providers.py | — | covered |
| FR-011 | 02-hld.md: Critical flows; 02-hld.md: Cross-cutting concerns; 02-hld.md: Data architecture | T-005(done) | tests\test_audit.py | — | covered |
| FR-012 | — | T-008(done) | tests\test_app.py | — | covered |
| FR-013 | — | T-009(done) | tests\test_cli.py | — | covered |
| FR-014 | — | T-009(done) | tests\test_api.py | — | covered |
| FR-015 | 02-hld.md: Critical flows | T-010(done), T-013(verify) | tests\test_bench.py | — | in progress |
| FR-016 | 02-hld.md: Critical flows | T-000(done) | — | — | NO TEST (G7 blocker) |
| FR-017 | — | T-011(verify) | — | — | NO TEST (G7 blocker) |
| FR-018 | 02-threat-model.md: AI-risk section (controls-evidence §8); 02-threat-model.md: STRIDE table | T-006(done), T-013(verify), T-014(done) | tests\test_briefing.py | — | in progress |
| FR-019 | — | T-012(done) | tests\test_mcp.py | — | covered |
| NFR-001 | 02-hld.md: NFR design | T-010(done) | tests\test_bench.py | — | covered |
| NFR-002 | 02-hld.md: NFR design | — | — | — | NO TASK (G4 finding) |
| NFR-003 | 02-hld.md: NFR design | T-000(done) | tests\test_config.py | — | covered |
| NFR-004 | 02-hld.md: NFR design | T-010(done) | tests\test_bench.py | — | covered |
| NFR-005 | 02-hld.md: NFR design | T-000(done), T-004(done) | tests\test_config.py, tests\test_data.py, tests\test_errors.py, tests\test_prompts.py, tests\test_providers.py | — | covered |
| NFR-006 | — | T-005(done) | tests\test_audit.py | — | covered |
| NFR-007 | 02-hld.md: NFR design | T-006(done), T-010(done), T-013(verify) | tests\test_bench.py, tests\test_briefing.py | — | in progress |
| NFR-008 | 02-hld.md: NFR design | T-005(done), T-010(done), T-013(verify) | tests\test_bench.py, tests\test_guard.py | — | in progress |
| NFR-009 | 02-hld.md: NFR design | T-000(done) | tests\test_data.py | — | covered |
| NFR-010 | 02-hld.md: NFR design | T-004(done) | tests\test_providers.py | — | covered |
| NFR-011 | 02-hld.md: NFR design | T-008(done) | tests\test_app.py | — | covered |
