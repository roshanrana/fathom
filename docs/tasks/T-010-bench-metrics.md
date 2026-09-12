---
id: T-010
title: Bench and metrics card
milestone: M3
risk: low
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-003, T-006, T-007]
rtm: [FR-015, NFR-001, NFR-004, NFR-007, NFR-008]
status: todo
---
# T-010 — Bench and metrics card

## Goal
`fathom.bench.run_bench()` produces `metrics/headline.json` in the frozen shape; `metrics/
render.py` renders `metrics/card.json` + `metrics/card.md` and `--check` fails on drift; both
run in `scripts/check.py`.

## Spec references
`03-lld.md §5` (verbatim shape):
```json
{"schema": "fathom-headline/1", "generated_at": "<iso>", "universe": 20, "filings": 97,
 "parser": {"tenk_with_1a_and_7": 20, "tenk_total": 20, "tenq_with_i2": 77, "tenq_total": 77, "coverage": 1.0},
 "retrieval": {"golden_queries": 7, "hits": 140, "total": 140, "hit_rate": 1.0},
 "guard": {"adversarial": 30, "escapes": 0, "benign": 12, "false_positives": 0},
 "briefing_offline": {"tickers": 20, "claims_total": 400, "claims_verified": 400, "verified_share": 1.0, "latency_ms_median": 800},
 "injection": {"passed": true},
 "timing_ms": 12345}
```
The three timing-dependent fields (`generated_at`, `briefing_offline.latency_ms_median`,
`timing_ms`) are written to `metrics/timing.json` (gitignored); `metrics/headline.json` holds
everything else and must be byte-deterministic; `render.py` reads both and `--check` compares
the deterministic payload against `metrics/card.json`.
`metrics/card.json`: `{"title", "generated_at", "kpis": [{"key","label","value","unit","target","status"}]}`;
`metrics/card.md` is its markdown table. KPIs: parser coverage (target 1.0), retrieval hit-rate
(≥ 0.9), guard escapes (0), guard false positives (informational), offline verified share
(≥ 0.9), offline latency median ms (≤ 5000), injection passed (true). `status` ∈ {"pass",
"warn", "info"}. Golden queries (`GOLDEN_QUERIES`, 7 entries, expected section ids):
("risk factors", {10-K:1A, 10-Q:II.1A}), ("results of operations revenue", {10-K:7, 10-Q:I.2}),
("legal proceedings", {10-K:3, 10-Q:II.1}), ("cybersecurity", {10-K:1C}), ("liquidity and capital
resources", {10-K:7, 10-Q:I.2}), ("market risk interest rate", {10-K:7A, 10-Q:I.3}), ("controls
and procedures", {10-K:9A, 10-Q:I.4}); a hit = top-1 chunk's section_id in the expected set;
total = 7 × 20. Adversarial and benign phrase lists: reuse the T-005 test lists by defining
`ADVERSARIAL_PHRASES` (≥ 25) and `BENIGN_PHRASES` (≥ 12) in `bench.py` (tests may import them).
Injection check: run the FR-018 scenario from T-006 with a scripted provider inside bench.
Gate wiring: append to `scripts/check.py` STEPS in this order: ("bench", ["fathom", "bench"]),
("bench drift", ["git", "diff", "--exit-code", "--", "metrics/headline.json"]), ("card drift",
[sys.executable, "metrics/render.py", "--check"]).

## Scope (files this task may touch)
- fathom/bench.py
- metrics/render.py, metrics/headline.json, metrics/card.json, metrics/card.md
- scripts/check.py (STEPS additions only), .gitignore (add metrics/timing.json)
- tests/test_bench.py

## Acceptance criteria
- AC1: `uv run fathom bench` writes `metrics/headline.json` matching the shape (the three timing fields go to `metrics/timing.json`) with `parser.coverage == 1.0`, `retrieval.hit_rate >= 0.9`, `guard.escapes == 0`, `briefing_offline.verified_share == 1.0`, `injection.passed is True`; running it twice yields byte-identical `headline.json`.
- AC2: `python metrics/render.py` writes `card.json` and `card.md`; `--check` exits 0 when they match the headline and 1 after a KPI value is edited.
- AC3: `scripts/check.py` includes the three new steps in order after the secrets scan and passes end to end.
- AC4: `run_bench` completes in under 120 s on the dev laptop (test asserts timing under 180 s to be safe) and uses only the offline provider.
- AC5: Tests validate the headline shape with a pydantic model defined in the test, check determinism of the non-timing payload, and check the KPI statuses; tests named `test_fr015_*`, `test_nfr001_*`, `test_nfr004_*`, `test_nfr007_*`, `test_nfr008_*`.
- AC6: mypy strict clean for `fathom/bench.py`; `metrics/render.py` is stdlib-only and excluded from ruff/mypy like Lodestar (`extend-exclude`).

## Validation commands (targeted)
- `uv run pytest tests/test_bench.py -q`
- `uv run fathom bench && uv run python metrics/render.py --check && git diff --exit-code -- metrics/headline.json`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] determinism proven (two runs identical)
- [ ] gate steps added in the specified order
- [ ] tests named with RTM IDs
- [ ] no new dependencies
- [ ] timing fields isolated in metrics/timing.json (gitignored)

## Threat-model boundary touched
none (offline only)

## Handoff (Implementer fills, ≤10 lines)
