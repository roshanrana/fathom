# Code graph (graphify)

Fathom carries a tree-sitter code graph so agents (and people) can ask "what calls this?",
"how do A and B connect?" and "what is X?" with file:line answers instead of grepping. The
committed `graphify-out/GRAPH_REPORT.md` is the human-readable map; `graph.json` and the HTML
view are rebuilt locally in seconds and are not committed.

## Build and query

```bash
graphify update .                                   # AST only, offline, ~5 s (1,314 nodes, 2,859 edges, 105 communities on 2026-09-12)
graphify query "how is a claim verified" --budget 800
graphify explain "brief"
graphify path "quote_card" "load_frame"
graphify affected "verify_claim" --depth 2
```

`make graph` (Linux/macOS) runs the update plus a cluster pass with no visualisation.

## Three real queries

`graphify explain "brief"` — the briefing entry point and its 32 connections (trimmed):

```
Node: brief()   Source: fathom/briefing.py L276   Degree: 32
  --> build_context() [calls]     --> make_provider() [calls]
  --> _obtain_draft() [calls]     --> scrub_claims() [calls]
  --> record() [calls]            --> Briefing [calls]
  <-- cli.py, api.py, main.py, mcp_server.py, bench.py [imports]
  <-- create_app() [calls]        <-- _injection_check() [calls]
```

`graphify path "quote_card" "load_frame"`:

```
Shortest path (2 hops):
  quote_card() <--contains-- quotes.py --imports--> load_frame()
```

`graphify affected "verify_claim" --depth 2` — blast radius of the citation verifier (trimmed):

```
- _to_claim() [calls] fathom/briefing.py:L246
- _claims_from_draft() [calls] fathom/briefing.py:L259
- briefing.py [imports] fathom/briefing.py:L1
- api.py, bench.py, cli.py, mcp_server.py, main.py [imports_from]
- test_guard.py: 4 tests; test_audit.py: 1 test; test_briefing.py [imports_from]
```

Quirk seen: plain names are sometimes AMBIGUOUS across modules (e.g. `main`); use the node id
printed by `graphify explain` (such as `fathom_briefing_brief`).

## What is excluded

`.graphifyignore`: `.venv/`, `.cache/`, `.worktrees/`, `graphify-out/`, `htmlcov/`,
`node_modules/`, `data/*.parquet`, `uv.lock`, minified JS.

## Hooks (local opt-in)

`graphify install --project` also writes PreToolUse hooks into `.claude/settings.json` that nag
before every Read/Grep. They are not committed; install locally if you want them.

## How Shipyard packs use it

Implementers run `graphify query`/`explain` before opening files; Verifiers run `graphify
affected` on every symbol a diff touches and treat impact outside the pack's scope as a finding
(see `docs/tasks/*.verdict.md`).
