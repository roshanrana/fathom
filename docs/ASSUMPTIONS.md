# Assumptions

Every assumption Fathom's design and build rested on, with its owner and where it surfaces.
Source: `docs/design/01-requirements.md` §"Assumptions (owner to confirm)" plus the fixture
as-of dates (`data/SOURCES.md`) and the offline-vs-live grounding caveat (decision D-005).

## From the requirements

1. **The committed snapshot is an acceptable "current quote" for the demo.** Bars run to
   2026-09-11; every quote figure is stamped as-of that date rather than presented as live.
   Owner: Roshan Rana. Surfaces: the quote card's "as of" captions (UI, CLI, API), README
   "Limits", `docs/OVERVIEW.md` "Limits".
2. **The Portkey gateway is OpenAI-chat-compatible at `/chat/completions`, with the catalogue
   model name from the problem brief.** Confirmed from Portkey's own documentation on
   2026-09-12, but not yet exercised against the actual Perficient gateway instance — that
   confirmation happens on interview day, when the key is issued. Owner: Roshan Rana, due
   interview day. Surfaces: `fathom/providers.py` (`PortkeyProvider`), `fathom probe`, README
   "Live mode".
3. **Twenty tickers are enough to demonstrate the retrieval, parsing and grounding approach.**
   The interview panel is told explicitly that the universe is a fixture choice made to keep the
   demo fast and reviewable, not a limit of the architecture — `scripts/fetch_data.py` re-runs
   against a larger universe with no code change. Owner: Roshan Rana. Surfaces: `fathom/config.py`
   `UNIVERSE`, README "Limits", `docs/OVERVIEW.md` "Limits".

## Fixture as-of dates

- **Filings:** 97 filings (20 10-K, 77 10-Q), filed 2025-04-23 to 2026-05-29, from
  `musk1209/finsight-sec-filings` (MIT).
- **Daily bars:** 8,480 rows, 2025-01-02 to 2026-09-11, from `AlphaDojo/dojo_stock_kline`
  (Apache-2.0). The "current quote" and the one-year chart both stop here.
- **Quote snapshots:** one row per ticker, `quote_time` maxing at
  2026-09-11T16:00:01+00:00, from `AlphaDojo/dojo_quote` (Apache-2.0).
- **Company master:** names, exchange, sector, industry, website, from
  `AlphaDojo/dojo_stock_info` (Apache-2.0), retrieved and filtered 2026-09-12.

All four fixtures are rebuilt deterministically by `scripts/fetch_data.py`; see
`data/SOURCES.md` for full provenance and the hand-checkable anchor values used by tests.

## The offline-vs-live grounding caveat (D-005)

Every provider — offline, Portkey, Anthropic — implements the same `complete_json` contract and
must return text that parses into the same `Briefing`/`Answer` JSON schema. The offline provider
(the default, and the only one exercised by CI and the bench) builds that JSON *extractively*:
each claim's `quote` is literally a sentence copied from the cited filing section. That makes its
claims verify by construction — the gated `offline_verified_share` KPI on the metrics card
(currently 1.0) is real, but it measures that the pipeline's plumbing (parsing → claim → verify)
works end to end, **not** that a live model paraphrases faithfully. A live call can still
hallucinate, misquote or paraphrase a filing; `verify_claim`'s normalisation (whitespace, case,
quote-glyph differences only) is exact after normalisation, so a live claim that isn't a genuine
substring of the section is marked unverified and flagged, never hidden — but the *share* of live
claims that verify is reported per call in `audit/fathom-audit.jsonl`, not gated in the bench.
Anyone reading the metrics card should read "verified_share: 1.0" as "the offline path is sound
end to end," not as "citations are always this reliable" — that second claim is only true for the
offline provider, by construction, and is explicitly not asserted for live mode.

## Other assumptions made during the build

- **Golden-query retrieval hit rate target is informational, not gated** (decision D-008): BM25
  with title-token boosting measures 0.7786 against the frozen 0.9 target on this fixture set.
  The metrics card reports the measured value; no threshold was edited to make it pass. Owner:
  architecture lead (standing authorisation).
- **The section parser's heading-vocabulary fallback (decision D-006)** only activates when a
  canonical section's parsed body is under 400 characters (guards against a cross-reference-sheet
  filing, e.g. McDonald's FY2025 10-K, from losing its business/risk sections to a page-number
  stub) — it must leave every other filing's sections byte-identical, verified by a per-filing
  spot check at T-013.
- **The advice-guard pattern set is frozen and adversarially tested**, not exhaustive: 0 escapes
  on the ≥25-phrase adversarial set is gated (`guard_escapes`), but a sufficiently indirect
  paraphrase outside that set could still evade it — accepted as residual risk for a prototype,
  same posture as Lodestar's deny-list guard.
