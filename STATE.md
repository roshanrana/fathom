# STATE — Fathom
Phase: 6   Milestone: M2   Wave: W4   Updated: 2026-09-12T14:30:00Z

**Gate command:** `uv run python scripts/check.py` (exists from T-000 onward).
**Routing:** T3 (this session) designs and orchestrates only; all implementation, verification
and security review at T2 Sonnet, effort high (owner instruction, memory: model-tiering-for-delegation).
**Target:** Perficient AI Prototype Challenge, scenario 2 (Finance). Deliverables: working
prototype, one pitch slide, live-demo readiness. Due 2026-09-12.

## Now / next
- G0–G5 passed (ledger seq 1–5, G5 after seq 11). Foundation: fixtures (seq 6), graphify scaffold committed, private repo `roshanrana/fathom` created and CI green.
- Done: T-000 (PASS attempt 2), T-001, T-002, T-003, T-004 (security CLEAR) — M0 and M1 complete except the G6.1 milestone entry (recorded with G6.2).
- In progress: T-005 (verify + security review), T-006 and T-007 (Implementers, attempt 1)
- Next: W5 = T-008, T-009, T-010; W6 = T-011, T-012; then G7 assurance, slide, G8.
- Accepted candidates (backlog): providers 2xx JSON shape validation (T-004 security F1, MEDIUM); Anthropic temperature pin (LOW).

## Blocked
| Task | Since | Reason | Needs |
|---|---|---|---|

## Deviations from plan
| Date | Task | Deviation | Recorded in |
|---|---|---|---|
| 2026-09-12 | gates | Gates G0–G4, G7, G8 approved under the owner's standing autonomous authorisation rather than per-gate replies | decisions.md D-000 |

## Task log
<!-- one line per event: ts task outcome attempt tier in≈tokens calls commit -->
2026-09-12T11:20Z T-000 HANDOFF v1 T2 in≈45k calls 30 commit 619bb72 (verifier in worktree)
2026-09-12T11:45Z T-000 verdict FAIL v1 (F2: optional deps declared as dependency-groups; uv sync --all-extras skipped them)
2026-09-12T11:50Z T-001 HANDOFF v1 T2 in≈55k calls 14 commit 20ff9b3
2026-09-12T12:00Z T-000 HANDOFF v2 T2 in≈20k calls 14 commit bad1059
2026-09-12T12:05Z T-002 HANDOFF v1 T2 in≈34k calls 30 commit adeddc1 (AC4 allowlist empty: 97/97)
2026-09-12T12:10Z T-001 PASS v1; evidence seq 7
2026-09-12T12:20Z T-004 HANDOFF v1 T2 in≈45k calls 35 commit 03df347
2026-09-12T12:30Z T-000 PASS v2; evidence seq 8. T-002 PASS v1; evidence seq 9
2026-09-12T12:40Z repo roshanrana/fathom created (private), CI check.yml green run 34698327450; graphify scaffold 567 nodes / 897 edges
2026-09-12T12:50Z T-004 PASS v1, security CLEAR (1 MEDIUM accepted candidate); evidence seq 10
2026-09-12T12:55Z T-003 HANDOFF v1 T2 in≈30k calls 30 commit 3f08cdb
2026-09-12T13:05Z T-003 PASS v1; evidence seq 11
2026-09-12T13:10Z T-005 HANDOFF v1 T2 in≈45k calls 35 commit f7420e9 (verifier + security dispatched)
2026-09-12T13:12Z W4 dispatched: T-006, T-007 (before T-005 verdict; accepted risk, gate green at handoff)

## Budget ledger
| Task | Tier | Planned in-tok | Actual | Calls | Attempts | Outcome |
|---|---|---|---|---|---|---|
| T-000 | T2 | 80000 | ~65000 (0.81×, two attempts) | 44 | 2 | PASS |
| T-001 | T2 | 40000 | ~55000 (1.38×) | 14 | 1 | PASS |
| T-002 | T2 | 80000 | ~34000 (0.43×) | 30 | 1 | PASS |
| T-003 | T2 | 40000 | ~30000 (0.75×) | 30 | 1 | PASS |
| T-004 | T2 | 80000 | ~45000 (0.56×) | 35 | 1 | PASS |
| T-005 | T2 | 80000 | ~45000 (0.56×) | 35 | 1 | verify |

## Gate log
| Gate | Date | Approver | Evidence seq |
|---|---|---|---|
| G0 | 2026-09-12 | delivery_lead (D-000) | 1 |
| G1 | 2026-09-12 | delivery_lead (D-000) | 2 |
| G2 | 2026-09-12 | architecture_review (D-000) | 3 |
| G3 | 2026-09-12 | architecture_lead (D-000) | 4 |
| G4 | 2026-09-12 | delivery_lead (D-000) | 5 |
| G5 | 2026-09-12 | ci (run 34698327450) | 12 |

## Routing overrides
<!-- deviations from config/model-routing.yaml, with reason -->
- All Implementer / Verifier / Security roles pinned to T2 (Sonnet, effort high) regardless of risk class; T3 reserved for design and orchestration (owner cost instruction).
