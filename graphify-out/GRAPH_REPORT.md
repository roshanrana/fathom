# Graph Report - fathom  (2026-09-12)

## Corpus Check
- 55 files · ~33,201 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 567 nodes · 897 edges · 47 communities (40 shown, 7 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `028e3de0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]

## God Nodes (most connected - your core abstractions)
1. `FathomError` - 59 edges
2. `Code` - 47 edges
3. `Settings` - 29 edges
4. `quote_card()` - 21 edges
5. `make_provider()` - 20 edges
6. `load_frame()` - 17 edges
7. `Filing` - 14 edges
8. `OfflineProvider` - 13 edges
9. `filings_for()` - 12 edges
10. `ProviderResult` - 12 edges

## Surprising Connections (you probably didn't know these)
- `LogCaptureFixture` --uses--> `Code`  [INFERRED]
  tests/test_providers.py → fathom/errors.py
- `Path` --uses--> `Code`  [INFERRED]
  tests/test_filings.py → fathom/errors.py
- `DataFrame` --uses--> `Code`  [INFERRED]
  tests/test_quotes.py → fathom/errors.py
- `date` --uses--> `Code`  [INFERRED]
  tests/test_quotes.py → fathom/errors.py
- `Path` --uses--> `Code`  [INFERRED]
  tests/test_quotes.py → fathom/errors.py

## Import Cycles
- 1-file cycle: `fathom/quotes.py -> fathom/quotes.py`

## Communities (47 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (43): Fathom Streamlit page — walking skeleton (T-008 replaces this)., Exception, _parse_bool(), Runtime configuration (LLD §2.1)., Build settings from a mapping of environment variables.          Reads `os.envir, Company, load_frame(), DataFrame (+35 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (41): Client, Application configuration, built from environment variables., Settings, AnthropicProvider, make_provider(), OfflineProvider, PortkeyProvider, Provider (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (40): datetime, _optional_float(), _pct_change(), PricePoint, Any, quote_card(), QuoteCard, Quote card and price context (LLD §2.4). (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (27): 10. Test strategy, 11. Migration / cutover, 1. Repository layout, 2.10 `briefing.py`, `ask.py` — see §3 contracts and §6 prompts., 2.1 `config.py`, 2.2 `errors.py`, 2.3 `data.py`, 2.4 `quotes.py` (+19 more)

### Community 4 - "Community 4"
Cohesion: 0.19
Nodes (18): BaseModel, Answer, AnswerDraft, Briefing, BriefingDraft, Claim, DraftClaim, Frozen output contracts (LLD §3).  `Briefing`/`Answer` are what Fathom returns t (+10 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (17): edgar_url(), filings_for(), period_end(), date, Filings listing and canonical-section parser (LLD §2.5)., List a ticker's filings newest first., Build the EDGAR filing-index URL for a CIK/accession pair., Extract the fiscal period-end date from the first 4,000 characters of `text`. (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (14): _claim(), _claims_from(), _excerpt_for_section(), _liquidity_claims(), _numeric_token_count(), _offline_ask(), _offline_briefing(), _offline_complete() (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.16
Nodes (14): Path, Return the canonical sections for one filing, cached by (accession, data_dir)., One canonical section parsed from a filing's normalised text (LLD §2.5)., Section, sections_for(), Path, AC4: every 10-K yields 1A/7; every 10-Q yields I.2, across all 97 fixtures., AC5: sections_for is cached (same object) and Section.text matches the slice. (+6 more)

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (12): Architecture style and rationale, Build-time model routing, Component breakdown (C4 L2), Critical flows, Cross-cutting concerns, Data architecture, Decisions, High-level design — Fathom (+4 more)

### Community 9 - "Community 9"
Cohesion: 0.48
Nodes (11): Path, append(), cmd_export(), cmd_rtm(), entry_hash(), git_sha(), main(), read_entries() (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (10): Claim, is_advice(), normalise(), Advice guard and citation verifier (LLD §2.8, patterns frozen at §6.4)., True when `text` matches any of the frozen advice patterns., Casefold, map curly quotes to straight ones, collapse whitespace, strip., A quote verifies when it has 6-60 words and appears verbatim (normalised) in the, Replace advice-flagged claims' text with `GUARD_NOTICE`.      Returns a new list (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (11): parse_sections(), _part_lookup(), Return a closure mapping a position to the nearest preceding Part numeral., Parse `text` into canonical sections (pure; caller fills `Section.accession`)., Match, A filing with zero canonical sections raises PARSE_FAILED., AC2: a TOC entry is dropped in favor of the real (longer) section body., AC3: 10-Q Part/Item ids come out in document order; a short real body survives. (+3 more)

### Community 13 - "Community 13"
Cohesion: 0.45
Nodes (10): anchors(), build_bars(), build_companies(), build_filings(), build_quotes(), download(), main(), DataFrame (+2 more)

### Community 14 - "Community 14"
Cohesion: 0.18
Nodes (10): Acceptance criteria, Acceptance criteria, Findings, Findings, Gate, Gate, Verdict T-000 — FAIL, Verdict T-000 — PASS (attempt 2) (+2 more)

### Community 15 - "Community 15"
Cohesion: 0.20
Nodes (9): Business outcome and measures, Constraints, Data classification, Integration landscape (summary), Open questions, Problem brief — Fathom, Problem statement, Regulatory and control context (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.20
Nodes (9): Actors, Agentic build pipeline boundary, AI-risk section (controls-evidence §8), Assets, High-risk components (feeds Planner's risk class), Open items, STRIDE table, Threat model — Fathom (+1 more)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-000 — Foundation and walking skeleton, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-001 — Quote card and price context, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 19 - "Community 19"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-002 — Filings list and section parser, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 20 - "Community 20"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-003 — BM25 retrieval, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-004 — Prompts and providers, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-005 — Contracts, guard and audit, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-006 — Briefing pipeline, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-007 — Grounded Q&A, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-008 — Streamlit page, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-009 — CLI and HTTP API, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-010 — Bench and metrics card, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 28 - "Community 28"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-011 — Documentation and screenshots, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-012 — MCP server (Could), Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.20
Nodes (9): Acceptance criteria, Goal, Handoff (Implementer fills, ≤10 lines), Scope (files this task may touch), Spec references, T-000 — <short title>, Threat-model boundary touched, Validation commands (targeted) (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.22
Nodes (8): Budget summary, Dependency graph, Execution plan — Fathom, Milestones, Risks to the plan, Task table, Validation gates per milestone, Wave schedule

### Community 32 - "Community 32"
Cohesion: 0.47
Nodes (8): Path, bullets(), load_budgets(), main(), parse_frontmatter(), parse_scalar(), section_body(), validate()

### Community 33 - "Community 33"
Cohesion: 0.22
Nodes (8): Blocked, Budget ledger, Deviations from plan, Gate log, Now / next, Routing overrides, STATE — Fathom, Task log

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (7): Assumptions (owner to confirm), Constraints, Functional requirements, Non-functional requirements (budgets), Out of scope (explicit), Requirements — Fathom, RTM seed

### Community 35 - "Community 35"
Cohesion: 0.25
Nodes (7): D-000 — Standing autonomous authorisation for gates G0–G4, G7, G8   (2026-09-12, phase 0, status: accepted), D-001 — Name: Fathom   (2026-09-12, phase 0, status: accepted), D-002 — Demo data from Hugging Face, committed as fixtures   (2026-09-12, phase 0, status: accepted), D-003 — Grounding by verbatim citation, not by trust   (2026-09-12, phase 0, status: accepted), D-004 — Lexical BM25 over SEC items and chunks, no vector store   (2026-09-12, phase 2, status: accepted), D-005 — Providers speak one JSON contract; the offline provider is a real provider   (2026-09-12, phase 2, status: accepted), Decisions (append-only ADR log)

### Community 36 - "Community 36"
Cohesion: 0.25
Nodes (7): Acceptance criteria, Findings, Gate, Quality spot-checks (non-blocking), Spec conformance (LLD §2.5, literal check), Verdict T-002 — PASS, Verification checklist

### Community 37 - "Community 37"
Cohesion: 0.33
Nodes (5): Acceptance criteria, Findings, Gate, Verdict T-001 — PASS, Verification checklist

### Community 38 - "Community 38"
Cohesion: 0.40
Nodes (4): data_dir(), Path, Shared pytest fixtures., The repo's real fixture directory (data/*.parquet).

### Community 39 - "Community 39"
Cohesion: 0.50
Nodes (3): Anchors (hand-checkable values used by tests), Coverage, Data sources

## Knowledge Gaps
- **214 isolated node(s):** `fathom`, `Path`, `Run it`, `Now / next`, `Blocked` (+209 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FathomError` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 11`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `Code` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 11`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `datetime` connect `Community 2` to `Community 0`, `Community 4`, `Community 5`, `Community 9`, `Community 13`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `FathomError` (e.g. with `Client` and `datetime`) actually correct?**
  _`FathomError` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `Code` (e.g. with `Client` and `datetime`) actually correct?**
  _`Code` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Settings` (e.g. with `Client` and `Code`) actually correct?**
  _`Settings` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Fathom Streamlit page — walking skeleton (T-008 replaces this).`, `Fathom — SEC filing and market data briefings for advisor preparation.`, `Runtime configuration (LLD §2.1).` to the rest of the system?**
  _299 weakly-connected nodes found - possible documentation gaps or missing edges._