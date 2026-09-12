"""Tests for app/main.py (RTM: FR-002, FR-006, FR-012, NFR-011)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.components.rendering import format_market_cap
from fathom.config import DEFAULT_DISCLAIMER
from fathom.guard import GUARD_NOTICE

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = str(REPO_ROOT / "app" / "main.py")
APP_DIR = REPO_ROOT / "app"

_KNOWN_BADGES = ("✅ verified", "⚠️ unverified", "⛔ removed")


def _set_app_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the app at the real fixtures, offline provider, and a tmp-only audit file."""
    monkeypatch.setenv("FATHOM_LLM_PROVIDER", "offline")
    monkeypatch.setenv("FATHOM_DATA_DIR", str(REPO_ROOT / "data"))
    monkeypatch.setenv("FATHOM_AUDIT_PATH", str(tmp_path / "audit" / "fathom-audit.jsonl"))


def _run_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AppTest:
    _set_app_env(monkeypatch, tmp_path)
    return AppTest.from_file(APP_PATH, default_timeout=120).run()


# --- AC1 -----------------------------------------------------------------------------------


def test_fr012_ac1_page_renders_core_elements_without_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)

    assert not at.exception
    assert len(at.selectbox) > 0
    assert len(at.metric) == 6
    assert re.match(r"^[+-]\d+\.\d{2}%$", at.metric[0].delta)
    assert len(at.get("plotly_chart")) == 1
    assert len(at.dataframe) >= 1

    caption_values = [c.value for c in at.caption]
    assert any(DEFAULT_DISCLAIMER in value for value in caption_values)


# --- AC2 -----------------------------------------------------------------------------------


def test_fr012_ac2_generate_briefing_renders_sections_in_order_with_badges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)
    at = at.sidebar.button[0].click().run()  # "Generate briefing"

    assert not at.exception

    expected_titles = [
        "Business snapshot",
        "Latest results",
        "Risks",
        "Liquidity and capital",
        "Notable disclosures",
        "Talking points",
    ]
    subheader_values = [s.value for s in at.subheader]
    positions = [subheader_values.index(title) for title in expected_titles]
    assert positions == sorted(positions), "section headers must appear in LLD order"

    markdown_values = [m.value for m in at.markdown]
    claim_lines = [m for m in markdown_values if m.startswith("- ")]
    badge_lines = [m for m in claim_lines if any(m.rstrip().endswith(b) for b in _KNOWN_BADGES)]
    assert len(badge_lines) >= 10
    for line in claim_lines:
        assert any(line.rstrip().endswith(badge) for badge in _KNOWN_BADGES), (
            f"claim line does not end with a known badge: {line!r}"
        )

    caption_values = [c.value for c in at.caption]
    source_captions = [c for c in caption_values if c.startswith("Source:")]
    assert len(source_captions) >= 10
    for caption in source_captions:
        assert caption != "Source: unknown filing"
        # every real briefing citation names its accession
        assert caption.rsplit("·", 1)[-1].strip()


# --- AC3 -----------------------------------------------------------------------------------


def test_fr012_ac3_ask_renders_verified_claim_and_guard_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)

    at = at.sidebar.text_input[0].input("What are the main risk factors?").run()
    at = at.sidebar.button[1].click().run()  # "Ask"
    assert not at.exception
    markdown_values = [m.value for m in at.markdown]
    assert any(m.rstrip().endswith("✅ verified") for m in markdown_values)

    at = at.sidebar.text_input[0].input("Should I buy?").run()
    at = at.sidebar.button[1].click().run()
    assert not at.exception
    markdown_values = [m.value for m in at.markdown]
    assert any(GUARD_NOTICE in m for m in markdown_values)


# --- AC4 -----------------------------------------------------------------------------------


def test_fr012_ac4_switching_ticker_reuses_cached_briefing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fathom.briefing as briefing_module

    call_count = {"n": 0}
    real_make_provider = briefing_module.make_provider

    def counting_make_provider(settings: object) -> object:
        call_count["n"] += 1
        return real_make_provider(settings)  # type: ignore[arg-type]

    monkeypatch.setattr(briefing_module, "make_provider", counting_make_provider)

    at = _run_app(monkeypatch, tmp_path)
    at = at.sidebar.selectbox[0].select("AAPL").run()
    at = at.sidebar.button[0].click().run()  # "Generate briefing"
    assert not at.exception
    assert call_count["n"] == 1
    aapl_header = at.header[0].value

    at = at.sidebar.selectbox[0].select("MSFT").run()
    assert not at.exception
    assert at.header[0].value != aapl_header

    at = at.sidebar.selectbox[0].select("AAPL").run()
    assert not at.exception
    assert at.header[0].value == aapl_header
    assert call_count["n"] == 1, "provider must not be called again for a cached ticker"


# --- AC5 -----------------------------------------------------------------------------------


def test_fr012_ac5_status_strip_shows_provider_model_and_claim_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)
    caption_values = [c.value for c in at.caption]
    assert any(c.startswith("Provider: offline") for c in caption_values)

    at = at.sidebar.button[0].click().run()  # "Generate briefing"
    caption_values = [c.value for c in at.caption]
    status_lines = [c for c in caption_values if c.startswith("Provider: offline")]
    assert status_lines
    status_line = status_lines[-1]
    assert "Model: extractive-v1" in status_line
    assert "claims" in status_line
    assert "verified" in status_line


# --- AC6 -----------------------------------------------------------------------------------


def test_fr012_ac6_no_computation_leaks_into_app() -> None:
    banned_terms = ("read_parquet", "BM25", "re.compile")
    offenders: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for term in banned_terms:
            if term in text:
                offenders.append(f"{path}: {term}")
    assert offenders == []


# --- NFR-011 ---------------------------------------------------------------------------------


def test_nfr011_metrics_have_text_labels_and_source_caption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)
    assert not at.exception

    metrics = at.metric
    assert len(metrics) == 6
    for metric in metrics:
        assert metric.label  # every metric carries a text label, not just a value

    caption_values = [c.value for c in at.caption]
    source_captions = [c for c in caption_values if c.startswith("Prices:")]
    assert len(source_captions) == 1, "the source caption line is present exactly once (D-011)"
    caption = source_captions[0]
    assert "as of" in caption
    assert "Snapshot:" in caption


def test_nfr011_badge_state_is_carried_by_text_not_colour(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)
    at = at.sidebar.button[0].click().run()  # "Generate briefing"
    assert not at.exception

    markdown_values = [m.value for m in at.markdown]
    claim_lines = [m for m in markdown_values if m.startswith("- ")]
    assert claim_lines

    for line in claim_lines:
        matches = [badge for badge in _KNOWN_BADGES if line.rstrip().endswith(badge)]
        assert len(matches) == 1, f"claim line must carry exactly one known badge: {line!r}"


# --- FR-002: quote-card / market-cap formatting (D-011) --------------------------------------


def test_fr002_format_market_cap_renders_trillions_billions_millions_and_none() -> None:
    assert format_market_cap(4_849_208_188_600) == "$4.85 T"
    assert format_market_cap(412_000_000_000) == "$412 B"
    assert format_market_cap(95_000_000) == "$95 M"
    assert format_market_cap(None) == "—"


def test_fr002_ac6_page_metrics_render_untruncated_with_one_source_caption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    at = _run_app(monkeypatch, tmp_path)
    assert not at.exception

    metrics = at.metric
    assert len(metrics) == 6
    for metric in metrics:
        assert "…" not in metric.value

    caption_values = [c.value for c in at.caption]
    source_captions = [c for c in caption_values if c.startswith("Prices:")]
    assert len(source_captions) == 1
