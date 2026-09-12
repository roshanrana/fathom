"""Fathom Streamlit advisor page (T-008).

This module computes nothing itself: it calls `fathom.data`, `fathom.quotes`,
`fathom.filings`, `fathom.briefing`, and `fathom.ask` for every value it renders.
`FathomError` is the only exception this page catches (LLD §2.2, §7).
"""

from __future__ import annotations

import hashlib
import json

import streamlit as st

from app.components.rendering import (
    BRIEFING_SECTIONS,
    render_chart,
    render_claims,
    render_filings_table,
    render_header,
    render_quote_metrics,
    render_status_strip,
)
from fathom.ask import ask
from fathom.briefing import brief
from fathom.config import UNIVERSE, Settings
from fathom.contracts import Answer, Briefing
from fathom.data import company
from fathom.errors import FathomError
from fathom.filings import Filing, filings_for
from fathom.live import data_dir_for
from fathom.quotes import quote_card

settings = Settings.from_env()

st.title("Fathom")

briefings: dict[str, Briefing] = st.session_state.setdefault("briefings", {})
answers: dict[str, Answer] = st.session_state.setdefault("answers", {})

_SOURCE_LABELS = ("Fixtures — 20 tickers", "Live — SEC EDGAR + Yahoo")

with st.sidebar:
    source_choice = st.radio(
        "Data source", _SOURCE_LABELS, index=1 if settings.data_source == "live" else 0
    )
    live_mode = source_choice == _SOURCE_LABELS[1]
    if live_mode:
        ticker = st.text_input("Ticker (live)").strip().upper()
        st.button("Fetch")
    else:
        ticker = st.selectbox("Ticker", UNIVERSE)
    generate_clicked = st.button("Generate briefing")
    question = st.text_input("Ask the filings")
    ask_clicked = st.button("Ask")

effective_settings = settings.model_copy(update={"data_source": "live"}) if live_mode else settings

data_dir = None
fetched_at: str | None = None
if live_mode:
    if ticker:
        try:
            data_dir = data_dir_for(ticker, effective_settings)
        except FathomError as exc:
            st.error(f"{exc.code}: {exc.message}")
    if data_dir is not None:
        manifest_path = data_dir / "manifest.json"
        if manifest_path.exists():
            try:
                fetched_at = json.loads(manifest_path.read_text(encoding="utf-8")).get("fetched_at")
            except (OSError, ValueError):
                fetched_at = None
else:
    data_dir = settings.data_dir

if generate_clicked and ticker not in briefings:
    try:
        briefings[ticker] = brief(ticker, effective_settings)
    except FathomError as exc:
        st.error(f"{exc.code}: {exc.message}")

if ask_clicked and question:
    answer_key = f"{ticker}:{hashlib.sha256(question.encode('utf-8')).hexdigest()}"
    if answer_key not in answers:
        try:
            answers[answer_key] = ask(ticker, question, effective_settings)
        except FathomError as exc:
            st.error(f"{exc.code}: {exc.message}")
    st.session_state["last_answer_key"] = answer_key

filings: list[Filing] = []
if data_dir is not None:
    try:
        firm = company(ticker, data_dir)
        quote = quote_card(ticker, data_dir)
        filings = filings_for(ticker, data_dir)
    except FathomError as exc:
        st.error(f"{exc.code}: {exc.message}")
    else:
        render_header(firm)
        render_quote_metrics(quote)
        render_chart(quote)
        render_filings_table(filings)

filings_by_accession = {filing.accession: filing for filing in filings}

briefing = briefings.get(ticker)
if briefing is not None:
    for field_name, title in BRIEFING_SECTIONS:
        st.subheader(title)
        render_claims(getattr(briefing, field_name), filings_by_accession)

st.caption(settings.disclaimer)

last_answer_key = st.session_state.get("last_answer_key")
answer = answers.get(last_answer_key) if last_answer_key else None
if answer is not None and answer.ticker == ticker:
    st.subheader("Answer")
    if answer.not_found:
        st.markdown("No answer found in the filings.")
    else:
        render_claims(answer.claims, filings_by_accession)

render_status_strip(
    settings.llm_provider,
    briefing.model if briefing is not None else None,
    briefing.claims_total if briefing is not None else None,
    briefing.claims_verified if briefing is not None else None,
    source="live" if live_mode else "fixture",
    fetched_at=fetched_at,
)
