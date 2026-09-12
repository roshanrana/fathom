# Decisions (append-only ADR log)

## D-000 — Standing autonomous authorisation for gates G0–G4, G7, G8   (2026-09-12, phase 0, status: accepted)
Context: The owner asked for the prototype to be built end to end with the Shipyard skill in an
autonomous session; the owner is the sole human approver and is not available per gate.
Options: (a) park at every gate for a typed "approved"; (b) treat the owner's build instruction
as a standing authorisation, present every gate in the standard block in the session record,
and log the approval text as "approved — standing autonomous authorisation (owner instruction
2026-09-12)"; (c) skip gates.
Decision: (b). Every gate is still presented and ledgered; the owner can reopen any gate after
the fact and the ledger shows exactly what was approved on their behalf. Same precedent as the
Lodestar build (2026-09-09).
Consequences: Rule 1's literal "approved" comes from the standing instruction rather than a
per-gate reply; recorded as a deviation in STATE.md.
Approver: Delivery lead / owner (Roshan Rana).

## D-001 — Name: Fathom   (2026-09-12, phase 0, status: accepted)
Context: The repo needs a name in the owner's nautical family (Lodestar, DRYDOCK, Harbormaster).
Options: Fathom, Soundings, Leadline, Bearings (all free on github.com/roshanrana).
Decision: Fathom — "get to the bottom of a stock"; short, a verb and a noun, reads well in a
pitch. Rename is a one-script change if the owner prefers another.
Consequences: package `fathom`, CLI `fathom`, repo `roshanrana/fathom`.
Approver: Delivery lead (standing authorisation, D-000).

## D-002 — Demo data from Hugging Face, committed as fixtures   (2026-09-12, phase 0, status: accepted)
Context: The challenge supplies no data. The owner asked for Hugging Face datasets.
Options considered (all inspected on the Hub on 2026-09-12):
- Filings: `musk1209/finsight-sec-filings` (97 cleaned 10-K/10-Q texts, 20 large caps, filed
  2025-04-23 to 2026-05-29, MIT) — chosen. Alternatives: `eloukas/edgar-corpus` (10-K only,
  1993–2020, script-loaded), `JanosAudran/financial-reports-sec` (sentence-split 10-K, to 2020),
  `winterForestStump/10-K_sec_filings` (to 2023, 100–500 MB shards, noisy).
- Prices: `AlphaDojo/dojo_stock_kline` (daily bars, all 20 tickers, 2025-01-02 to 2026-09-11,
  Apache-2.0) + `AlphaDojo/dojo_quote` (latest-session snapshots with market cap, P/E, P/B,
  dividend yield) + `AlphaDojo/dojo_stock_info` (company master) — chosen. Alternatives:
  `no-ry/world-stock-prices-daily-updating` (11 of 20 tickers, ends 2025-07),
  `jwigginton/timeseries-daily-sp500` (ends 2024), `paperswithbacktest/Stocks-Daily-Price`
  (gated, subscription).
Decision: `scripts/fetch_data.py` downloads the four parquet files, filters to the 20 tickers,
and writes `data/*.parquet` (≈ 12 MB total, committed) plus `data/SOURCES.md` with dataset ids,
licences, row counts and retrieval date. CI and the demo read the fixtures only.
Consequences: deterministic, offline demo; "current quote" means the latest committed bar and is
stamped as-of; refreshing data is one command.
Approver: Delivery lead (standing authorisation, D-000).

## D-003 — Grounding by verbatim citation, not by trust   (2026-09-12, phase 0, status: accepted)
Context: A wealth-management briefing that misquotes a filing is worse than no briefing.
Options: (a) free-text summary; (b) summary with section references; (c) structured output where
every claim carries a short verbatim quote and the section id, and the application verifies the
quote exists in that section before showing it as verified.
Decision: (c). Unverified claims are shown, flagged, and counted; the eval suite reports the
verified share as a headline metric.
Consequences: the prompt contract is a JSON schema (frozen in the LLD); the offline provider
produces the same schema extractively so every surface and test runs without a key.
Approver: Delivery lead (standing authorisation, D-000).

## D-004 — Lexical BM25 over SEC items and chunks, no vector store   (2026-09-12, phase 2, status: accepted)
Context: Retrieval must be explainable to a compliance reviewer, deterministic in CI, and free of
model downloads; each ticker has five or six filings already structured into SEC items.
Options: (a) embeddings + FAISS/Chroma; (b) `rank_bm25` dependency; (c) in-package BM25 (~60
lines) over item-level sections and 1 200-character chunks.
Decision: (c). `retrieval.search` is the single interface; a hybrid or embedding ranker can
replace it later without touching callers (HLD §risks).
Consequences: no new dependency; retrieval quality measured by the golden-query hit-rate in
bench; documented upgrade path for large universes.
Approver: Delivery lead (standing authorisation, D-000).

## D-005 — Providers speak one JSON contract; the offline provider is a real provider   (2026-09-12, phase 2, status: accepted)
Context: The demo must not depend on a key; CI must run the whole pipeline; live mode must be a
one-variable switch.
Options: (a) branch in `briefing.py` between "extractive" and "LLM" paths; (b) every provider
implements `complete_json(system, user, max_tokens)` where `user` is a JSON document containing
the task and the capped sections, so the offline provider composes the same output contract
extractively from that document.
Decision: (b). Portkey is called as OpenAI-compatible chat completions at
`<PORTKEY_BASE_URL>/chat/completions` with header `x-portkey-api-key` and the catalogue model
id (`max_tokens` mandatory); Anthropic via the Messages API. Both return the JSON text that
`briefing.py` validates against the frozen schema.
Consequences: one code path from prompt to verified claims; the offline output is verified by
construction (quotes are the sentences themselves), which makes NFR-007's offline gate honest
but not a measure of live quality — live verified share is reported from the audit log.
Approver: Delivery lead (standing authorisation, D-000).
