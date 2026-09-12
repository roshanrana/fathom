"""Error taxonomy shared across Fathom (LLD §2.2, §7)."""

from __future__ import annotations

from enum import StrEnum


class Code(StrEnum):
    """Stable error codes surfaced to callers and, via the CLI, to users."""

    UNKNOWN_TICKER = "UNKNOWN_TICKER"
    DATA_MISSING = "DATA_MISSING"
    PARSE_FAILED = "PARSE_FAILED"
    PROVIDER_CONFIG = "PROVIDER_CONFIG"
    PROVIDER_HTTP = "PROVIDER_HTTP"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    CONTRACT_INVALID = "CONTRACT_INVALID"
    AUDIT_WRITE = "AUDIT_WRITE"


class FathomError(Exception):
    """The one exception type raised for known failure modes.

    Messages never contain key values, prompt bodies, or filing text longer than 80
    characters (LLD §2.2).
    """

    def __init__(self, code: Code, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, object] = details if details is not None else {}
