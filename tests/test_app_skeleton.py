"""Tests for app/main.py (RTM: FR-001)."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from fathom.config import DEFAULT_DISCLAIMER

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = str(REPO_ROOT / "app" / "main.py")


def test_fr001_app_shows_ticker_selector_company_and_disclaimer() -> None:
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()

    assert not at.exception
    assert len(at.selectbox) > 0

    page_text = " ".join(
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [t.value for t in at.title]
        + [h.value for h in at.header]
    )
    assert "Apple Inc." in page_text
    assert DEFAULT_DISCLAIMER in page_text
