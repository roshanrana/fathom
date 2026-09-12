# STATE — Fathom
Phase: 5   Milestone: M0   Wave: W1   Updated: 2026-09-12T10:55:00Z

**Gate command:** `uv run python scripts/check.py` (exists from T-000 onward).
**Routing:** T3 (this session) designs and orchestrates only; all implementation, verification
and security review at T2 Sonnet, effort high (owner instruction, memory: model-tiering-for-delegation).
**Target:** Perficient AI Prototype Challenge, scenario 2 (Finance). Deliverables: working
prototype, one pitch slide, live-demo readiness. Due 2026-09-12.

## Now / next
- G0–G4 passed (ledger seq 1–5). Foundation data committed (seq 6): `scripts/fetch_data.py`, `data/*.parquet`, `data/SOURCES.md` with anchors.
- In progress: W1 — T-000 (Implementer, attempt 1, T2 Sonnet)
- Next unblocked after T-000: W2 = T-001, T-002, T-004; then graphify scaffold (Orchestrator, T0)

## Blocked
| Task | Since | Reason | Needs |
|---|---|---|---|

## Deviations from plan
| Date | Task | Deviation | Recorded in |
|---|---|---|---|
| 2026-09-12 | gates | Gates G0–G4, G7, G8 approved under the owner's standing autonomous authorisation rather than per-gate replies | decisions.md D-000 |

## Task log
<!-- one line per event: ts task outcome attempt tier in≈tokens calls commit -->

## Budget ledger
| Task | Tier | Planned in-tok | Actual | Calls | Attempts | Outcome |
|---|---|---|---|---|---|---|

## Gate log
| Gate | Date | Approver | Evidence seq |
|---|---|---|---|
| G0 | 2026-09-12 | delivery_lead (D-000) | 1 |
| G1 | 2026-09-12 | delivery_lead (D-000) | 2 |
| G2 | 2026-09-12 | architecture_review (D-000) | 3 |
| G3 | 2026-09-12 | architecture_lead (D-000) | 4 |
| G4 | 2026-09-12 | delivery_lead (D-000) | 5 |

## Routing overrides
<!-- deviations from config/model-routing.yaml, with reason -->
- All Implementer / Verifier / Security roles pinned to T2 (Sonnet, effort high) regardless of risk class; T3 reserved for design and orchestration (owner cost instruction).
