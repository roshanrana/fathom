"""Capture PNGs of the Fathom Streamlit page for docs/assets (T-011 helper, not in the gate).

Prerequisites (one-time):
    uv sync --all-extras
    uv run playwright install chromium
Then, from the repository root:
    uv run python scripts/screenshots.py

This script starts `streamlit run app/main.py --server.port 8765 --server.headless true` as a
subprocess itself (FATHOM_LLM_PROVIDER=offline, FATHOM_AUDIT_PATH pointing at a temp file so the
demo audit log is untouched), waits for the port to open, drives the page with Playwright
Chromium at a 1440px-wide viewport, clicks "Generate briefing" and asks one question before the
briefing/Q&A captures, and writes five PNGs to docs/assets/. The Streamlit subprocess is killed
on exit, including on failure.

Streamlit renders the whole page inside a container that scrolls on its own; a plain full_page
screenshot only captures the visible viewport, not the scrolled content (the same lesson as
Lodestar's screenshots.py). Before every capture this script grows the browser viewport to the
`[data-testid="stMain"]` container's scrollHeight so nothing is clipped, then takes a `clip`ped
screenshot of just the section named by the output file.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets"

HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}"

VIEWPORT_WIDTH = 1440
STARTUP_TIMEOUT_S = 60.0
NAV_TIMEOUT_MS = 60_000
SETTLE_MS = 800
ASK_QUESTION = "What are the main risk factors?"
CLIP_PAD = 12


def _wait_for_port(host: str, port: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"streamlit did not open {host}:{port} within {timeout_s}s") from last_error


def _start_streamlit(audit_path: Path) -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    env["FATHOM_LLM_PROVIDER"] = "offline"
    env["FATHOM_AUDIT_PATH"] = str(audit_path)
    env["PYTHONIOENCODING"] = "utf-8"
    args = [
        "uv",
        "run",
        "streamlit",
        "run",
        "app/main.py",
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
    ]
    return subprocess.Popen(
        args, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def _stop_process(proc: subprocess.Popen[bytes] | None) -> None:
    """Kill the streamlit subprocess (and its child process on Windows), best-effort."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            proc.terminate()
            proc.wait(timeout=10)
    except Exception:  # pragma: no cover - best-effort teardown
        pass


def _grow_to_full_height(page: Any) -> None:
    """Resize the viewport to the page's full content height (see module docstring)."""
    height = page.evaluate(
        "() => { const m = document.querySelector('[data-testid=\"stMain\"]');"
        " const a = m ? m.scrollHeight : 0;"
        " return Math.max(a, document.documentElement.scrollHeight); }"
    )
    page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": min(int(height) + 40, 12000)})
    page.wait_for_timeout(SETTLE_MS)


def _page_bottom(page: Any) -> float:
    height = page.evaluate(
        "() => { const m = document.querySelector('[data-testid=\"stMain\"]');"
        " const a = m ? m.scrollHeight : 0;"
        " return Math.max(a, document.documentElement.scrollHeight); }"
    )
    return float(height)


def _clip(top_y: float, bottom_y: float) -> dict[str, float]:
    y0 = max(top_y - CLIP_PAD, 0)
    y1 = bottom_y + CLIP_PAD
    return {"x": 0, "y": y0, "width": VIEWPORT_WIDTH, "height": max(y1 - y0, 1)}


def _capture(page: Any, name: str, clip: dict[str, float]) -> None:
    out = OUT / name
    page.screenshot(path=str(out), clip=clip)
    size_kb = out.stat().st_size // 1024
    print(f"wrote {out.relative_to(ROOT)} ({size_kb} KB)")


def _run(page: Any) -> None:
    page.goto(BASE_URL, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
    page.wait_for_selector("text=Generate briefing", timeout=NAV_TIMEOUT_MS)
    page.wait_for_function(
        "() => document.querySelectorAll('[data-testid=\"stMetric\"]').length >= 5",
        timeout=NAV_TIMEOUT_MS,
    )
    page.wait_for_selector(".js-plotly-plot", timeout=NAV_TIMEOUT_MS)
    page.wait_for_selector('[data-testid="stDataFrame"]', timeout=NAV_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)
    _grow_to_full_height(page)

    _capture(page, "00-full-page.png", _clip(0, _page_bottom(page)))

    header_box = page.get_by_role("heading", level=2).first.bounding_box()
    chart_box = page.locator(".js-plotly-plot").first.bounding_box()
    table_box = page.locator('[data-testid="stDataFrame"]').first.bounding_box()
    assert header_box is not None
    assert chart_box is not None
    assert table_box is not None

    _capture(page, "01-header-quote.png", _clip(header_box["y"], chart_box["y"]))
    _capture(
        page,
        "02-chart-filings.png",
        _clip(chart_box["y"], table_box["y"] + table_box["height"]),
    )

    page.get_by_role("button", name="Generate briefing").click()
    page.wait_for_selector("text=Talking points", timeout=NAV_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)
    _grow_to_full_height(page)
    briefing_box = page.get_by_text("Business snapshot", exact=True).first.bounding_box()
    assert briefing_box is not None
    _capture(page, "03-briefing.png", _clip(briefing_box["y"], _page_bottom(page)))

    page.get_by_label("Ask the filings").fill(ASK_QUESTION)
    page.get_by_role("button", name="Ask", exact=True).click()
    page.wait_for_selector("text=Answer", timeout=NAV_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)
    _grow_to_full_height(page)
    answer_box = page.get_by_text("Answer", exact=True).first.bounding_box()
    assert answer_box is not None
    _capture(page, "04-ask.png", _clip(answer_box["y"], _page_bottom(page)))


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - tooling guard
        print("playwright missing: uv sync --all-extras && uv run playwright install chromium")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[bytes] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="fathom-screenshots-") as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            proc = _start_streamlit(audit_path)
            _wait_for_port(HOST, PORT, STARTUP_TIMEOUT_S)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                context = browser.new_context(
                    viewport={"width": VIEWPORT_WIDTH, "height": 900},
                    device_scale_factor=1,
                    color_scheme="light",
                )
                page = context.new_page()
                _run(page)
                browser.close()
    finally:
        _stop_process(proc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
