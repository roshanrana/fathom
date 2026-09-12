---
id: T-008
title: Streamlit page
milestone: M3
risk: low
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: [T-001, T-006, T-007]
rtm: [FR-012, NFR-011]
status: done
---
# T-008 — Streamlit page

## Goal
Replace the T-000 skeleton with the full advisor page: ticker selector, company header, quote
card, one-year chart, filings table with EDGAR links, briefing by section with verified /
unverified badges and the disclaimer, a question box with cited answers, and a status strip.
The page computes nothing itself; it calls `fathom.*`.

## Spec references
`01-requirements.md` FR-012 (verbatim): One page: ticker selector (universe), company header,
quote card with as-of stamps, one-year close chart, filings table with EDGAR links, briefing
rendered by section with verified/unverified badges and the disclaimer, a question box with the
answer and citations, a status strip showing provider, model and the last audit record summary.
Renders without exception under `streamlit.testing` in offline mode. NFR-011: every metric has
a text label and an as-of stamp; colour is never the only carrier of verified state (badge
text). Public surface used: `data.company`, `quotes.quote_card`, `filings.filings_for`,
`briefing.brief`, `ask.ask`, `config.Settings.from_env()`, `Briefing`/`Answer` fields (LLD §3),
`QuoteCard` fields (LLD §2.4). Layout: sidebar = ticker selectbox, provider/model caption, a
"Generate briefing" button and a "Ask" text input + button; main = header (name, exchange,
sector · industry, website link), `st.metric` row (last close with change, 52-week range, market
cap, P/E, dividend yield) each with a caption "as of <date> · <source>", plotly line chart of
`series`, `st.dataframe` of filings (form, filing date, period end, accession, EDGAR link), then
the briefing sections in the LLD order with each claim as a bullet followed by a badge string
"✅ verified" / "⚠️ unverified" / "⛔ removed" and a `st.caption` "Source: <form> <filing_date> ·
<section title> · <accession>", then the disclaimer, then the answer block. Cache the briefing
and answers in `st.session_state` keyed by ticker. Errors (`FathomError`) render as
`st.error(f"{code}: {message}")`; nothing else is caught.

## Scope (files this task may touch)
- app/main.py
- app/components/__init__.py, app/components/*.py (optional helpers; pure rendering)
- tests/test_app.py (replaces tests/test_app_skeleton.py — delete the skeleton test file)

## Acceptance criteria
- AC1: `AppTest.from_file("app/main.py", default_timeout=120).run()` in offline mode has no exception; the page contains a selectbox, at least five `st.metric` elements, one plotly chart, one dataframe, and the disclaimer text.
- AC2: Clicking "Generate briefing" (via `at.button[...]`/`at.sidebar.button`) renders the six section headers in the LLD order and at least ten badge strings; every rendered badge is one of the three strings; the caption for each claim includes the accession.
- AC3: Entering "What are the main risk factors?" and clicking Ask renders at least one claim with a "✅ verified" badge; entering "Should I buy?" renders the guard notice text.
- AC4: Selecting a different ticker re-renders the header with that company's name; switching back reuses the cached briefing (the provider is not called again — assert via a call counter monkeypatched on `fathom.briefing.make_provider`).
- AC5: The status strip shows provider "offline" and model "extractive-v1" and, after a briefing, "claims N · verified M".
- AC6: No computation in `app/`: a test greps `app/` for `read_parquet`, `BM25`, `re.compile` and asserts none; mypy is not required for `app/` but ruff is; tests named `test_fr012_*`, `test_nfr011_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_app.py -q`
- `uv run ruff check app tests/test_app.py && uv run ruff format --check app`

## Verification checklist (for the Verifier)
- [ ] scope respected (no changes under fathom/)
- [ ] only FathomError is caught
- [ ] disclaimer present; badge text carries state
- [ ] tests named with RTM IDs
- [ ] no new dependencies

## Threat-model boundary touched
B1 (user input passes straight to `ask`; page never renders raw model text as HTML — use `st.markdown` with `unsafe_allow_html=False`).

## Handoff (Implementer fills, ≤10 lines)
Delivered: app/main.py (rewritten), app/components/{__init__,badges,rendering}.py,
tests/test_app.py (replaces deleted tests/test_app_skeleton.py). Page only calls
fathom.data/quotes/filings/briefing/ask + config.Settings; only FathomError caught;
badges are plain text (✅/⚠️/⛔); st.markdown never unsafe_allow_html.
Targeted: `pytest tests/test_app.py -q` → 8 passed; `ruff check app tests/test_app.py` +
`ruff format --check app` → clean.
Full gate FAILS, but only outside my scope: ruff E501 in fathom/api.py (lines 69/71), and
test_config.py's test_nfr003_pyproject_declares_lld_dependency_set (pyproject.toml gained a
`[project.scripts] fathom = "fathom.cli:app"` entry from concurrent T-006/T-007 work). No
edits made under fathom/ or pyproject.toml. Untargeted `pytest -q`: 171 passed, 1 failed (same).
