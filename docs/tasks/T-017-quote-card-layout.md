---
id: T-017
title: Quote-card layout — two rows of three, percentage delta, untruncated at demo width
milestone: M3
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 15000, tool_calls: 10, wall_clock_min: 10}
depends_on: [T-016]
rtm: [FR-012, NFR-011]
status: todo
---
# T-017 — Quote-card layout

## Goal
At the screenshot viewport (1440 px wide, sidebar open) no metric value or delta is truncated.

## Spec references
`decisions.md D-011` page formatting, amended: the six metrics render as two rows of three
(`st.columns(3)` twice): row 1 = Last close (delta = percentage only, e.g. "+1.75%"), 52-wk low,
52-wk high; row 2 = Market cap ("$4.85 T" style from `format_market_cap`), P/E, Dividend yield.
The single source caption stays under row 2. FR-012 / NFR-011 unchanged.

## Scope (files this task may touch)
- app/main.py, app/components/rendering.py
- tests/test_app.py (metric layout assertions only)
- docs/assets/*.png (regenerate with `uv run python scripts/screenshots.py`)

## Acceptance criteria
- AC1: AppTest shows six metrics; the Last-close delta string matches `^[+-]\d+\.\d{2}%$`.
- AC2: `docs/assets/01-header-quote.png` regenerated; in the PNG no metric value shows an ellipsis (the Verifier inspects the image).
- AC3: Full gate green; test names `test_fr012_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_app.py -q`
- `uv run python scripts/screenshots.py && uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] no computation in app/
- [ ] PNGs ≤ 600 KB and untruncated

## Threat-model boundary touched
none

## Handoff (Implementer fills, ≤10 lines)
