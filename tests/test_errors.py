"""Tests for fathom.errors (RTM: NFR-005)."""

from __future__ import annotations

from fathom.errors import Code, FathomError


def test_nfr005_fathom_error_stores_code_message_details() -> None:
    error = FathomError(Code.DATA_MISSING, "fixture missing", {"name": "bars"})

    assert error.code == Code.DATA_MISSING
    assert error.message == "fixture missing"
    assert error.details == {"name": "bars"}
    assert str(error) == "fixture missing"


def test_nfr005_fathom_error_defaults_details_to_empty_dict() -> None:
    error = FathomError(Code.UNKNOWN_TICKER, "unknown")

    assert error.details == {}


def test_nfr005_code_enum_members_match_taxonomy() -> None:
    assert {member.value for member in Code} == {
        "UNKNOWN_TICKER",
        "DATA_MISSING",
        "PARSE_FAILED",
        "PROVIDER_CONFIG",
        "PROVIDER_HTTP",
        "PROVIDER_TIMEOUT",
        "CONTRACT_INVALID",
        "AUDIT_WRITE",
        "SOURCE_CONFIG",
        "SOURCE_HTTP",
        "SOURCE_EMPTY",
    }
