---
id: T-015
title: Provider transport and malformed-response errors; CLI guarded-claim rendering
milestone: M3
risk: medium
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-004, T-009]
rtm: [FR-010, FR-013, NFR-002]
status: todo
---
# T-015 — Provider transport and malformed-response errors; CLI guarded-claim rendering

## Goal
Close D-010: no raw `httpx` exception or `KeyError`/`IndexError` escapes a provider; the CLI
renders guarded claims without "? ? ?".

## Spec references
`03-lld.md §2.7` errors (D-010, verbatim): non-2xx → `PROVIDER_HTTP` with `{"status", "provider"}`
only; `httpx.TimeoutException` → `PROVIDER_TIMEOUT`; any other `httpx.HTTPError` (connect refused,
DNS, protocol errors) → `PROVIDER_HTTP` with `{"status": 0, "provider", "reason": <exception class
name>}`; a 2xx body that is not JSON or lacks the expected keys/indices → `PROVIDER_HTTP` with
`{"status": <code>, "provider", "reason": "malformed response"}` (never the body); missing key →
`PROVIDER_CONFIG` naming the variable, raised before any client is built. No raw `httpx` or
`KeyError`/`IndexError` escapes a provider. The `FathomError.message` for these reads
`"<provider> provider request failed (reason=<reason>)"` / `"<provider> provider returned HTTP
<status>"`. Prior finding closed: T-004.security.md F1 (MEDIUM). CLI (`§4`): in the non-JSON
rendering of `brief`/`ask`, a claim whose source accession is empty prints `(no source)` instead
of the form/date/section triple.

## Scope (files this task may touch)
- fathom/providers.py, fathom/cli.py
- tests/test_providers.py, tests/test_cli.py

## Acceptance criteria
- AC1: With `httpx.MockTransport` handlers that raise `httpx.ConnectError`, `httpx.RemoteProtocolError` and `httpx.ReadTimeout`, `PortkeyProvider.complete_json` raises `PROVIDER_HTTP` (reason "ConnectError" / "RemoteProtocolError", status 0) and `PROVIDER_TIMEOUT` respectively; the same for `AnthropicProvider`; no message or details contain the key or URL query.
- AC2: A 200 response with body `{"choices": []}`, `{"foo": 1}`, `"not json"` (invalid JSON) and `{"choices": [{"message": {}}]}` each raise `PROVIDER_HTTP` with reason "malformed response" and details without the body; same shapes for Anthropic (`{"content": []}` etc.).
- AC3: `fathom brief AAPL` with `FATHOM_LLM_PROVIDER=portkey PORTKEY_API_KEY=x PORTKEY_BASE_URL=http://127.0.0.1:9/v1` exits 2 with stderr `error PROVIDER_HTTP: portkey provider request failed (reason=ConnectError)` (tested with `CliRunner` and a monkeypatched transport, not a real socket).
- AC4: `fathom ask AAPL "Should I buy Apple stock?"` (offline) renders the guarded claim line ending in `(no source)`; the JSON rendering is unchanged.
- AC5: All existing provider/CLI tests still pass; mypy strict clean; full gate green; tests named `test_fr010_*`, `test_fr013_*`, `test_nfr002_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_providers.py tests/test_cli.py -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] no raw httpx/KeyError/IndexError escapes (fuzz the response shapes)
- [ ] no key, URL query or body in any message/details/log
- [ ] tests named with RTM IDs; no new dependencies

## Threat-model boundary touched
B2 (gateway egress; malformed/spoofed responses) — fresh Security Reviewer at T2 confirms closure of T-004 F1.

## Handoff (Implementer fills, ≤10 lines)
Implemented in fathom/providers.py: shared `_timeout_error`/`_transport_error`/`_http_status_error`/
`_malformed_response_error` builders plus one parse helper per provider
(`_parse_portkey_payload`, `_parse_anthropic_payload`) catching
`json.JSONDecodeError`/`KeyError`/`IndexError`/`TypeError` around the 2xx body decode+index, never
including the body. `complete_json` now catches `httpx.TimeoutException` before the general
`httpx.HTTPError`. Messages: "<name> provider request failed (reason=<reason>)" (timeout/transport/
malformed) and "<name> provider returned HTTP <status>" (non-2xx). CLI: `_claim_line` in
fathom/cli.py prints `(no source)` when `claim.source.accession` is empty (covers `fathom ask`'s
input-guard claim). Added tests test_nfr002_* (providers: ConnectError/RemoteProtocolError/timeout
x2 providers, malformed-body parametrized x2 providers; cli: monkeypatched-transport ConnectError
exit-2 case) and test_fr013_* (no-source text + unchanged JSON rendering) in
tests/test_providers.py / tests/test_cli.py. Full gate green (257 tests, mypy strict both
platforms, ruff, no secrets, bench/card drift clean). Not touched: no new deps; scope respected.
