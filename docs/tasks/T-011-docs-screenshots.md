---
id: T-011
title: Documentation and screenshots
milestone: M3
risk: low
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-008, T-009, T-010]
rtm: [FR-017]
status: done
---
# T-011 — Documentation and screenshots

## Goal
README, `docs/OVERVIEW.md`, `docs/SHOWCASE.md` (with screenshots), `docs/ASSUMPTIONS.md`,
`docs/mcp.md` placeholder if T-012 is not yet merged (omit otherwise), all matching the code as
built. The pitch slide is NOT in scope (Orchestrator produces it).

## Spec references
`01-requirements.md` FR-017 (verbatim): README (run in three commands, provider switch, how
citations are verified), `docs/OVERVIEW.md`, `docs/SHOWCASE.md` with screenshots,
`docs/ASSUMPTIONS.md`, the one-slide pitch in `docs/pitch/` (Orchestrator). Owner conventions
(Lodestar precedent): OVERVIEW = what it is, architecture (one diagram in text), how grounding
works, data sources with licences (copy from `data/SOURCES.md`), limits; SHOWCASE = a walk-through
with screenshots (`docs/assets/*.png`) of the page: header + quote card, chart + filings,
briefing with badges, Q&A with citations, the CLI JSON, the API envelope, and the metrics card
table (`metrics/card.md` embedded); ASSUMPTIONS = the three assumptions from `01-requirements.md`
plus fixture as-of dates and the offline-vs-live grounding caveat (D-005). Screenshots:
`scripts/screenshots.py` using Playwright (optional dependency group `screenshots`), starting
`streamlit run app/main.py --server.port 8765 --server.headless true` as a subprocess, waiting
for the port, growing the viewport to the `stMain` container height before each full-page
capture (Lodestar lesson), clicking "Generate briefing" and asking one question before the
briefing/Q&A captures; PNGs ≤ 600 KB each (scale 1). README sections: what, why it is
trustworthy (verified citations, advice guard, audit log), run (three commands), live mode
(`FATHOM_LLM_PROVIDER=portkey PORTKEY_API_KEY=…`, `fathom probe`), CLI/API/MCP one-liners,
metrics card (embed `metrics/card.md`), data sources + licences, design docs index, limits.

## Scope (files this task may touch)
- README.md, docs/OVERVIEW.md, docs/SHOWCASE.md, docs/ASSUMPTIONS.md
- docs/assets/*.png, scripts/screenshots.py
- pyproject.toml (only if the `screenshots` optional group is missing)

## Acceptance criteria
- AC1: Every command in README runs as written (the Verifier executes `uv sync --all-extras`, `uv run python scripts/check.py`, `uv run fathom brief AAPL`).
- AC2: SHOWCASE embeds ≥ 5 PNGs that exist under `docs/assets/`, each ≤ 600 KB, and the metrics card table.
- AC3: Every figure quoted in the docs (test count, coverage, KPI values) matches `metrics/card.md` or the current gate output; no invented numbers.
- AC4: OVERVIEW's data-source table lists the four Hugging Face dataset ids with licences exactly as in `data/SOURCES.md`.
- AC5: `uv run python scripts/check.py` still passes; screenshots script is excluded from mypy/ruff strictness like Lodestar or passes them.

## Validation commands (targeted)
- `uv run --group screenshots python scripts/screenshots.py`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] no invented figures
- [ ] commands run as written
- [ ] screenshots present and sized
- [ ] no new runtime dependencies

## Threat-model boundary touched
none

## Handoff (Implementer fills, ≤10 lines)

Wrote README.md, docs/OVERVIEW.md, docs/SHOWCASE.md, docs/ASSUMPTIONS.md, scripts/screenshots.py
(rewritten: self-starts the streamlit subprocess, offline provider, temp audit path, grows the
viewport per capture, kills the subprocess in `finally`), and 5 PNGs in docs/assets/ (00-full-page
142 KB, 01-header-quote 45 KB, 02-chart-filings 76 KB, 03-briefing 468 KB, 04-ask 68 KB — all
≤600 KB). docs/mcp.md and pyproject.toml untouched (T-012 already merged; `screenshots` extra
already present). Commands run and quoted verbatim: `uv sync --all-extras`;
`uv run python scripts/check.py` (238 passed, 95.18% coverage, all checks passed — run twice,
identical each time); `uv run fathom brief AAPL` / `--json`; `uv run fathom quote AAPL`;
`uv run fathom filings AAPL`; `uv run fathom probe`; `uv run fathom --help`;
`uv run python scripts/screenshots.py`; `uv run ruff check/format --check scripts/screenshots.py`;
`uv run mypy scripts/screenshots.py` (all clean, script not added to the ruff/mypy exclude list);
a `fastapi.testclient.TestClient` call against `fathom.api.create_app()` for `/healthz` and
`POST /api/ask/AAPL` (embedded in SHOWCASE, noted as TestClient-captured, byte-identical to the
equivalent `curl`). Every figure quoted (test count, coverage, KPI table, AAPL quote/JSON values)
came from one of these runs or from `metrics/card.md` / `data/SOURCES.md` verbatim — none invented.
Not verified or approved by me; over to the Verifier.
Attempt 2: README.md metrics table latency 36ms->33ms; docs/SHOWCASE.md prose "238 passed, 95.18%" -> "241 passed, 95.22%" and metrics table latency 36ms->33ms; docs/OVERVIEW.md and docs/ASSUMPTIONS.md had no stale gate figures ; gate 241 passed/95.22% coverage
Attempt 3: regenerated all 5 PNGs (uv run python scripts/screenshots.py) for the six-metric quote card + single source caption and the T-016 offline-briefing wording change; updated docs/SHOWCASE.md prose "241 passed, 95.22%" -> "287 passed, 96.02%", quote-card description (five tiles/per-tile caption -> six tiles/shared caption), briefing status-strip counts "20 claims / 20 verified" -> "18 claims / 18 verified" (re-run `fathom brief AAPL --json`), the `head -c 1500` JSON excerpt (business_snapshot claim text lost its "Business\nCompany Background\n" prefix), the `/api/ask/AAPL` TestClient timestamps, and the screenshot-regeneration size line (138/40/76/415/68 KB); re-verified README.md's and docs/SHOWCASE.md's metrics tables are byte-identical to metrics/card.md; docs/OVERVIEW.md and docs/ASSUMPTIONS.md had no stale gate figures (only carry the KPI values already matching card.md); added README "What's inside" links to docs/assurance-report.md, docs/ops/{runbook,orr,change-record,demo-checklist}.md, docs/pitch/fathom-pitch.pptx (with fathom-pitch.png embedded), and docs/graph/README.md. gate 287/96.02% coverage
Attempt 4 (post-M4): docs/SHOWCASE.md §1 prose "287 passed, 96.02%" -> "440 passed (2 network tests skipped offline), 95.62%"; README.md metrics block already byte-identical to metrics/card.md (no edit needed); docs/OVERVIEW.md and docs/ASSUMPTIONS.md had no stale gate figures; gate 440/95.62%
