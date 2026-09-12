# Demo checklist — 20-minute interview

## Before the session (5 min)

1. `cd C:\Code-Central\fathom && uv sync --all-extras && uv run python scripts/check.py` — gate green.
2. Open `docs/pitch/fathom-pitch.pptx` in PowerPoint (slide-show mode ready).
3. Terminal A: `uv run fathom app` — page open at http://localhost:8501, ticker AAPL selected, offline briefing already generated (click "Generate briefing" once so the cached page is instant).
4. Terminal B (live path, once the key arrives):
   ```
   $env:FATHOM_LLM_PROVIDER="portkey"; $env:PORTKEY_API_KEY="<key from the panel>"
   uv run fathom probe
   ```
   `probe` prints provider, model, latency and "pong". If it errors, keep the offline page and say so.
5. Have `uv run fathom brief NVDA --json` ready in Terminal B to show the contract and the audit line (`Get-Content audit\fathom-audit.jsonl -Tail 1`).

## Flow (≈ 12 min demo + 8 min questions)

| Min | Beat | Say |
|---|---|---|
| 0–2 | Slide | Problem → four steps → what the prototype proves → why compliance can say yes. |
| 2–5 | Page, AAPL | Quote card with as-of stamps and sources; chart; filings table with EDGAR links. "Every number here is from a public dataset; nothing is typed in." |
| 5–8 | Briefing | Walk one section: claim → ✅ verified badge → source caption. Point at an ⚠️ unverified one if live mode produced any: "flagged, never hidden". |
| 8–10 | Ask | "What are the main risk factors?" → cited answer. Then "Should I buy?" → guard notice. "The tool describes; it never advises." |
| 10–12 | Live switch | Terminal B: `fathom probe`, then regenerate a briefing in live mode (or show the JSON brief). Show the audit line: hashes, model, latency, verified counts, no bodies. |
| 12–20 | Defend | See the question bank below. |

## Likely questions and the one-line answer

- **Why not a vector database?** Five filings per ticker, already structured into SEC items; BM25 over sections is explainable to compliance and deterministic in CI. The retrieval interface is one function; embeddings are a drop-in when the universe grows (D-004).
- **How do you know the model isn't making things up?** It must return a verbatim quote per claim; the app checks the quote against the filing text; the badge is the control; the eval suite reports the verified share (D-003).
- **What does the offline mode prove?** That the plumbing, contracts, guard and audit work without a model; its 100 % verified share is by construction. Live-mode quality is measured from the audit log, not asserted (D-005).
- **What did the model tiering look like?** Frontier model for design, threat model, contracts and orchestration; Sonnet for every implementation, verification and security review; each task verified by a fresh context in a pinned worktree; hash-chained evidence ledger.
- **What broke?** Two frozen specs were wrong (a cross-reference-sheet 10-K; guard inflections), a security review found an unbounded claim path, and a resilience check found unmapped transport errors. Each became a decision, a pack, a fix and a re-review (D-006 … D-010).
- **What would the pilot need?** Full EDGAR universe and a live quote feed; SSO in front of the API; tamper-evident audit sink; an advisor eval set built with compliance; retrieval hit-rate above 0.9.
- **Cost?** One gateway call per briefing, capped at ≈ 30 k input tokens by section caps; per-call token counts land in the audit log.

## If something fails

- Live call fails → `error PROVIDER_*` on screen; say "this is the runbook path", switch the sidebar/env to offline, continue.
- Streamlit hiccup → `uv run fathom brief AAPL` in the terminal shows the same briefing as text.
