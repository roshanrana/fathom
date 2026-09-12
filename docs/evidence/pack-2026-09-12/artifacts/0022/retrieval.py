"""Pure-Python BM25 retrieval over chunked canonical sections (LLD §2.6)."""

from __future__ import annotations

import functools
import math
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from fathom.filings import CANONICAL_SECTIONS, Section, filings_for, sections_for

STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "at",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "we",
        "our",
        "us",
        "company",
        "inc",
        "corp",
        "may",
        "will",
        "which",
        "has",
        "have",
        "had",
        "not",
        "than",
        "also",
        "other",
        "such",
        "any",
        "all",
        "per",
    }
)

_WORD = re.compile(r"\w+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class Chunk(BaseModel):
    """One retrievable slice of a canonical section (LLD §2.6)."""

    doc_id: str
    accession: str
    section_id: str
    text: str
    ordinal: int


class Hit(BaseModel):
    """One scored search result."""

    chunk: Chunk
    score: float


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens of length >= 2, minus `STOPWORDS`."""
    return [
        word
        for word in (match.group(0) for match in _WORD.finditer(text.lower()))
        if len(word) >= 2 and word not in STOPWORDS
    ]


def _joined_len(sentences: list[str]) -> int:
    """Length of `sentences` if joined with single spaces."""
    return len(" ".join(sentences))


def _trailing_overlap(sentences: list[str], overlap: int) -> list[str]:
    """Trailing sentences of `sentences` whose joined length fits within `overlap`."""
    carry: list[str] = []
    for sentence in reversed(sentences):
        candidate = [sentence, *carry]
        if _joined_len(candidate) <= overlap:
            carry = candidate
        else:
            break
    return carry


def chunk_section(section: Section, size: int = 1200, overlap: int = 200) -> list[Chunk]:
    """Split `section.text` into chunks at sentence boundaries.

    Sentences accumulate into a chunk until the next sentence would push it past
    `size`; the next chunk is seeded with the trailing sentences of the previous
    one that fit within `overlap` characters. A single sentence longer than `size`
    becomes its own chunk (hard cut).
    """
    sentences = [s for s in _SENTENCE_SPLIT.split(section.text.strip()) if s]
    if not sentences:
        return []

    groups: list[list[str]] = []
    current: list[str] = []

    for sentence in sentences:
        if len(sentence) > size:
            if current:
                groups.append(current)
                current = []
            groups.append([sentence])
            continue

        if not current:
            current = [sentence]
            continue

        candidate_len = _joined_len(current) + 1 + len(sentence)
        if candidate_len > size:
            groups.append(current)
            current = [*_trailing_overlap(current, overlap), sentence]
        else:
            current.append(sentence)

    if current:
        groups.append(current)

    chunks = []
    for ordinal, group in enumerate(groups):
        chunks.append(
            Chunk(
                doc_id=f"{section.accession}#{section.section_id}#{ordinal}",
                accession=section.accession,
                section_id=section.section_id,
                text=" ".join(group),
                ordinal=ordinal,
            )
        )
    return chunks


class BM25Index:
    """A pure-Python BM25 index over a fixed list of chunks."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b

        # D-008: index tokens are section-title tokens + chunk-text tokens (explainable,
        # deterministic; `Chunk.text` itself is unchanged).
        doc_tokens = [
            tokenize(CANONICAL_SECTIONS.get(chunk.section_id, "")) + tokenize(chunk.text)
            for chunk in chunks
        ]
        self._doc_len = [len(tokens) for tokens in doc_tokens]
        self._n_docs = len(chunks)
        self._avgdl = (sum(self._doc_len) / self._n_docs) if self._n_docs else 0.0
        self._term_freqs: list[Counter[str]] = [Counter(tokens) for tokens in doc_tokens]

        df: dict[str, int] = {}
        for term_freq in self._term_freqs:
            for term in term_freq:
                df[term] = df.get(term, 0) + 1
        self._df = df

    def _idf(self, term: str) -> float:
        n = self._df.get(term, 0)
        return math.log((self._n_docs - n + 0.5) / (n + 0.5) + 1)

    def search(self, query: str, k: int = 6) -> list[Hit]:
        """Score every chunk against `query`; return up to `k` hits with score > 0."""
        terms = set(tokenize(query))
        if not terms or self._n_docs == 0:
            return []

        scored: list[tuple[float, int]] = []
        for index in range(self._n_docs):
            term_freq = self._term_freqs[index]
            doc_len = self._doc_len[index]
            score = 0.0
            for term in terms:
                freq = term_freq.get(term, 0)
                if freq == 0:
                    continue
                if self._avgdl:
                    denom = freq + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl)
                else:
                    denom = freq + self.k1
                score += self._idf(term) * (freq * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((score, index))

        scored.sort(key=lambda pair: (-pair[0], self.chunks[pair[1]].doc_id))
        return [Hit(chunk=self.chunks[i], score=s) for s, i in scored[:k]]


@functools.cache
def index_for(ticker: str, data_dir: Path) -> BM25Index:
    """Build (once per ticker per process) the BM25 index over all of a ticker's filings."""
    chunks: list[Chunk] = []
    for filing in filings_for(ticker, data_dir):
        for section in sections_for(filing.accession, data_dir):
            chunks.extend(chunk_section(section))
    return BM25Index(chunks)


def search(ticker: str, query: str, k: int, data_dir: Path) -> list[Hit]:
    """Search a ticker's indexed filings for `query`, returning up to `k` hits."""
    return index_for(ticker, data_dir).search(query, k)
