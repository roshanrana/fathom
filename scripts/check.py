"""The one gate: `uv run python scripts/check.py` (NFR-003).

Runs every STEPS entry in order from the repo root, printing each step as it starts, and
exits non-zero at the first failure. Prints "all checks passed" only if every step succeeds.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEPS: list[tuple[str, list[str]]] = [
    ("ruff check", ["ruff", "check", "."]),
    ("ruff format --check", ["ruff", "format", "--check", "."]),
    ("mypy fathom", ["mypy", "fathom"]),
    ("mypy fathom --platform linux", ["mypy", "fathom", "--platform", "linux"]),
    (
        "pytest",
        [
            "pytest",
            "--cov=fathom",
            "--cov-report=term-missing",
            "--cov-fail-under=80",
        ],
    ),
    ("secrets scan", [sys.executable, "scripts/secrets_scan.py"]),
]


def main() -> int:
    for name, argv in STEPS:
        print(f"==> {name}")
        result = subprocess.run(argv, cwd=ROOT)
        if result.returncode != 0:
            print(f"FAILED: {name} (exit {result.returncode})")
            return result.returncode
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
