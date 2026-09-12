"""Tests for fathom.retrieval (RTM: FR-009)."""

from __future__ import annotations

from pathlib import Path

from fathom.filings import Section
from fathom.retrieval import (
    BM25Index,
    Chunk,
    chunk_section,
    index_for,
    search,
    tokenize,
)


def _section(text: str, accession: str = "acc-1", section_id: str = "10-K:1A") -> Section:
    return Section(
        accession=accession,
        section_id=section_id,
        title="Risk Factors",
        text=text,
        char_start=0,
        char_end=len(text),
    )


def test_fr009_tokenize_matches_ac1_example() -> None:
    """AC1: tokenize drops stopwords and short tokens produced by the \\w+ split."""
    assert tokenize("The Company's risk factors, and its 10-K") == ["risk", "factors", "10"]


def test_fr009_chunk_section_boundaries_ordinals_and_overlap() -> None:
    """AC2: chunks stay <= size, share a sentence with their neighbor, ordinals 0..n-1."""
    sentences = [
        f"This is sentence number {i:02d} with some padding words for length." for i in range(30)
    ]
    text = " ".join(sentences)
    section = _section(text, accession="acc-2", section_id="10-K:7")

    chunks = chunk_section(section, size=1200, overlap=200)

    assert len(chunks) > 1
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    for ordinal, chunk in enumerate(chunks):
        assert chunk.doc_id == f"acc-2#10-K:7#{ordinal}"
        assert chunk.accession == "acc-2"
        assert chunk.section_id == "10-K:7"
        assert len(chunk.text) <= 1200

    for first, second in zip(chunks, chunks[1:], strict=False):
        shared = [s for s in sentences if s in first.text and s in second.text]
        assert shared, "consecutive chunks must share at least one sentence"


def test_fr009_chunk_section_hard_cuts_an_over_long_sentence() -> None:
    """A single sentence longer than `size` becomes its own (over-limit) chunk."""
    huge_sentence = ("filler word " * 150) + "end."
    assert len(huge_sentence) > 1200
    text = (
        "Short intro sentence for context today. "
        + huge_sentence
        + " Short outro sentence follows nicely today."
    )
    section = _section(text, accession="acc-3", section_id="10-K:1")

    chunks = chunk_section(section, size=1200, overlap=200)

    huge_chunks = [c for c in chunks if huge_sentence in c.text]
    assert len(huge_chunks) == 1
    assert huge_chunks[0].text == huge_sentence
    assert len(huge_chunks[0].text) > 1200


def test_fr009_chunk_section_empty_text_yields_no_chunks() -> None:
    """An empty/whitespace-only section produces zero chunks."""
    section = _section("   ", accession="acc-4", section_id="10-K:1")
    assert chunk_section(section) == []


def test_fr009_bm25_ranks_unique_term_first_and_excludes_zero_scores() -> None:
    """AC3: a term unique to doc B ranks B first with score > 0, others excluded."""
    chunk_a = Chunk(
        doc_id="doc_a",
        accession="acc",
        section_id="10-K:1A",
        ordinal=0,
        text="the market grew steadily during the quarter for most participants",
    )
    chunk_b = Chunk(
        doc_id="doc_b",
        accession="acc",
        section_id="10-K:1A",
        ordinal=0,
        text="unique widget factory production increased sharply this year",
    )
    chunk_c = Chunk(
        doc_id="doc_c",
        accession="acc",
        section_id="10-K:1A",
        ordinal=0,
        text="general commentary about the economy and broad market trends",
    )
    index = BM25Index([chunk_a, chunk_b, chunk_c])

    hits = index.search("widget", k=6)

    assert len(hits) == 1
    assert hits[0].chunk.doc_id == "doc_b"
    assert hits[0].score > 0


def test_fr009_bm25_search_ties_break_by_doc_id_ascending() -> None:
    """Equal-scoring hits are ordered by doc_id ascending."""
    chunk_z = Chunk(
        doc_id="doc_z",
        accession="acc",
        section_id="10-K:1A",
        ordinal=0,
        text="alpha beta gamma delta epsilon",
    )
    chunk_a = Chunk(
        doc_id="doc_a",
        accession="acc",
        section_id="10-K:1A",
        ordinal=0,
        text="alpha beta gamma delta epsilon",
    )
    index = BM25Index([chunk_z, chunk_a])

    hits = index.search("alpha beta", k=6)

    assert [h.chunk.doc_id for h in hits] == ["doc_a", "doc_z"]
    assert hits[0].score == hits[1].score


def test_fr009_bm25_search_respects_k_and_returns_empty_for_no_terms() -> None:
    """search(k=...) truncates results; a query with no surviving tokens returns []."""
    chunks = [
        Chunk(
            doc_id=f"doc_{i}",
            accession="acc",
            section_id="10-K:1A",
            ordinal=0,
            text=f"widget factory number {i} produces widgets efficiently",
        )
        for i in range(5)
    ]
    index = BM25Index(chunks)

    hits = index.search("widget", k=2)
    assert len(hits) == 2

    assert index.search("the and of") == []


def test_fr009_search_aapl_risk_factors_top_section(data_dir: Path) -> None:
    """AC4: searching "risk factors" surfaces a Risk Factors section on top."""
    hits = search("AAPL", "risk factors", 6, data_dir)
    assert hits
    assert hits[0].chunk.section_id in ("10-K:1A", "10-Q:II.1A")


def test_fr009_search_aapl_liquidity_top_section(data_dir: Path) -> None:
    """AC4: searching for liquidity/capital-resources language surfaces MD&A on top."""
    hits = search("AAPL", "liquidity and capital resources", 6, data_dir)
    assert hits
    assert hits[0].chunk.section_id in ("10-K:7", "10-Q:I.2")


def test_fr009_search_aapl_nonsense_query_returns_empty(data_dir: Path) -> None:
    """AC4: a query with no matching terms anywhere in the corpus returns []."""
    assert search("AAPL", "zqxjv", 6, data_dir) == []


def test_fr009_index_for_is_cached_and_covers_all_sections(data_dir: Path) -> None:
    """AC5: index_for is cached per (ticker, data_dir) and indexes > 100 chunks for AAPL."""
    first = index_for("AAPL", data_dir)
    second = index_for("AAPL", data_dir)

    assert first is second
    assert len(first.chunks) > 100
