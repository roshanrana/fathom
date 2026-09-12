"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def data_dir() -> Path:
    """The repo's real fixture directory (data/*.parquet)."""
    return REPO_ROOT / "data"
