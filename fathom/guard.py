"""Advice guard and citation verifier (LLD §2.8, patterns frozen at §6.4)."""

from __future__ import annotations

import re

from fathom.contracts import Claim

GUARD_NOTICE = "[removed: recommendation-style language is not permitted in Fathom output]"

# Frozen, case-insensitive (LLD §6.4). Do not reorder, add, or remove entries.
ADVICE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(we|i|you|investors?|clients?|one)\s+(should|ought to|must|need to)\s+"
        r"(buy|sell|hold|invest|avoid|add|trim|accumulate|short)\b",
        r"\b(strong\s+)?(buy|sell|hold)\s+(rating|recommendation|signal|call|idea)\b",
        r"\brecommend(s|ed|ation|ations)?\b[^.]{0,60}\b(buy|sell|hold|purchas\w*|invest\w*|position)\b",
        r"\bprice\s+target\b",
        r"\b(over|under)weight\b",
        r"\b(under|over)valued\b",
        r"\b(good|great|excellent|bad|poor|terrible)\s+"
        r"(investment|buy|entry point|time to (buy|sell))\b",
        r"\b(buy|sell)\s+(the|this|these)\s+(stock|shares?|dip|name)\b",
        r"\bshould\s+(i|you|we|they|clients?|investors?)\s+(buy|sell|hold|invest|short)\b",
        r"\bis\s+(it|this|\w+)\s+a\s+(good|bad|great|safe)\s+(investment|buy|stock|bet)\b",
        r"\b(will|is|does)\s+(the\s+)?(stock|share price|price|it)\s+"
        r"(go|going|likely to go|rise|fall|rally|crash)\b",
        r"\b(predict|forecast)\b[^.]{0,40}\b(price|stock)\b",
        r"\b(bullish|bearish)\b",
        r"\btop pick\b",
    )
)

_CURLY_QUOTES = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)
_WHITESPACE = re.compile(r"\s+")


def is_advice(text: str) -> bool:
    """True when `text` matches any of the frozen advice patterns."""
    return any(pattern.search(text) is not None for pattern in ADVICE_PATTERNS)


def normalise(text: str) -> str:
    """Casefold, map curly quotes to straight ones, collapse whitespace, strip."""
    folded = text.casefold().translate(_CURLY_QUOTES)
    return _WHITESPACE.sub(" ", folded).strip()


def verify_claim(claim_quote: str, section_text: str) -> bool:
    """A quote verifies when it has 6-60 words and appears verbatim (normalised) in the section."""
    word_count = len(claim_quote.split())
    if not (6 <= word_count <= 60):
        return False
    return normalise(claim_quote) in normalise(section_text)


def scrub_claims(claims: list[Claim]) -> tuple[list[Claim], int]:
    """Replace advice-flagged claims' text with `GUARD_NOTICE`.

    Returns a new list (the input is never mutated) plus the number of claims flagged.
    """
    scrubbed: list[Claim] = []
    hits = 0
    for claim in claims:
        if is_advice(claim.text):
            hits += 1
            scrubbed.append(
                claim.model_copy(update={"text": GUARD_NOTICE, "guarded": True, "verified": False})
            )
        else:
            scrubbed.append(claim)
    return scrubbed, hits
