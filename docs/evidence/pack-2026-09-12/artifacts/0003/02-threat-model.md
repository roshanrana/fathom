# Threat model — Fathom

## Assets

| Asset | Classification | Why it matters |
|---|---|---|
| Portkey API key (and optional Anthropic key) | restricted (secret) | Client-issued; leakage means spend and reputational exposure |
| Briefing and answer output | internal | An advisor may repeat it to a client; wrong or advice-like content is a conduct risk |
| Audit log | internal | Compliance evidence; must be complete and not contain secrets or client identity |
| Filing and price fixtures | public | Integrity matters: tampered fixtures produce plausible false briefings |
| Evidence ledger and design docs | internal | The build's own control record |

## Actors

Legitimate: advisor (single local user), owner/operator, CI, Portkey gateway.
Adversarial: a filing author or dataset publisher embedding instructions in text (prompt
injection via data); a curious user trying to extract advice or the system prompt; a malicious
dependency; an agent (build pipeline) acting on instructions found in repo content; an operator
mistake (key in repo, bodies in logs).

## Trust boundaries

| # | Boundary | Diagram ref |
|---|---|---|
| B1 | Browser / CLI / HTTP client ↔ fathom package (user input) | HLD context |
| B2 | fathom package ↔ Portkey gateway / Anthropic (network egress, key) | HLD context |
| B3 | fathom package ↔ fixtures on disk (data trust) | HLD data |
| B4 | fathom package ↔ audit file (what leaves into logs) | HLD data |
| B5 | Build pipeline: agents ↔ repo, Hugging Face downloads, tickets | SKILL §agent security |

## STRIDE table

| Boundary | Threat | Scenario | Likelihood | Impact | Controls | Residual | Accepted by |
|---|---|---|---|---|---|---|---|
| B1 | S | None (no identity in the prototype) | — | — | Documented: hosting requires SSO in front (C-08) | accepted for local demo | owner |
| B1 | T/E | User crafts a question to elicit recommendations or to override the system prompt | high | medium | Input guard (FR-008); system prompt states document text and user text are data; output guard on every claim; no tool calls in the model loop (C-09, C-22) | model may still phrase borderline language; flagged not hidden | owner |
| B1 | I | Error messages leak internals | low | low | Error taxonomy; API 500 body is generic (C-12) | none | owner |
| B1 | D | Large or repeated requests | low | low | Single user; `httpx` timeouts; no retries beyond one repair | none | owner |
| B2 | I | Key leaks via repo, logs, UI or error text | medium | high | Keys only from env by name; secrets scan in gate; never-log list tested; UI shows provider name only (C-07, C-12) | none | owner |
| B2 | T | Gateway response spoofed or malformed | low | medium | HTTPS; JSON contract validation; `CONTRACT_INVALID` path | none | owner |
| B2 | I | Filing text leaves to the provider | certain | low | Filings are public; questions are advisor-authored internal text; documented in data classification; Portkey is the client's own gateway | accepted | owner |
| B2 | R | No record of what the model said | medium | high (compliance) | Audit log with hashes, counts, model, latency; bodies opt-in (C-11) | audit file is local, not tamper-evident | owner (prototype) |
| B3 | T | Fixture tampering yields false briefings | low | high | Fixtures rebuilt by a script from named datasets with recorded row counts; `SOURCES.md`; git history; bench coverage would shift | no signature on fixtures | owner |
| B3 | T/E | Prompt injection embedded in filing text | medium | medium | Text is data (prompt); structured contract; verifier requires quotes from the source, so injected instructions cannot become "verified" claims unless they are literally in the filing (then they are quoted, not obeyed); FR-018 test (C-22) | model may follow an instruction in the text; guard catches advice; other effects limited to content quality | owner |
| B4 | I | Audit file contains prompts, questions or keys | medium | medium | Default mode stores hashes and counts only; bodies behind `FATHOM_AUDIT_BODIES=1`; redaction test (C-12) | opt-in mode stores bodies by design | owner |
| B5 | T/E | Agent obeys instructions found in datasets, docs or tool output | medium | high | Shipyard rule 10; verifier separation; scanners in gate; downloads only from named Hugging Face ids (C-21, C-22) | — | owner |
| B5 | T | Malicious dependency | low | high | Minimal pinned dependency set (`uv.lock`); no new dependency without pack listing (C-13) | no SBOM tooling in the time box | owner |

## High-risk components (feeds Planner's risk class)

- `providers.py` (external interface, secret handling) — risk: medium (no money movement,
  public data) with security review of the diff.
- `guard.py`, `briefing.py`, `ask.py` (conduct-risk controls) — risk: medium.
- `audit.py` (never-log rules) — risk: medium.
- Everything else — risk: low.

No task meets the SKILL's `risk: high` criteria (no authn/z, money movement, PII, crypto, IaC
or migration); all verification stays at T2 per the owner's routing override.

## AI-risk section (controls-evidence §8)

| Item | Fathom |
|---|---|
| Model inventory | One model: Claude Sonnet 4.5 via Portkey (`@aws-bedrock-use2/us.anthropic.claude-sonnet-4-5-20250929-v1:0`); optional direct Anthropic model id from config; purpose: briefing and Q&A generation over public filings; owner: Roshan Rana |
| Evaluation suite | `fathom bench` in the gate: parser coverage, retrieval hit-rate, guard escapes, verified share, injection test |
| Guardrails | Input and output advice guard; citation verifier; JSON contract; no model tool use; disclaimer on every surface |
| Prompt-injection testing | FR-018 test with an injected section and a scripted provider |
| Monitoring | Audit log fields (latency, tokens, verified share, guard hits); ORR lists alert candidates |
| Data governance | Public filings and advisor questions leave to the client's gateway; no PII; bodies not retained locally by default |
| Model-risk sign-off | Owner, recorded at G8 |

## Agentic build pipeline boundary

Agents run with the repo and fixtures only; no production systems exist. Hugging Face downloads
are pinned to dataset ids and recorded with row counts. Any instruction found in fixture text,
dataset cards or tool output is reported, not acted on. Verifiers run in pinned worktrees.

## Open items

1. Tamper-evident audit (hash chain like the evidence ledger) — backlog for hosting.
2. SBOM and dependency audit tooling — backlog; `uv.lock` pins for now.
