---
id: T-021
title: Live mode — network smoke test, docs, demo checklist
milestone: M4
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-020]
rtm: [FR-020, NFR-012, NFR-013, FR-017]
status: todo
---
# T-021 — Live mode: network smoke test, docs, demo checklist

## Goal
An opt-in network smoke test proves the live path against real endpoints; the docs describe live
mode truthfully with figures from a real run.

## Spec references
`05-m4-live-data.md` §1 (FR-020, FR-024, FR-025, NFR-012, NFR-013), §5, §6. Smoke test
`tests/test_live_network.py`: skipped unless `FATHOM_NETWORK_TESTS=1` and `FATHOM_SEC_CONTACT` is
set; runs `materialize` for two tickers outside the fixture universe (e.g. `NFLX`, `COST`) with
`force=True` into a temp cache, asserts parser coverage (10-K `1A`+`7`, every 10-Q `I.2`), bars ≥
250 rows, snapshot market_cap present, and records elapsed seconds; then runs an offline `brief`
on the live cache and asserts `verified_share == 1.0`.

## Scope (files this task may touch)
- tests/test_live_network.py
- README.md (new "Live data (free, no keys)" section: env vars, `fathom fetch`, sources and their terms — SEC fair-access policy, Yahoo/Stooq unofficial endpoints), docs/OVERVIEW.md (data sources table gains the live row), docs/ASSUMPTIONS.md (live caveats: Yahoo/Stooq are unofficial and may change; XBRL-derived ratios differ from vendor figures; cache TTL), docs/SHOWCASE.md (a live-mode section with the real `fathom fetch NFLX` output pasted verbatim), docs/ops/runbook.md and docs/ops/demo-checklist.md (live-mode start and fallback), docs/design/02-threat-model.md (B6 row referencing the amendment)
- docs/assets/05-live-mode.png (optional, if the page can be captured in live mode with network)

## Acceptance criteria
- AC1: `FATHOM_NETWORK_TESTS=1 FATHOM_SEC_CONTACT=<your contact> uv run pytest tests/test_live_network.py -q` passes on this machine (record the elapsed cold-start seconds per ticker in the handoff and in docs as measured); without the variables the test is skipped and the gate stays offline.
- AC2: Every command in the new README section runs as written; every figure quoted in docs comes from a command you ran (list them in the handoff).
- AC3: README's metrics block is unchanged (bench is fixture-only); docs state plainly that live prices come from unofficial endpoints and that XBRL-derived valuation figures are approximations.
- AC4: Full gate green.

## Validation commands (targeted)
- `FATHOM_NETWORK_TESTS=1 FATHOM_SEC_CONTACT=<contact> uv run pytest tests/test_live_network.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] smoke test skips cleanly without env; passes with env (Verifier runs it once with network)
- [ ] no invented figures; sources' terms stated
- [ ] gate offline and green

## Threat-model boundary touched
none (docs) — B6 row added to the threat model.

## Handoff (Implementer fills, ≤10 lines)

Added `tests/test_live_network.py` (skips w/o env), README "Live data (free, no API keys)",
OVERVIEW/ASSUMPTIONS/SHOWCASE/runbook/demo-checklist live sections, threat-model B6 rows (4 rows,
`02-threat-model.md`). Commands run, output quoted in docs/here: `PYTHONIOENCODING=utf-8 uv run
pytest tests/test_live_network.py -q` (2 skipped, no env); `FATHOM_NETWORK_TESTS=1
FATHOM_SEC_CONTACT=<contact> uv run pytest tests/test_live_network.py -q -s` → 2
passed, **NFLX 2.58s, COST 2.38s** cold materialize; `FATHOM_DATA_SOURCE=live
FATHOM_SEC_CONTACT=... FATHOM_AUDIT_PATH=.cache/live/_audit.jsonl uv run fathom fetch NFLX
--force` → all 5 filings full canonical coverage, bars 2024-09-12..2026-09-11, snapshot 4/4
fields (pasted verbatim in SHOWCASE.md §9); `uv run fathom brief NFLX` (offline provider, live
cache) → all claims `[verified]`; `uv run python scripts/check.py` → 420 passed/2 skipped,
96%+ coverage, all checks passed. `scripts/screenshots.py` doesn't support switching to the live
sidebar radio without edits — skipped per pack note, stated in SHOWCASE.md §9. Contact email
used only via env var at runtime; grepped repo, confirmed not in any tracked file.
