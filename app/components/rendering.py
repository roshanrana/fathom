"""Rendering helpers for the Fathom advisor page (T-008).

Every function here only renders values already computed by `fathom.*`; nothing here
reads fixtures, calls a provider, or does any parsing/retrieval of its own.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.components.badges import badge_for
from fathom.contracts import Claim
from fathom.data import Company
from fathom.filings import CANONICAL_SECTIONS, Filing
from fathom.quotes import QuoteCard

# LLD-ordered (section attribute name, section title) pairs for a Briefing.
BRIEFING_SECTIONS: tuple[tuple[str, str], ...] = (
    ("business_snapshot", "Business snapshot"),
    ("latest_results", "Latest results"),
    ("risks", "Risks"),
    ("liquidity_capital", "Liquidity and capital"),
    ("notable_disclosures", "Notable disclosures"),
    ("talking_points", "Talking points"),
)

_UNKNOWN_FILING = "Source: unknown filing"

_TRILLION = 1_000_000_000_000
_BILLION = 1_000_000_000
_MILLION = 1_000_000


def render_header(firm: Company) -> None:
    """Company name, exchange, sector/industry, and a website link."""
    st.header(firm.name)
    st.caption(f"{firm.exchange} · {firm.sector} · {firm.industry}")
    st.markdown(f"[{firm.website}]({firm.website})")


def format_market_cap(value: float | None) -> str:
    """Market cap as "$4.85 T" / "$412 B" / "$95 M" (D-011); "—" when unknown."""
    if value is None:
        return "—"
    magnitude = abs(value)
    if magnitude >= _TRILLION:
        return f"${value / _TRILLION:.2f} T"
    if magnitude >= _BILLION:
        return f"${value / _BILLION:.0f} B"
    if magnitude >= _MILLION:
        return f"${value / _MILLION:.0f} M"
    return f"${value:,.0f}"


def _metrics_source_caption(quote: QuoteCard) -> str:
    """The single 'Prices: ... · Snapshot: ...' caption placed under the metric row (D-011)."""
    prices = f"Prices: {quote.source} as of {quote.as_of}"
    if quote.snapshot_source is None or quote.snapshot_as_of is None:
        snapshot = "Snapshot: —"
    else:
        snapshot_time = f"{quote.snapshot_as_of:%Y-%m-%d %H:%M}"
        snapshot = f"Snapshot: {quote.snapshot_source} as of {snapshot_time} UTC"
    return f"{prices} · {snapshot}"


def render_quote_metrics(quote: QuoteCard) -> None:
    """The six `st.metric` cards required by FR-012, plus one shared source caption (D-011)."""
    columns = st.columns(6)

    with columns[0]:
        st.metric(
            "Last close",
            f"{quote.last_close:.2f}",
            f"{quote.change_abs:+.2f} ({quote.change_pct:+.2f}%)",
        )

    with columns[1]:
        st.metric("52-wk low", f"{quote.week52_low:.2f}")

    with columns[2]:
        st.metric("52-wk high", f"{quote.week52_high:.2f}")

    with columns[3]:
        st.metric("Market cap", format_market_cap(quote.market_cap))

    with columns[4]:
        value = f"{quote.pe:.2f}" if quote.pe is not None else "—"
        st.metric("P/E", value)

    with columns[5]:
        value = f"{quote.dividend_yield:.2f}%" if quote.dividend_yield is not None else "—"
        st.metric("Dividend yield", value)

    st.caption(_metrics_source_caption(quote))


def render_chart(quote: QuoteCard) -> None:
    """A one-year plotly line chart of `quote.series`."""
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[point.date for point in quote.series],
                y=[point.close for point in quote.series],
                mode="lines",
                name=quote.ticker,
            )
        ]
    )
    figure.update_layout(xaxis_title="Date", yaxis_title="Close", margin={"t": 20})
    st.plotly_chart(figure, use_container_width=True)


def render_filings_table(filings: list[Filing]) -> None:
    """The filings table (form, filing date, period end, accession, EDGAR link)."""
    rows = [
        {
            "Form": filing.form,
            "Filing date": filing.filing_date.isoformat(),
            "Period end": filing.period_end.isoformat() if filing.period_end else "-",
            "Accession": filing.accession,
            "EDGAR link": filing.edgar_url,
        }
        for filing in filings
    ]
    st.dataframe(
        rows,
        hide_index=True,
        column_config={"EDGAR link": st.column_config.LinkColumn("EDGAR link")},
    )


def source_caption(claim: Claim, filings_by_accession: dict[str, Filing]) -> str:
    """The 'Source: <form> <filing_date> · <section title> · <accession>' caption."""
    filing = filings_by_accession.get(claim.source.accession)
    if filing is None:
        return _UNKNOWN_FILING
    title = CANONICAL_SECTIONS.get(claim.source.section_id, claim.source.section_id)
    return f"Source: {filing.form} {filing.filing_date} · {title} · {claim.source.accession}"


def render_claim(claim: Claim, filings_by_accession: dict[str, Filing]) -> None:
    """One claim bullet with its badge, followed by its source caption."""
    st.markdown(f"- {claim.text}  {badge_for(claim)}")
    st.caption(source_caption(claim, filings_by_accession))


def render_claims(claims: list[Claim], filings_by_accession: dict[str, Filing]) -> None:
    """Render each of `claims` in order."""
    for claim in claims:
        render_claim(claim, filings_by_accession)


def render_status_strip(
    llm_provider: str, model: str | None, claims_total: int | None, claims_verified: int | None
) -> None:
    """The status strip: provider, model, and (once a briefing exists) claim counts."""
    if model is None:
        st.caption(f"Provider: {llm_provider} · Model: -")
        return
    st.caption(
        f"Provider: {llm_provider} · Model: {model} · "
        f"claims {claims_total} · verified {claims_verified}"
    )
