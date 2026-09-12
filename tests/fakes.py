"""Shared test doubles for fathom's provider protocol."""

from __future__ import annotations

from fathom.providers import ProviderResult


class ScriptedProvider:
    """A `Provider` that replays pre-scripted completions in order, recording each call."""

    name = "scripted"
    model = "scripted-v1"

    def __init__(self, texts: list[str]) -> None:
        self._texts: list[str] = list(texts)
        self.calls: list[tuple[str, str, int]] = []

    def complete_json(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        """Record the call and return the next queued text; raises once exhausted."""
        self.calls.append((system, user, max_tokens))
        if not self._texts:
            raise RuntimeError("ScriptedProvider exhausted: no more queued texts")
        text = self._texts.pop(0)
        return ProviderResult(text=text, input_tokens=None, output_tokens=None, latency_ms=0)
