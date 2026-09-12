---
id: T-016
title: Demo polish — offline sentence heuristics, quote-card formatting
milestone: M3
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-008, T-013]
rtm: [FR-002, FR-006, FR-012, FR-015]
status: done
---
# T-016 — Demo polish: offline sentence heuristics, quote-card formatting

## Goal
Deliver D-011 so the offline demo reads like a briefing and the quote card shows whole numbers.

## Spec references
`03-lld.md §6.3` (D-011, verbatim): (a) if a sentence contains a newline, only the text after its
last newline is kept, and it must still qualify; (b) sentences containing, case-insensitively,
"forward-looking", "Private Securities Litigation Reform Act", "this Item and other sections",
"safe harbor" or "should be read in conjunction" are skipped; (c) a sentence already used as a
claim anywhere in the briefing is not reused in a later section (talking points excepted);
(d) sentences are trimmed of leading "Item N." / "Item NA." prefixes.
`decisions.md D-011` (page): market cap as "$4.85 T" / "$412 B" / "$95 M" (two decimals for T,
integers for B and M); the 52-week range as two metrics "52-wk low" / "52-wk high"; P/E and
dividend yield as before; one caption under the metric row: "Prices: <bars source> as of <date> ·
Snapshot: <quote source> as of <datetime UTC>"; individual metric captions removed. All values
must render untruncated at a 1440-px viewport (six metrics in one row).

## Scope (files this task may touch)
- fathom/providers.py (OfflineProvider sentence selection only), tests/test_providers.py
- app/main.py, app/components/rendering.py (metric formatting), tests/test_app.py
- metrics/headline.json, metrics/card.json, metrics/card.md (regenerate: `uv run python -m fathom.bench && uv run python metrics/render.py`)

## Acceptance criteria
- AC1: On a synthetic 10-K:1 excerpt beginning "Business\nCompany Background\nThe Company designs, manufactures and markets smartphones and related services worldwide.", the first business_snapshot claim text is "The Company designs, manufactures and markets smartphones and related services worldwide." (and equals its quote).
- AC2: On a synthetic 10-Q:I.2 excerpt whose first three sentences are forward-looking boilerplate and whose fourth is "Net sales increased 5% year over year driven by services growth in all segments.", latest_results starts with that fourth sentence.
- AC3: With identical legal-proceedings sentences in `10-K:3` and the newest `10-Q:II.1`, notable_disclosures contains that sentence once.
- AC4: A sentence "Item 1A. Risk Factors The following summarizes factors that could affect the Company." yields claim text without the "Item 1A." prefix; every claim's `quote` remains a verbatim substring of its excerpt (verification still passes).
- AC5: Offline `brief()` over all 20 tickers keeps `verified_share == 1.0` and `claims_total >= 10`; bench regenerated; drift checks green.
- AC6: `format_market_cap(4_849_208_188_600) == "$4.85 T"`, `format_market_cap(412_000_000_000) == "$412 B"`, `None → "—"`; the AppTest page shows six metrics whose displayed values contain no "…"; the source caption line is present once.
- AC7: Full gate green; tests named `test_fr002_*`, `test_fr006_*`, `test_fr012_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_providers.py tests/test_app.py -q`
- `uv run python -m fathom.bench && uv run python metrics/render.py && uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] quotes remain verbatim substrings (verified share 1.0)
- [ ] no computation added to app/ beyond formatting helpers
- [ ] metrics regenerated; drift green
- [ ] tests named with RTM IDs; no new dependencies

## Threat-model boundary touched
none

## Handoff (Implementer fills, ≤10 lines)
Implemented D-011 (a)-(d) in `fathom/providers.py` offline section: `_trim_newline_tail`,
`_trim_item_prefix`, `_is_boilerplate`, and a `used: set[str]` threaded through
`_claims_from`/`_liquidity_claims` in section order (business→results→risks→liquidity→notable);
talking points exempt. Added `format_market_cap` + one shared source caption in
`app/components/rendering.py`; six `st.metric` in one row (removed per-metric captions).
Updated `tests/test_providers.py` (5 new/changed `test_fr006_*`, incl. liquidity dedup) and
`tests/test_app.py` (metric count→6, caption checks, new `test_fr002_*`). Metrics regenerated:
claims_total 378→374 (verified_share stays 1.0). Full gate green except `bench drift`
(git diff on metrics/headline.json vs last commit — expected since I never commit; card
drift is clean). No Portkey/Anthropic/error-helper code touched.
