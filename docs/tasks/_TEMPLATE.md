---
id: T-000
title: <short title>
milestone: M0
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: []
rtm: []
status: todo
---
# T-000 — <short title>

## Goal
<2–3 lines: what exists when this task is done>

## Spec references
<`03-lld.md §x.y` — paste the exact excerpt, ≤30 lines>

## Scope (files this task may touch)
- <path>

## Acceptance criteria
- AC1: <testable statement>
- AC2: <testable statement>

## Validation commands (targeted)
- `<command>`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] error taxonomy used
- [ ] no sensitive fields logged
- [ ] tests named with RTM IDs
- [ ] no new dependencies (or listed and audited)

## Threat-model boundary touched
none

## Handoff (Implementer fills, ≤10 lines)
