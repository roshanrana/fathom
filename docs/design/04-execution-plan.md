# Execution plan — Fathom

## Milestones

| M | Name | Outcome | Gate |
|---|---|---|---|
| M0 | Walking skeleton | Fresh clone → `uv sync` → gate green → Streamlit page shows a company name and last close from the fixtures; CI runs the gate | G5 |
| M1 | Data layer | Quote card with derived context; filings list with EDGAR links; section parser covering all 97 filings; BM25 retrieval | G6.1 |
| M2 | Intelligence | Providers (offline / Portkey / Anthropic), guard, audit, contracts, briefing, grounded Q&A | G6.2 |
| M3 | Surfaces and assurance | Full Streamlit page, CLI, API, bench + metrics card, docs and screenshots, MCP (Could) | G6.3 → G7 |
| — | Pitch | One slide (`docs/pitch/`), demo checklist, evidence pack, ship | G8 |

Foundation items done by the Orchestrator as T0 scripts before T-000 dispatch (Phase 5):
`scripts/fetch_data.py` run once → `data/*.parquet`, `data/SOURCES.md` (with spot anchors);
graphify scaffold (`.graphifyignore`, `graphify-out/GRAPH_REPORT.md`, `.claude/skills/graphify`,
`CLAUDE.md` section) after T-000 lands.

## Task table

| Task | M | Title | Risk | Tier | Complexity | Budget (in-tok/calls/min) | Depends on | RTM |
|---|---|---|---|---|---|---|---|---|
| T-000 | M0 | Foundation and walking skeleton | low | T2 | high | 80000/80/120 | — | NFR-003, NFR-005, NFR-009, FR-001 |
| T-001 | M1 | Quote card and price context | low | T2 | normal | 40000/40/45 | T-000 | FR-002, FR-003 |
| T-002 | M1 | Filings list and section parser | low | T2 | high | 80000/80/120 | T-000 | FR-004, FR-005 |
| T-003 | M1 | BM25 retrieval | low | T2 | normal | 40000/40/45 | T-002 | FR-009 (retrieval half) |
| T-004 | M2 | Prompts and providers | medium | T2 | high | 80000/80/120 | T-000 | FR-010, NFR-005, NFR-010 |
| T-005 | M2 | Contracts, guard and audit | medium | T2 | high | 80000/80/120 | T-002 | FR-007, FR-008, FR-011, NFR-006, NFR-008 |
| T-006 | M2 | Briefing pipeline | medium | T2 | high | 80000/80/120 | T-002, T-004, T-005 | FR-006, FR-007, FR-018, NFR-007 |
| T-007 | M2 | Grounded Q&A | medium | T2 | normal | 40000/40/45 | T-003, T-004, T-005 | FR-009 |
| T-008 | M3 | Streamlit page | low | T2 | high | 80000/80/120 | T-001, T-006, T-007 | FR-012, NFR-011 |
| T-009 | M3 | CLI and HTTP API | medium | T2 | high | 80000/80/120 | T-001, T-006, T-007 | FR-013, FR-014 |
| T-010 | M3 | Bench and metrics card | low | T2 | high | 80000/80/120 | T-003, T-006, T-007 | FR-015, NFR-001, NFR-004, NFR-007, NFR-008 |
| T-011 | M3 | Documentation and screenshots | low | T2 | high | 80000/80/120 | T-008, T-009, T-010 | FR-017 |
| T-012 | M3 | MCP server (Could) | low | T2 | normal | 40000/40/45 | T-006, T-007 | FR-019 |
| T-013 | M3 | Polish — parser heading fallback, guard inflections, metrics regen (D-006) | medium | T2 | high | 80000/80/120 | T-006, T-007, T-010 | FR-005, FR-008, FR-015, FR-018, NFR-007, NFR-008 |

FR-016 (fetch script) is delivered by the Orchestrator's foundation step and verified by T-001's
fixture-schema tests. FR-017's pitch slide is produced by the Orchestrator at Phase 8.

## Dependency graph

```
T-000 ─┬─► T-001 ─────────────────────────┬─► T-008
       ├─► T-002 ─┬─► T-003 ─┬─► T-007 ───┼─► T-009 ─┬─► T-011
       │          ├─► T-005 ─┼─► T-006 ───┼─► T-010 ─┘
       └─► T-004 ─┘          └────────────┴─► T-012
```

## Wave schedule

| Wave | Tasks (disjoint scopes) | Max parallel |
|---|---|---|
| W1 | T-000 | 1 |
| W2 | T-001, T-002, T-004 | 3 |
| W3 | T-003, T-005 | 2 |
| W4 | T-006, T-007 | 2 |
| W5 | T-008, T-009, T-010 | 3 |
| W5b | T-013 (after T-010; serialised because it changes parser/guard outputs and the metrics) | 1 |
| W6 | T-011, T-012 | 2 |

Each completed task: Verifier (fresh Sonnet context, worktree pinned to the task's commit) →
Security Reviewer for `risk: medium` (Sonnet, diff + threat-model boundary) → `check` → evidence
→ STATE.md → commit `T-###: …`.

## Validation gates per milestone

- G5 (M0): `uv run python scripts/check.py` green locally and in CI; Streamlit skeleton test.
- G6.1 (M1): full suite; parser coverage test over 97 filings; golden retrieval test.
- G6.2 (M2): full suite; offline briefing for all 20 tickers verified_share = 1.0; injection test; never-log test; security reviews CLEAR for T-004..T-007.
- G6.3 (M3): full suite; bench in gate; card rendered; screenshots captured; docs complete.
- G7: assurance report (bench figures, live probe result if a key is available, resilience: provider down → offline path).
- G8: ORR, change record, evidence export, slide, demo checklist.

## Budget summary

| Tier | Tasks | Planned in-tokens |
|---|---|---|
| T2 Implementer | 13 packs | 840 000 |
| T2 Verifier (~40 %) | 13 | 336 000 |
| T2 Security (medium × 5, ~25 %) | 5 | 100 000 |
| T3 (this session) | design, orchestration, gates, slide | not metered |

## Risks to the plan

| Risk | Mitigation |
|---|---|
| `normal` packs overrun 2× (Lodestar actuals) | only single-module packs are `normal`; everything multi-file is `high` |
| Parser edge cases eat T-002's budget | pack lists the frozen algorithm and the coverage test; unusual filings are recorded, not chased; fallback to first-N-characters context exists in T-006 |
| Streamlit `AppTest` fragility on Windows | T-000 proves the harness early with a one-widget page |
| Live gateway untestable before interview | T-004 tests the exact request shape with `MockTransport`; `fathom probe` exists for the day |
| Time: interview is today | M3 tasks T-011/T-012 are cut first if needed; slide and demo checklist are Orchestrator work and not on the agent critical path |
