"""Claim badge text (NFR-011: colour is never the only carrier of verified state)."""

from __future__ import annotations

from fathom.contracts import Claim

BADGE_VERIFIED = "✅ verified"
BADGE_UNVERIFIED = "⚠️ unverified"
BADGE_REMOVED = "⛔ removed"

KNOWN_BADGES: tuple[str, ...] = (BADGE_VERIFIED, BADGE_UNVERIFIED, BADGE_REMOVED)


def badge_for(claim: Claim) -> str:
    """The one badge string describing `claim`'s guard/verification state."""
    if claim.guarded:
        return BADGE_REMOVED
    if claim.verified:
        return BADGE_VERIFIED
    return BADGE_UNVERIFIED
