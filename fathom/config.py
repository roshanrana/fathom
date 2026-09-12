"""Runtime configuration (LLD §2.1)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from fathom.errors import Code, FathomError

UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "AMZN",
    "BAC",
    "CAT",
    "CVX",
    "GOOGL",
    "GS",
    "JNJ",
    "JPM",
    "KO",
    "MCD",
    "META",
    "MSFT",
    "NVDA",
    "PFE",
    "PG",
    "TSLA",
    "UNH",
    "WMT",
    "XOM",
)

DEFAULT_DISCLAIMER = (
    "Fathom summarises public SEC filings and market data for advisor preparation. "
    "It is not investment advice, does not make recommendations, and may contain errors; "
    "verify against the cited filing before relying on any statement."
)

_TRUE_VALUES = {"1", "true", "yes"}
_LLM_PROVIDERS = ("offline", "portkey", "anthropic")
_DATA_SOURCES = ("fixture", "live")
_PRICE_SOURCES = ("yahoo", "stooq")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in _TRUE_VALUES


class Settings(BaseModel):
    """Application configuration, built from environment variables."""

    llm_provider: Literal["offline", "portkey", "anthropic"] = "offline"
    portkey_base_url: str = "https://portkeygateway.perficient.com/v1"
    portkey_api_key: str | None = None
    portkey_model: str = "@aws-bedrock-use2/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    data_dir: Path = Path("data")
    audit_path: Path = Path("audit/fathom-audit.jsonl")
    audit_bodies: bool = False
    http_timeout_s: float = 90.0
    max_tokens_brief: int = 4000
    max_tokens_ask: int = 1500
    disclaimer: str = DEFAULT_DISCLAIMER
    data_source: Literal["fixture", "live"] = "fixture"
    sec_contact: str | None = None
    live_cache_dir: Path = Path(".cache/live")
    live_ttl_hours: float = 6.0
    price_source: Literal["yahoo", "stooq"] = "yahoo"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from a mapping of environment variables.

        Reads `os.environ` when `env` is None; tests pass a plain dict instead.
        """
        source: Mapping[str, str] = env if env is not None else os.environ

        llm_provider_raw = source.get("FATHOM_LLM_PROVIDER", "offline")
        if llm_provider_raw not in _LLM_PROVIDERS:
            raise FathomError(
                Code.PROVIDER_CONFIG,
                f"FATHOM_LLM_PROVIDER must be one of {_LLM_PROVIDERS}",
                {"var": "FATHOM_LLM_PROVIDER"},
            )
        llm_provider: Literal["offline", "portkey", "anthropic"] = llm_provider_raw  # type: ignore[assignment]

        audit_bodies_raw = source.get("FATHOM_AUDIT_BODIES")
        audit_bodies = _parse_bool(audit_bodies_raw) if audit_bodies_raw is not None else False

        data_source_raw = source.get("FATHOM_DATA_SOURCE", "fixture")
        if data_source_raw not in _DATA_SOURCES:
            raise FathomError(
                Code.PROVIDER_CONFIG,
                f"FATHOM_DATA_SOURCE must be one of {_DATA_SOURCES}",
                {"var": "FATHOM_DATA_SOURCE"},
            )
        data_source: Literal["fixture", "live"] = data_source_raw  # type: ignore[assignment]

        price_source_raw = source.get("FATHOM_PRICE_SOURCE", "yahoo")
        if price_source_raw not in _PRICE_SOURCES:
            raise FathomError(
                Code.PROVIDER_CONFIG,
                f"FATHOM_PRICE_SOURCE must be one of {_PRICE_SOURCES}",
                {"var": "FATHOM_PRICE_SOURCE"},
            )
        price_source: Literal["yahoo", "stooq"] = price_source_raw  # type: ignore[assignment]

        return cls(
            llm_provider=llm_provider,
            portkey_base_url=source.get(
                "PORTKEY_BASE_URL", "https://portkeygateway.perficient.com/v1"
            ),
            portkey_api_key=source.get("PORTKEY_API_KEY"),
            portkey_model=source.get(
                "PORTKEY_MODEL",
                "@aws-bedrock-use2/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
            anthropic_api_key=source.get("ANTHROPIC_API_KEY"),
            anthropic_model=source.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
            data_dir=Path(source.get("FATHOM_DATA_DIR", "data")),
            audit_path=Path(source.get("FATHOM_AUDIT_PATH", "audit/fathom-audit.jsonl")),
            audit_bodies=audit_bodies,
            http_timeout_s=float(source.get("FATHOM_HTTP_TIMEOUT_S", "90.0")),
            disclaimer=source.get("FATHOM_DISCLAIMER", DEFAULT_DISCLAIMER),
            data_source=data_source,
            sec_contact=source.get("FATHOM_SEC_CONTACT"),
            live_cache_dir=Path(source.get("FATHOM_LIVE_CACHE_DIR", ".cache/live")),
            live_ttl_hours=float(source.get("FATHOM_LIVE_TTL_HOURS", "6.0")),
            price_source=price_source,
        )
