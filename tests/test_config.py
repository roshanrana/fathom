"""Tests for fathom.config (RTM: FR-001, NFR-003, NFR-005)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from fathom.config import DEFAULT_DISCLAIMER, Settings
from fathom.errors import Code, FathomError

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_fr001_from_env_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.llm_provider == "offline"
    assert settings.portkey_base_url == "https://portkeygateway.perficient.com/v1"
    assert settings.portkey_api_key is None
    assert settings.anthropic_api_key is None
    assert settings.data_dir == Path("data")
    assert settings.audit_path == Path("audit/fathom-audit.jsonl")
    assert settings.audit_bodies is False
    assert settings.disclaimer == DEFAULT_DISCLAIMER


def test_fr021_from_env_live_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.data_source == "fixture"
    assert settings.sec_contact is None
    assert settings.live_cache_dir == Path(".cache/live")
    assert settings.live_ttl_hours == 6.0
    assert settings.price_source == "yahoo"


def test_fr025_from_env_live_source_requires_no_immediate_error() -> None:
    # Settings.from_env itself never requires FATHOM_SEC_CONTACT; that check belongs to
    # SecClient.from_settings (AC1) so fixture-mode callers are unaffected.
    settings = Settings.from_env({"FATHOM_DATA_SOURCE": "live"})

    assert settings.data_source == "live"
    assert settings.sec_contact is None


def test_fr021_from_env_sets_live_fields() -> None:
    settings = Settings.from_env(
        {
            "FATHOM_DATA_SOURCE": "live",
            "FATHOM_SEC_CONTACT": "ops@example.com",
            "FATHOM_LIVE_CACHE_DIR": "/tmp/live-cache",
            "FATHOM_LIVE_TTL_HOURS": "12.5",
            "FATHOM_PRICE_SOURCE": "stooq",
        }
    )

    assert settings.data_source == "live"
    assert settings.sec_contact == "ops@example.com"
    assert settings.live_cache_dir == Path("/tmp/live-cache")
    assert settings.live_ttl_hours == 12.5
    assert settings.price_source == "stooq"


def test_nfr005_from_env_invalid_data_source_raises_provider_config() -> None:
    with pytest.raises(FathomError) as excinfo:
        Settings.from_env({"FATHOM_DATA_SOURCE": "nope"})

    assert excinfo.value.code == Code.PROVIDER_CONFIG
    assert excinfo.value.details["var"] == "FATHOM_DATA_SOURCE"


def test_nfr005_from_env_invalid_price_source_raises_provider_config() -> None:
    with pytest.raises(FathomError) as excinfo:
        Settings.from_env({"FATHOM_PRICE_SOURCE": "nope"})

    assert excinfo.value.code == Code.PROVIDER_CONFIG
    assert excinfo.value.details["var"] == "FATHOM_PRICE_SOURCE"


def test_fr001_from_env_sets_provider_and_portkey_key() -> None:
    settings = Settings.from_env({"FATHOM_LLM_PROVIDER": "portkey", "PORTKEY_API_KEY": "k"})

    assert settings.llm_provider == "portkey"
    assert settings.portkey_api_key == "k"


def test_nfr005_from_env_invalid_provider_raises_fathom_error() -> None:
    with pytest.raises(FathomError) as excinfo:
        Settings.from_env({"FATHOM_LLM_PROVIDER": "nope"})

    assert excinfo.value.code == Code.PROVIDER_CONFIG


@pytest.mark.parametrize("raw", ["1", "true", "yes", "TRUE", "Yes", "True"])
def test_nfr005_from_env_audit_bodies_accepts_truthy_strings(raw: str) -> None:
    settings = Settings.from_env({"FATHOM_AUDIT_BODIES": raw})

    assert settings.audit_bodies is True


@pytest.mark.parametrize("raw", ["0", "false", "no", ""])
def test_nfr005_from_env_audit_bodies_rejects_other_strings(raw: str) -> None:
    settings = Settings.from_env({"FATHOM_AUDIT_BODIES": raw})

    assert settings.audit_bodies is False


def test_nfr003_pyproject_declares_lld_dependency_set() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]

    dep_names = {dep.split(">=")[0].split("[")[0].strip() for dep in project["dependencies"]}
    assert dep_names == {
        "pydantic",
        "typer",
        "streamlit",
        "plotly",
        "httpx",
        "fastapi",
        "uvicorn",
        "pyarrow",
        "pandas",
    }

    groups = data["dependency-groups"]
    assert "dev" in groups

    optional_deps = project["optional-dependencies"]
    assert "mcp" in optional_deps
    assert "screenshots" in optional_deps
    assert project["scripts"] == {"fathom": "fathom.cli:app"}


def test_nfr003_no_print_statements_in_package() -> None:
    package_dir = REPO_ROOT / "fathom"
    offenders = [
        path for path in package_dir.rglob("*.py") if "print(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
