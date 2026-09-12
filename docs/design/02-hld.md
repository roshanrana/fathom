# High-level design — Fathom

## Architecture style and rationale

A single Python package (`fathom`) holds every computation; three thin surfaces (Streamlit page,
Typer CLI, FastAPI app; MCP optional) call the same functions and never compute anything
themselves. The intelligence layer is retrieval-augmented generation with a **verifiable
contract**: the model returns structured claims, each carrying a verbatim quote and a section id,
and the application checks the quote against the source before displaying it. Providers are
swappable behind one protocol so the demo runs offline by default and switches to Portkey
(Claude Sonnet 4.5 on Bedrock) with one environment variable.

Why not a vector database: a ticker has five or six filings, each already structured into SEC
items. Item-level sections and fixed-size chunks ranked by BM25 give precise, explainable
retrieval with zero infrastructure. The design note in §"Risks" records the embedding upgrade
path for a larger universe.

## System context (C4 L1)

```
Advisor ──(browser)──► Streamlit page ─┐
Advisor ──(terminal)─► Typer CLI ──────┼──► fathom package ──► data/*.parquet (fixtures)
Automation ──(HTTP)──► FastAPI ────────┤          │
AI assistant ─(stdio)► MCP server ─────┘          ├──► Portkey gateway ──► Bedrock / Claude Sonnet 4.5
                                                  ├──► Anthropic Messages API (optional)
                                                  └──► audit/fathom-audit.jsonl
Build time: scripts/fetch_data.py ──► Hugging Face Hub ──► data/*.parquet + data/SOURCES.md
```

## Component breakdown (C4 L2)

| Component | Module | Responsibility | Data it holds | Tier (build) |
|---|---|---|---|---|
| Config | `fathom/config.py` | `Settings` from environment: provider, base URL, model, key names, audit path and flags, disclaimer text, universe | secrets by name only | T2 |
| Errors | `fathom/errors.py` | `FathomError` + `Code` enum (error taxonomy, LLD §7) | — | T2 |
| Data access | `fathom/data.py` | Load and cache the four parquet fixtures; universe check | fixtures | T2 |
| Quotes | `fathom/quotes.py` | `QuoteCard` from bars + quote snapshot; derived context (52-week, YTD, 1y, 30d, series) | — | T2 |
| Filings | `fathom/filings.py` | `Filing`, `Section` models; section parser (TOC-dropping, Part-aware); period-end extraction; EDGAR URL | — | T2 |
| Retrieval | `fathom/retrieval.py` | In-package BM25 over sections and chunks per ticker; golden-query scoring | index in memory per ticker | T2 |
| Providers | `fathom/providers.py` | `Provider` protocol; `OfflineProvider` (extractive), `PortkeyProvider` (OpenAI-compatible), `AnthropicProvider` | — | T2 |
| Guard | `fathom/guard.py` | Advice-language patterns (input and output); citation verifier | — | T2 |
| Briefing | `fathom/briefing.py` | Prompt assembly under character caps, provider call, contract parsing, verification, guard, audit | — | T2 |
| Ask | `fathom/ask.py` | Retrieval → prompt → answer contract → verification, guard, audit; not-found path | — | T2 |
| Audit | `fathom/audit.py` | Append-only JSONL writer with the never-log rules | audit file | T2 |
| Bench | `fathom/bench.py` | Offline eval suite → `metrics/headline.json` | — | T2 |
| Surfaces | `app/main.py`, `fathom/cli.py`, `fathom/api.py`, `fathom/mcp_server.py` | Render / expose; no computation | — | T2 |
| Data fetch | `scripts/fetch_data.py` | Rebuild fixtures from Hugging Face | — | T0 |
| Gate | `scripts/check.py`, `scripts/secrets_scan.py`, `metrics/render.py` | One command; CI parity | — | T0 |

## Data architecture

| Store | Content | Classification | Owner | Consistency |
|---|---|---|---|---|
| `data/filings.parquet` | 97 rows: ticker, cik, company_name, form, filing_date, accession, text | public | fetch script | immutable fixture |
| `data/bars.parquet` | ~8 500 rows: symbol, date, open, high, low, close, volume | public | fetch script | immutable fixture |
| `data/quotes.parquet` | latest snapshot rows per symbol: last_price, pre_close, change_percent, volume, market_cap, pe, pb, dividend_yield, quote_time | public | fetch script | immutable fixture |
| `data/companies.parquet` | 20 rows: ticker, long_name, exchange, sector, industry, website | public | fetch script | immutable fixture |
| `audit/fathom-audit.jsonl` | one record per provider call (FR-011) | internal | runtime | append-only |
| `metrics/headline.json`, `metrics/card.json` | bench outputs | public | gate | regenerated, drift-checked |

Sections are parsed on load and cached in memory per process (`functools.cache` keyed by
accession); no derived store on disk.

## Critical flows

1. **Briefing (FR-002..FR-008, FR-011).** UI selects ticker → `quotes.quote_card` (bars + snapshot)
   → `filings.for_ticker` → `briefing.build_context` picks the most recent 10-K and the two most
   recent 10-Qs, takes the canonical sections, truncates each to its character cap, and assembles
   the system + user prompt → `provider.complete_json` → parse into `Briefing` (invalid JSON →
   one repair retry with the parse error, then `Code.CONTRACT_INVALID`) → `guard.verify_claims`
   sets `verified` per claim → `guard.scrub_advice` replaces flagged claims → `audit.record` →
   page renders sections with badges and the disclaimer.
2. **Ask (FR-009).** Input guard on the question → `retrieval.search(ticker, question, k=6)` over
   sections and chunks → if best score < floor: `Answer(not_found=True)` and no call → else prompt
   with the chunks → `Answer` contract → verify → scrub → audit → render with citations.
3. **Offline path (FR-010).** Same as 1 and 2 but `OfflineProvider` composes the contract from
   the parsed sections: the first sentences of each canonical section become claims whose quote
   is the sentence itself, so verification passes by construction and the demo, CI and bench
   never need a key.
4. **Bench (FR-015).** Parser coverage over all 97 filings; retrieval hit-rate on the golden
   query set (query → expected section id per form); guard escapes on the adversarial set;
   verified share of offline briefings for the 20 tickers; injection test; write headline;
   render card; drift check.
5. **Fetch (FR-016).** Download four parquet files → filter to universe → dedupe companies →
   write fixtures and SOURCES.md; run by the owner, never by CI.

## Cross-cutting concerns

- Authn/z: none in the prototype (single-user laptop). Documented as the first hosting task.
- Audit: FR-011; the audit line is the compliance artefact; hashes allow later matching to
  gateway logs (Portkey keeps request logs on the client side).
- Observability: structured stdlib logging at INFO for provider name, model, latency, claim
  counts; never bodies or keys (LLD never-log list).
- Configuration: `Settings` from environment with defaults; secrets referenced by name.
- Errors: single taxonomy (LLD §7); surfaces map codes to exit code 2 / HTTP 4xx / UI notice.
- Idempotency: all reads are pure over fixtures; audit append is the only write.

## NFR design

| NFR | How it is met |
|---|---|
| NFR-001 latency offline | sections cached per accession; extractive provider is string slicing; bench measures |
| NFR-002 latency live | one call per briefing; prompt capped (NFR-010); `httpx` timeout 90 s |
| NFR-003 gate | `scripts/check.py` mirrors Lodestar's; CI workflow runs it |
| NFR-004 determinism | bench has no randomness; timing excluded from drift |
| NFR-005/006 secrets, never-log | keys only via `Settings`; secrets scan patterns; log-redaction test with a fake handler |
| NFR-007 grounding | verifier is exact after normalisation; offline claims are quotes by construction; live claims measured |
| NFR-008 guard | pattern set unit-tested against the adversarial list |
| NFR-009 fixture size | test asserts sum of `data/*.parquet` ≤ 20 MB |
| NFR-010 prompt cost | per-section character caps (10-K Item 1A: 12 000; Item 7: 16 000; 10-Q Item 2: 16 000; others 6 000) ≈ 25–35 k tokens |
| NFR-011 accessibility | badge text "verified" / "unverified" beside colour; labels and as-of stamps on every metric |

## Tech-stack decision

| Layer | Options | Trade-off | **Recommendation** | Rationale vs this client |
|---|---|---|---|---|
| UI | Streamlit; Gradio; React + API | Streamlit fastest to a credible page and testable headless; React is polish the brief discounts | **Streamlit** | "Focus on core functionality over polish"; matches the challenge's suggested stack |
| Orchestration | n8n; LangChain; plain Python | n8n is offered but hides the grounding logic in a canvas; LangChain adds abstraction over one call; plain Python keeps the verifier explicit and testable | **Plain Python (`httpx`)** | The verifier is the product; it must be readable in an interview |
| LLM path | Portkey gateway (given); direct Anthropic; local model | Portkey is the client's gateway with logging and key management; direct Anthropic is a fallback; local models are out of the time box | **Portkey primary, Anthropic secondary, offline default** | Uses the client's platform; demo cannot fail |
| Retrieval | BM25 in-package; `rank_bm25`; embeddings + FAISS/Chroma | In-package BM25 is ~60 lines, deterministic, no deps; embeddings need a model download and add nondeterminism | **In-package BM25 over SEC items and chunks** | Five documents per ticker; explainability to a compliance reviewer |
| Data | Parquet fixtures via pyarrow/pandas; DuckDB; SQLite | Fixtures are read-only and small; a database adds nothing yet | **Parquet + pandas** | Fresh-clone simplicity |
| Packaging / gate | uv + hatchling + ruff + mypy strict + pytest | Owner standard | **Same** | CI parity with prior repos |

## Build-time model routing

`config/model-routing.yaml`: T0 scripts; T1 unused (no Haiku-class step is on the critical
path — commit messages and ledger entries are produced by the orchestrator's scripts); T2 =
Claude Sonnet, effort high, for Implementer, Verifier and Security roles at every risk class
(owner override, STATE.md routing overrides); T3 = this session for Phases 0–4, gate synthesis
and second-strike diagnosis. Verifiers run in a git worktree pinned to the task's commit.

## Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Portkey instance rejects the OpenAI-compatible call shape on the day | medium | live path down | Anthropic-SDK-shaped fallback header set behind the same provider; offline path always works; smoke script `fathom probe` prints the gateway response shape |
| Model returns non-JSON or wrong schema | medium | briefing fails | one repair retry with the error text; contract error surfaces cleanly; offline path in UI as a button |
| Section parser misses a filing's items (formatting drift) | medium | thin briefing | bench coverage assertion over all 97 filings at build time; the prompt falls back to the first N characters of the filing when a canonical section is missing |
| Verified share in live mode is low because the model paraphrases quotes | medium | trust | prompt demands verbatim quotes ≤ 40 words; normalisation tolerates whitespace and quote glyphs; unverified claims are flagged, not hidden |
| Universe of 20 tickers looks small | low | perception | slide and README state the fixture choice and the refresh command; larger universes are a data task, not a design change |
| Embedding upgrade needed for many filings | low (prototype) | retrieval quality | retrieval module has one interface (`search`) so a hybrid ranker can replace BM25 without touching callers |

## Decisions

D-000 (gate authorisation), D-001 (name), D-002 (data), D-003 (verifiable citations); D-004
(BM25 over embeddings) and D-005 (Portkey call shape) recorded in `decisions.md` at G2.
