---
id: T-003
title: BM25 retrieval
milestone: M1
risk: low
tier: T2
complexity: normal
reasoning: off
budget: {input_tokens: 40000, tool_calls: 40, wall_clock_min: 45}
depends_on: [T-002]
rtm: [FR-009]
status: todo
---
# T-003 — BM25 retrieval

## Goal
In-package BM25 over each ticker's canonical sections split into chunks, exposed as
`retrieval.search(ticker, query, k, data_dir)`, deterministic and dependency-free.

## Spec references
`03-lld.md §2.6` (verbatim):
```python
class Chunk(BaseModel): doc_id: str; accession: str; section_id: str; text: str; ordinal: int
class Hit(BaseModel): chunk: Chunk; score: float
STOPWORDS: frozenset[str]   # the, a, an, and, or, of, to, in, on, for, with, by, at, from, as, is, are, was, were, be, been, this, that, these, those, it, its, we, our, us, company, inc, corp, may, will, which, has, have, had, not, than, also, other, such, any, all, per
def tokenize(text: str) -> list[str]                       # lowercase \w+ , len>=2, minus STOPWORDS
def chunk_section(section: Section, size: int = 1200, overlap: int = 200) -> list[Chunk]   # split at sentence boundaries when possible; doc_id f"{accession}#{section_id}#{ordinal}"
class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None
    def search(self, query: str, k: int = 6) -> list[Hit]   # hits with score > 0 only, descending, ties by doc_id
@functools.cache
def index_for(ticker: str, data_dir: Path) -> BM25Index    # all canonical sections of all filings for the ticker
def search(ticker: str, query: str, k: int, data_dir: Path) -> list[Hit]
```
Standard BM25: idf = ln((N − n + 0.5)/(n + 0.5) + 1). Chunking: walk sentences
(`re.split(r"(?<=[.!?])\s+", text)`); accumulate until adding the next sentence would exceed
`size`; start the next chunk with the trailing sentences that fit in `overlap` characters; a
single sentence longer than `size` becomes its own chunk (hard cut).

## Scope (files this task may touch)
- fathom/retrieval.py
- tests/test_retrieval.py

## Acceptance criteria
- AC1: `tokenize("The Company's risk factors, and its 10-K")` == `["risk", "factors", "10"]` (`\w+` splits "company's" into `company` — a stopword — and `s`, dropped for length; `the`, `and`, `its` are stopwords). The test asserts exactly this.
- AC2: Chunking a synthetic section of 30 sentences × ~80 chars with size 1200/overlap 200 yields chunks each ≤ 1200 chars (except a single over-long sentence case, tested separately), consecutive chunks share ≥ 1 sentence, ordinals are 0..n−1, doc_ids follow the pattern.
- AC3: On a three-document toy corpus, a query matching a term unique to doc B ranks B first with score > 0 and excludes documents with score 0; ties break by `doc_id` ascending.
- AC4: `search("AAPL", "risk factors", 6, data_dir)` returns hits whose top-1 `section_id` is `10-K:1A` or `10-Q:II.1A`; `search("AAPL", "liquidity and capital resources", 6, data_dir)` top-1 section is `10-K:7` or `10-Q:I.2`; `search("AAPL", "zqxjv", 6, data_dir) == []`.
- AC5: `index_for` builds once per ticker per process (cached) and indexes chunks from every canonical section of every filing of that ticker; a test asserts the chunk count > 100 for AAPL.
- AC6: mypy strict clean; tests named `test_fr009_*`.

## Validation commands (targeted)
- `uv run pytest tests/test_retrieval.py -q`
- `uv run ruff check fathom/retrieval.py tests/test_retrieval.py && uv run mypy fathom`

## Verification checklist (for the Verifier)
- [ ] scope respected
- [ ] no new dependencies (no rank_bm25, no sklearn)
- [ ] deterministic ordering
- [ ] tests named with RTM IDs
- [ ] no filing text logged

## Threat-model boundary touched
none

## Handoff (Implementer fills, ≤10 lines)
Implemented: pure-Python BM25 retrieval — tokenize/STOPWORDS, sentence-boundary chunk_section (hard-cut for over-long sentences, overlap-seeded continuation chunks), BM25Index (idf per LLD formula, score>0 filter, ties by doc_id asc), functools.cache'd index_for, module-level search. No new deps.
Files changed: fathom/retrieval.py (new), tests/test_retrieval.py (new).
Tests run: `uv run pytest tests/test_retrieval.py -q` → 11 passed. `uv run ruff check` and `uv run mypy fathom` → clean.
Deviations: none from spec.
Open questions: none.
Full gate (`uv run python scripts/check.py`): fails only on `ruff format --check` for fathom/guard.py (pre-existing, out of my scope — owned by the concurrent contracts/guard/audit implementer). All checks touching my two files are green.
Budget actual: ~30 tool calls, well under 40k input tokens / 45 min.
