# Problem brief — Fathom

## Problem statement

Verbatim (Perficient "AI Prototype Challenge", scenario 2, Finance):

> A wealth management firm wants a solution that helps advisors quickly get up to speed on a
> stock — fetching current quote data and summarizing key information from recent SEC filings.

Challenge framing, verbatim: "Build a working prototype that demonstrates a viable AI solution.
Prepare a single slide that pitches your solution to client stakeholders. Demo and defend your
approach in a live interview. [...] Does not need to be production-ready. Interface approach is
up to you — chat, form, report, API, or something else. Focus on core functionality over polish.
[...] Data is not provided — you are responsible for sourcing or creating your own."

Restated: an advisor has minutes before a client call about a stock they do not follow. Fathom
takes a ticker and returns one page: the current quote with context (range, valuation, trend),
the company's most recent 10-K and 10-Qs with links to EDGAR, and an AI briefing of what those
filings say that matters — results, risks, liquidity, notable disclosures, talking points — where
every claim is cited to a verifiable passage in the filing and nothing reads as investment advice.
The advisor can then ask follow-up questions grounded in the same filings.

The name: to fathom something is to get to the bottom of it; a fathom is also the unit a navigator
uses to sound depth. Fathom sounds the depth of a stock quickly.

## Business outcome and measures

| Outcome | Measure | Baseline | Target | By when |
|---|---|---|---|---|
| Advisor prep time for an unfamiliar stock | Wall-clock from ticker entry to a briefing on screen | 30–60 min reading filings | ≤ 90 s (live LLM path) / ≤ 5 s (offline path) | demo |
| Briefing is trustworthy | Share of briefing claims with a verified citation (quoted passage found verbatim in the cited filing section) | n/a | ≥ 90 % verified; unverified claims visibly flagged, never hidden | demo |
| Briefing is compliant for advisor use | Advice-language guard blocks recommendation phrasing; disclaimer present; every LLM call audit-logged | n/a | 0 guard escapes in the eval set; 100 % of calls logged | demo |
| Demo cannot fail on the day | Full flow works with no network and no API key (offline extractive briefing); live path is a config switch | n/a | Fresh clone, `uv sync`, one command | demo |
| Live interview: defensible design | Panel questions on grounding, compliance, cost, and scale answered from the design docs and the evidence ledger | n/a | Shipyard docs complete through G8 | 2026-09-12 |
| Portfolio: repo demonstrates FDE practice | Shipyard lifecycle evidence, provider abstraction (Portkey / Anthropic / offline), eval suite, measured card, CI gate | n/a | shipped to `roshanrana/fathom` | 2026-09-12 |

## Users and actors

| Actor | Type | Needs | Volume |
|---|---|---|---|
| Wealth-management advisor | human, primary | One page per ticker: quote with context, recent filings, cited briefing, follow-up Q&A; no advice language they could be held to | several per day |
| Compliance / supervision | human, secondary | Audit trail of what the AI produced from which sources with which model; guard evidence | on review |
| Interview panel (client stakeholders) | human | Live demo, slide, answers on design and trade-offs | once |
| Portkey gateway → Claude Sonnet 4.5 (Bedrock) | system, external | Chat-completions requests with a key injected at runtime | per briefing / question |
| Hugging Face datasets (build time only) | system, external | Source of demo filings and prices; fetched by a script, committed as fixtures | at build |
| CI | system | One gate command, deterministic, offline | every push |

## Regulatory and control context

- Jurisdictions / regulators: none binding on the prototype. The client context is a US
  wealth-management firm (FINRA / SEC supervised); the design borrows two of that world's
  constraints as product features: no investment recommendations from the tool (advice guard,
  disclaimer) and a books-and-records style audit log of AI output.
- Internal frameworks in force: Shipyard lifecycle (this repo); owner's portfolio conventions
  (measured card, single `check` gate, CI runs the gate, OVERVIEW.md + SHOWCASE.md).
- External frameworks aligned to: none formally. AI-component controls per
  `controls-evidence.md §8` (model inventory, eval suite in `check`, guardrails, prompt-injection
  test, data-governance note on what leaves the boundary).
- Named gate approvers:

  | Gate | Role | Name |
  |---|---|---|
  | G0–G4, G7, G8 | Delivery lead / product owner | Roshan Rana (standing autonomous authorisation for this build, D-000) |
  | G5, G6.x | CI + fresh-context Verifier | automated |

- Evidence expectations: hash-chained ledger, verdict per task, RTM, exported evidence pack;
  all reviewable by the interview panel if asked.

## Data classification

| Data element | Class | PII/PCI/MNPI | Residency | Retention |
|---|---|---|---|---|
| SEC filings text (10-K, 10-Q), 20 issuers, filed 2025-04 to 2026-05 | public | none | repo fixture (Hugging Face `musk1209/finsight-sec-filings`, MIT) | indefinite |
| Daily OHLCV bars, 20 tickers, 2025-01-02 to 2026-09-11 | public | none | repo fixture (Hugging Face `AlphaDojo/dojo_stock_kline`, Apache-2.0) | indefinite |
| Quote snapshots (price, market cap, P/E, P/B, yield), 20 tickers, 2026-07-20 to latest | public | none | repo fixture (Hugging Face `AlphaDojo/dojo_quote`, Apache-2.0) | indefinite |
| Company master (name, exchange, sector, industry, website) | public | none | repo fixture (Hugging Face `AlphaDojo/dojo_stock_info`, Apache-2.0) | indefinite |
| Advisor question text | internal | none expected; never stored with identity | sent to the LLM gateway; audit log stores a hash, not the text, by default | local JSONL, demo lifetime |
| LLM prompts and completions | internal | none | Portkey gateway (client-operated) → AWS Bedrock | audit log stores model, latency, token counts, citation-check result; bodies only when `FATHOM_AUDIT_BODIES=1` |
| Portkey API key | restricted (secret) | — | environment variable only, injected at runtime | never in repo, logs or UI |

No PII, PCI or MNPI is touched. Filings and prices are public disclosures.

## Constraints

- Hosting / sovereignty: local laptop for the demo; anything hosted later sits behind the
  client's identity provider (out of scope).
- Approved technology catalogue: Python 3.12, uv, Streamlit, FastAPI, Typer, pydantic, plotly,
  httpx, pyarrow/pandas (owner's standard stack; matches the challenge's suggested "Code +
  Frameworks" path). No vector database: five to six documents per ticker are section-chunked
  and ranked lexically (BM25); an embedding index is a documented upgrade path, not a prototype
  need.
- Approved AI providers: Portkey gateway (`https://portkeygateway.perficient.com/v1`, model
  `@aws-bedrock-use2/us.anthropic.claude-sonnet-4-5-20250929-v1:0`, key issued at interview);
  direct Anthropic API as a second live path; offline extractive provider as the default so the
  demo and CI never depend on a key.
- Build-time AI spend ceiling: T3 for design and orchestration only; all implementation,
  verification and security review at T2 (Sonnet, effort high) per owner instruction
  (memory: model-tiering-for-delegation).
- Hard dates: prototype, slide and evidence complete 2026-09-12 (today); interview date set by
  Perficient.
- Team and skills: one owner (FDE), AI agents under Shipyard; Windows dev host (no GNU make; the
  gate is `uv run python scripts/check.py`, Makefile wraps it for CI/Linux).

## Integration landscape (summary)

| Integration | Direction | Protocol | Notes |
|---|---|---|---|
| Portkey AI gateway | out | HTTPS, OpenAI-compatible `/chat/completions`, header `x-portkey-api-key` | Model named in the catalogue format `@provider/model`; `max_tokens` mandatory for Anthropic models |
| Anthropic Messages API | out (optional) | HTTPS `/v1/messages` | Same prompt contract; selected by `FATHOM_LLM_PROVIDER=anthropic` |
| SEC EDGAR | out (links only) | HTTPS URL built from CIK + accession | The UI links to the source filing; no live scraping in the prototype |
| Hugging Face Hub | out (build time) | HTTPS parquet download | `scripts/fetch_data.py` rebuilds `data/` deterministically; CI never calls it |

## Open questions

1. Live quote feed for the interview: the prototype's "current quote" is the latest bar in the
   committed snapshot (2026-09-11), stamped as-of. A live adapter (e.g. a market-data API with a
   key) is a documented extension, not built. (owner; before interview — accept as-is)
2. Interview environment: the Portkey key arrives at the start of the exercise; the app reads it
   from `PORTKEY_API_KEY` and falls back to offline if absent. Confirm outbound HTTPS is allowed
   from the demo laptop. (owner; interview day)
3. Ticker coverage: 20 large caps (AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, JPM, BAC, GS, JNJ,
   PFE, UNH, WMT, PG, KO, MCD, XOM, CVX, CAT). Any ticker outside the set returns a clear
   "not in demo universe" message listing the supported tickers. (owner; accepted)
