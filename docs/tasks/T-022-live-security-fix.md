---
id: T-022
title: Live security fix — EDGAR field validation, streamed size cap, reason sanitisation
milestone: M4
risk: medium
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-018, T-019]
rtm: [FR-021, FR-025]
status: todo
---
# T-022 — Live security fix: EDGAR field validation, streamed size cap, reason sanitisation

## Goal
Close T-018 security findings F1 (MEDIUM), F2 (MEDIUM) and F3 (LOW).

## Spec references
`05-m4-live-data.md` §4 throttle/cache ("bodies larger than 25 MB raise SOURCE_HTTP reason
'too large'") and B6 controls; `T-018.security.md` F1–F3. Rules added (frozen): (1) every value
taken from EDGAR JSON that is placed into a URL path is validated first — `accessionNumber`
against `^\d{10}-\d{2}-\d{6}$`, `primaryDocument` and older-page `name` against
`^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$` with no `..` — a failing value raises `SOURCE_HTTP` with
reason "invalid edgar field" (never echoing the value); (2) `LiveHttp.get` streams the response
(`client.stream`) and aborts with reason "too large" as soon as the accumulated bytes exceed
25 MB, before any decoding; (3) `SOURCE_HTTP.details["reason"]` for transport errors is the
exception class name only (`type(exc).__name__`), never `str(exc)`.

## Scope (files this task may touch)
- fathom/live/http.py, fathom/live/sec.py
- tests/test_live_http.py, tests/test_live_sec.py

## Acceptance criteria
- AC1: A submissions fixture edited to contain `accessionNumber: "../../etc"` and `primaryDocument: "../x.htm"` makes `filings()` raise `SOURCE_HTTP` reason "invalid edgar field" without the value in message/details; valid fixtures unchanged.
- AC2: A MockTransport that streams 30 MB in chunks triggers "too large" after ≤ 26 MB have been read (assert via a counting stream) and no `.text` decode occurs; a 20 MB body still succeeds.
- AC3: `httpx.ConnectError("http://host/secret?x=1")` → `details["reason"] == "ConnectError"` and the message contains no URL.
- AC4: Existing T-018 tests pass unchanged (behavioural); full gate green; mypy strict; tests named `test_fr021_*`, `test_fr025_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_live_http.py tests/test_live_sec.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] values from EDGAR JSON validated before URL construction
- [ ] size cap enforced while streaming
- [ ] no URL/body in any error

## Threat-model boundary touched
B6 — fresh Security Reviewer at T2 confirms closure of T-018 F1–F3.

## Handoff (Implementer fills, ≤10 lines)
