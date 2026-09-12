"""Regex secrets scan (LLD §7 PROVIDER_CONFIG / NFR-009). Stdlib only, offline.

Fails if any tracked, non-binary file contains what looks like a live Portkey or Anthropic
key. Usage: `python scripts/secrets_scan.py [root]` — exits 1 and prints each hit, or exits 0
and prints "no secrets found".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "node_modules",
    "data",
}
EXCLUDED_PARTS = {
    ("docs", "evidence"),
}
EXCLUDED_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".docx",
    ".zip",
    ".lock",
    ".parquet",
}

PATTERNS = [
    re.compile(r"PORTKEY_API_KEY\s*=\s*\S{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    re.compile(r"x-portkey-api-key[\"']?\s*[:=]\s*[\"'][^\"']{12,}"),
]


def _is_excluded(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    for excluded in EXCLUDED_PARTS:
        n = len(excluded)
        if any(parts[i : i + n] == excluded for i in range(len(parts) - n + 1)):
            return True
    return False


def _iter_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded(path, root):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def scan(root: Path) -> list[str]:
    """Return a list of "path: pattern" hit descriptions; empty means clean."""
    hits: list[str] = []
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                hits.append(f"{path.relative_to(root)}: matches {pattern.pattern!r}")
    return hits


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]).resolve() if args else ROOT
    hits = scan(root)
    if hits:
        print("secrets_scan: potential secret material found:")
        for hit in hits:
            print(f"  {hit}")
        return 1
    print("no secrets found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
