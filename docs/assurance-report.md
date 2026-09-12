# Assurance report — Fathom, 2026-09-12

Rungs follow `controls-evidence.md §5`. "Evidence" cites the ledger sequence or the file.

| Rung | Target | Actual | Evidence | Status |
|---|---|---|---|---|
| 1 Unit / integration / contract tests, coverage ≥ 80 % | gate green | gate green on every task commit and in CI; final count recorded in `metrics/card.md` and README (refreshed by T-011 after the last code task) | ledger task entries; CI runs on `main` | pass |
| 2 End-to-end for every critical flow | briefing, ask, offline, bench, fetch | briefing/ask exercised end to end offline by tests (all 20 tickers), CLI (`CliRunner`), API (`TestClient`), Streamlit (`AppTest`), MCP (in-process session); fetch run once at foundation | T-006/T-007/T-008/T-009/T-012 verdicts; seq 6 | pass |
| 3 SAST / secrets / dependency and licence audit | zero blocking | ruff (E,F,I,B,UP,N,W) + mypy strict in the gate; regex secrets scan in the gate; dependencies pinned in `uv.lock`; licences: MIT / Apache-2.0 data, permissive Python packages; no SBOM tooling (accepted, threat model open item 2) | gate; `data/SOURCES.md` | pass with accepted gap |
| 4 DAST | n/a (no hosted deployment) | not run; API binds loopback by default (D-008) | T-013 security | not applicable |
| 5 Performance vs NFR budgets | NFR-001 ≤ 5 s offline; NFR-010 ≤ 40 k input tokens | offline briefing median ≈ 33 ms end-to-end (bench, `metrics/timing.json`); prompt size bounded by section caps ≈ 106 k chars ≈ 27 k tokens; live latency (NFR-002) not measured — no key before the interview; reported from the audit log on the day | bench; LLD §6.2 | pass / NFR-002 deferred |
| 6 Resilience | dependency failure, restart, backpressure | gateway unreachable → raw `httpx.ConnectError` escaped (finding → D-010 → T-015: now `PROVIDER_HTTP reason=ConnectError`); missing key → `PROVIDER_CONFIG` before any client; offline fallback works with no network; single user, no backpressure path | G7 run log in STATE task log; T-015 verdict | pass after T-015 |
| 7 Backup / restore / DR | rebuild from git + fetch script | fixtures deterministic from four named datasets; rebuilt once; no runtime state | seq 6 | pass |
| 8 Data-handling review | never-log list honoured | audit records carry hashes, counts, model, latency only; bodies opt-in; question text never stored; tests with capturing log handler; G7 manual run of brief/ask confirmed no key or body in the audit file | T-005/T-006/T-007 verdicts; G7 run | pass |
| 9 Access review | least privilege | no authn in the prototype (documented C-08 gap); API loopback; agents had no production access | threat model B1 | accepted gap |
| 10 AI components: eval suite, injection, guardrails | in gate; 0 escapes; verified share ≥ 0.9 offline | bench: parser coverage 1.0, guard escapes 0, offline verified share 1.0, injection test pass, retrieval hit-rate 0.7786 (informational, D-008) | `metrics/card.md`; T-010/T-013 verdicts | pass (hit-rate below aspiration, disclosed) |
| 11 Penetration test hook | n/a | not in scope for a prototype | — | not applicable |

## NFR budget results

| NFR | Budget | Result |
|---|---|---|
| NFR-001 offline latency | ≤ 5 s | ≈ 33 ms median (snapshot) |
| NFR-002 live latency | ≤ 90 s (reported) | deferred to the interview (no key); `fathom probe` measures |
| NFR-003 single gate | one command, CI parity | `scripts/check.py`; CI green on every push |
| NFR-004 determinism | byte-identical headline | verified by bench-drift step and Verifiers (two runs) |
| NFR-005 secrets | none in repo | secrets scan in gate; 0 hits |
| NFR-006 never-log | no bodies/keys/questions | tests + G7 manual review |
| NFR-007 verified share | ≥ 0.90 offline | 1.0 (by construction; D-005) |
| NFR-008 guard escapes | 0 | 0 on 30 adversarial phrases; 0 false positives on 12 benign |
| NFR-009 fixture size | ≤ 20 MB | 11.8 MB |
| NFR-010 prompt cost | ≤ 40 k tokens | ≈ 27 k (character caps) |
| NFR-011 accessibility | text badges + labels | badges "✅ verified / ⚠️ unverified / ⛔ removed"; every metric labelled and stamped |

## Findings converted to tasks

T-013 (D-006 parser fallback, D-008 retrieval boost / API bind / latency KPI; attempt 2 after
D-009), T-014 (D-007 unbounded claim text — HIGH), T-015 (D-010 transport errors), T-016
(D-011 demo polish).

## Residual risks and acceptances (owner)

- Offline verified share is by construction; live share is measured, not asserted (D-005).
- Retrieval hit-rate 0.78 on the golden set (informational KPI; embedding upgrade path D-004).
- No authn, no SBOM, no tamper-evident audit sink (hosting backlog, ORR).
- Parser fallback polish for MCD Items 9A/1 (T-013 v2 non-blocking findings).
- Guard scans claim text, not quotes; quotes are not rendered (T-005/T-007 LOW).
