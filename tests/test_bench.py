"""Tests for fathom.bench and metrics/render.py.

RTM: FR-015 (bench + card), NFR-001 (offline latency), NFR-004 (determinism), NFR-007
(citation grounding), NFR-008 (guard escapes).
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import BaseModel, ConfigDict, Field

from fathom.bench import ADVERSARIAL_PHRASES, BENIGN_PHRASES, GOLDEN_QUERIES, run_bench
from fathom.config import UNIVERSE
from fathom.guard import is_advice

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Pydantic model for the frozen headline shape (LLD §5) ----------------------------------


class _ParserStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenk_with_1a_and_7: int
    tenk_total: int
    tenq_with_i2: int
    tenq_total: int
    coverage: float


class _RetrievalStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    golden_queries: int
    hits: int
    total: int
    hit_rate: float


class _GuardStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adversarial: int
    escapes: int
    benign: int
    false_positives: int


class _BriefingOfflineStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tickers: int
    claims_total: int
    claims_verified: int
    verified_share: float


class _InjectionStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool


class _Headline(BaseModel):
    """The frozen `metrics/headline.json` shape, minus the three timing-only fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(alias="schema")
    universe: int
    filings: int
    parser: _ParserStats
    retrieval: _RetrievalStats
    guard: _GuardStats
    briefing_offline: _BriefingOfflineStats
    injection: _InjectionStats


class _Timing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    briefing_offline: dict[str, int]
    timing_ms: int


# --- Shared fixture: run the bench once per test module (offline loop is not free) ----------


@pytest.fixture(scope="module")
def bench_result(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[str, object], dict[str, object]]:
    out = tmp_path_factory.mktemp("bench") / "headline.json"
    run_bench(out=out)
    headline = json.loads(out.read_text(encoding="utf-8"))
    timing = json.loads((out.parent / "timing.json").read_text(encoding="utf-8"))
    return headline, timing


# --- FR-015: shape, gate wiring, golden queries, injection -----------------------------------


def test_fr015_headline_matches_frozen_shape(
    bench_result: tuple[dict[str, object], dict[str, object]],
) -> None:
    headline, timing = bench_result

    validated = _Headline.model_validate(headline)
    _Timing.model_validate(timing)

    assert validated.schema_name == "fathom-headline/1"
    assert validated.universe == len(UNIVERSE)
    assert validated.filings == validated.parser.tenk_total + validated.parser.tenq_total
    assert validated.retrieval.golden_queries == len(GOLDEN_QUERIES)
    assert validated.retrieval.total == len(GOLDEN_QUERIES) * len(UNIVERSE)
    assert 0.0 <= validated.retrieval.hit_rate <= 1.0
    assert "latency_ms_median" in timing["briefing_offline"]  # type: ignore[operator]


def test_fr015_parser_coverage_is_full_over_the_universe(
    bench_result: tuple[dict[str, object], dict[str, object]],
) -> None:
    headline, _ = bench_result
    parser = headline["parser"]
    assert isinstance(parser, dict)
    assert parser["coverage"] == 1.0
    assert parser["tenk_with_1a_and_7"] == parser["tenk_total"] == 20
    assert parser["tenq_with_i2"] == parser["tenq_total"]


def test_fr015_injection_check_reports_guarded_and_unverified(
    bench_result: tuple[dict[str, object], dict[str, object]],
) -> None:
    headline, _ = bench_result
    assert headline["injection"] == {"passed": True}


def test_fr015_bench_step_wired_into_gate_in_order() -> None:
    check_source = (REPO_ROOT / "scripts" / "check.py").read_text(encoding="utf-8")
    bench_pos = check_source.index('"bench"')
    drift_pos = check_source.index('"bench drift"')
    card_pos = check_source.index('"card drift"')
    secrets_pos = check_source.index('"secrets scan"')
    assert secrets_pos < bench_pos < drift_pos < card_pos
    assert '"-m", "fathom.bench"' in check_source
    assert '"git", "diff", "--exit-code", "--", "metrics/headline.json"' in check_source
    assert '"metrics/render.py", "--check"' in check_source


# --- NFR-008: guard escapes / false positives -------------------------------------------------


def test_nfr008_bench_phrase_lists_meet_minimum_counts() -> None:
    assert len(ADVERSARIAL_PHRASES) >= 25
    assert len(BENIGN_PHRASES) >= 12


def test_nfr008_bench_phrase_lists_agree_with_is_advice() -> None:
    assert all(is_advice(phrase) for phrase in ADVERSARIAL_PHRASES)
    assert not any(is_advice(phrase) for phrase in BENIGN_PHRASES)


def test_nfr008_guard_escapes_and_false_positives_are_zero(
    bench_result: tuple[dict[str, object], dict[str, object]],
) -> None:
    headline, _ = bench_result
    guard = headline["guard"]
    assert isinstance(guard, dict)
    assert guard["adversarial"] >= 25
    assert guard["escapes"] == 0
    assert guard["benign"] >= 12
    assert guard["false_positives"] == 0


# --- NFR-007: citation grounding (offline verified share) --------------------------------------


def test_nfr007_offline_briefing_verified_share_meets_target(
    bench_result: tuple[dict[str, object], dict[str, object]],
) -> None:
    headline, _ = bench_result
    briefing_offline = headline["briefing_offline"]
    assert isinstance(briefing_offline, dict)
    assert briefing_offline["tickers"] == len(UNIVERSE)
    assert briefing_offline["verified_share"] >= 0.9
    assert briefing_offline["claims_total"] > 0
    assert briefing_offline["claims_verified"] == briefing_offline["claims_total"]


# --- NFR-001: offline latency ------------------------------------------------------------------


def test_nfr001_offline_latency_median_under_budget(
    bench_result: tuple[dict[str, object], dict[str, object]],
) -> None:
    _, timing = bench_result
    briefing_offline_timing = timing["briefing_offline"]
    assert isinstance(briefing_offline_timing, dict)
    assert briefing_offline_timing["latency_ms_median"] <= 5000


def test_nfr001_run_bench_completes_within_wall_clock_budget(tmp_path: Path) -> None:
    out = tmp_path / "headline.json"
    start = time.monotonic()
    run_bench(out=out)
    elapsed_s = time.monotonic() - start
    assert elapsed_s < 180


# --- NFR-004: determinism -----------------------------------------------------------------------


def test_nfr004_two_runs_are_byte_identical_except_timing(tmp_path: Path) -> None:
    out1 = tmp_path / "run1" / "headline.json"
    out2 = tmp_path / "run2" / "headline.json"

    run_bench(out=out1)
    run_bench(out=out2)

    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")

    timing1 = json.loads((out1.parent / "timing.json").read_text(encoding="utf-8"))
    timing2 = json.loads((out2.parent / "timing.json").read_text(encoding="utf-8"))
    assert set(timing1) == set(timing2) == {"generated_at", "briefing_offline", "timing_ms"}


# --- metrics/render.py: KPI statuses and drift check (stdlib-only, loaded by file path) --------


def _load_render_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "metrics_render", REPO_ROOT / "metrics" / "render.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_headline(hit_rate: float) -> dict[str, object]:
    return {
        "schema": "fathom-headline/1",
        "universe": 20,
        "filings": 97,
        "parser": {
            "tenk_with_1a_and_7": 20,
            "tenk_total": 20,
            "tenq_with_i2": 77,
            "tenq_total": 77,
            "coverage": 1.0,
        },
        "retrieval": {
            "golden_queries": 7,
            "hits": int(hit_rate * 140),
            "total": 140,
            "hit_rate": hit_rate,
        },
        "guard": {"adversarial": 33, "escapes": 0, "benign": 12, "false_positives": 0},
        "briefing_offline": {
            "tickers": 20,
            "claims_total": 400,
            "claims_verified": 400,
            "verified_share": 1.0,
        },
        "injection": {"passed": True},
    }


_FAKE_TIMING: dict[str, object] = {
    "generated_at": "2026-01-01T00:00:00+00:00",
    "briefing_offline": {"latency_ms_median": 800},
    "timing_ms": 12345,
}


def test_fr015_render_marks_retrieval_hit_rate_warn_below_target() -> None:
    render = _load_render_module()
    card = render.build_card(_fake_headline(0.75), _FAKE_TIMING)
    kpi = next(k for k in card["kpis"] if k["key"] == "retrieval_hit_rate")
    assert kpi["status"] == "warn"


def test_fr015_render_marks_retrieval_hit_rate_pass_at_target() -> None:
    render = _load_render_module()
    card = render.build_card(_fake_headline(0.95), _FAKE_TIMING)
    kpi = next(k for k in card["kpis"] if k["key"] == "retrieval_hit_rate")
    assert kpi["status"] == "pass"


def test_fr015_render_marks_guard_false_positives_always_info() -> None:
    render = _load_render_module()
    card = render.build_card(_fake_headline(1.0), _FAKE_TIMING)
    kpi = next(k for k in card["kpis"] if k["key"] == "guard_false_positives")
    assert kpi["status"] == "info"


def test_fr015_render_check_detects_drift_after_a_kpi_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    render = _load_render_module()

    headline_path = tmp_path / "headline.json"
    timing_path = tmp_path / "timing.json"
    card_json_path = tmp_path / "card.json"
    card_md_path = tmp_path / "card.md"

    headline_path.write_text(json.dumps(_fake_headline(1.0)), encoding="utf-8")
    timing_path.write_text(json.dumps(_FAKE_TIMING), encoding="utf-8")

    monkeypatch.setattr(render, "HEADLINE", headline_path)
    monkeypatch.setattr(render, "TIMING", timing_path)
    monkeypatch.setattr(render, "CARD_JSON", card_json_path)
    monkeypatch.setattr(render, "CARD_MD", card_md_path)

    assert render.main([]) == 0
    assert card_json_path.exists()
    assert card_md_path.exists()
    assert render.main(["--check"]) == 0

    card_json_path.write_text("{}", encoding="utf-8")
    assert render.main(["--check"]) == 1


def test_nfr004_render_check_ignores_timing_jitter_across_bench_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second bench run's fresh timing.json (new generated_at/latency) is not drift."""
    render = _load_render_module()

    headline_path = tmp_path / "headline.json"
    timing_path = tmp_path / "timing.json"
    card_json_path = tmp_path / "card.json"
    card_md_path = tmp_path / "card.md"

    headline_path.write_text(json.dumps(_fake_headline(1.0)), encoding="utf-8")
    timing_path.write_text(json.dumps(_FAKE_TIMING), encoding="utf-8")

    monkeypatch.setattr(render, "HEADLINE", headline_path)
    monkeypatch.setattr(render, "TIMING", timing_path)
    monkeypatch.setattr(render, "CARD_JSON", card_json_path)
    monkeypatch.setattr(render, "CARD_MD", card_md_path)

    assert render.main([]) == 0

    # Simulate a fresh `python -m fathom.bench` run: a new timing.json with a different
    # timestamp and (possibly) a different latency reading, same underlying headline content.
    timing_path.write_text(
        json.dumps(
            {
                "generated_at": "2027-06-15T09:30:00+00:00",
                "briefing_offline": {"latency_ms_median": 3},
                "timing_ms": 9999,
            }
        ),
        encoding="utf-8",
    )

    assert render.main(["--check"]) == 0
