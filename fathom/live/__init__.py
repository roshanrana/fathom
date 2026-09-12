"""Live (non-fixture) data sources (05-m4-live-data.md §3).

`data_dir_for` is the one call site the rest of the app should use to resolve where a
ticker's tables live: fixture mode returns `settings.data_dir` unchanged; live mode
materializes (or serves from a fresh cache) `.cache/live/<TICKER>/` via
`fathom.live.build.materialize`.
"""

from __future__ import annotations

from pathlib import Path

from fathom.config import Settings
from fathom.live.build import materialize

__all__ = ["data_dir_for", "is_live", "materialize"]


def is_live(settings: Settings) -> bool:
    """Whether `settings` selects the live data source."""
    return settings.data_source == "live"


def data_dir_for(ticker: str, settings: Settings) -> Path:
    """The directory holding `ticker`'s tables: `settings.data_dir` (fixture) or the live cache."""
    if not is_live(settings):
        return settings.data_dir
    manifest = materialize(ticker, settings)
    return Path(manifest.data_dir)
