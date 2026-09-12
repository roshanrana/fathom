"""Pure-rendering helpers for the Fathom Streamlit page (T-008).

Nothing in this package computes data: every function here takes an already-built
`fathom.*` object (Company, QuoteCard, Filing, Briefing, Answer, Claim, ...) and renders
it with Streamlit/Plotly calls only.
"""

from __future__ import annotations
