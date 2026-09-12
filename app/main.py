"""Fathom Streamlit advisor page (T-008).

This module computes nothing itself: it calls `fathom.data`, `fathom.quotes`,
`fathom.filings`, `fathom.briefing`, and `fathom.ask` for every value it renders.
`FathomError` is the only exception this page catches (LLD §2.2, §7).
"""

from __future__ import annotations

import hashlib

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
from fathom.quotes import quote_card

settings = Settings.from_env()

st.title("Fathom")

briefings: dict[str, Briefing] = st.session_state.setdefault("briefings", {})
answers: dict[str, Answer] = st.session_state.setdefault("answers", {})

with st.sidebar:
    ticker = st.selectbox("Ticker", UNIVERSE)
    generate_clicked = st.button("Generate briefing")
    question = st.text_input("Ask the filings")
    ask_clicked = st.button("Ask")

if generate_clicked and ticker not in briefings:
    try:
        briefings[ticker] = brief(ticker, settings)
    except FathomError as exc:
        st.error(f"{exc.code}: {exc.message}")

if ask_clicked and question:
    answer_key = f"{ticker}:{hashlib.sha256(question.encode('utf-8')).hexdigest()}"
    if answer_key not in answers:
        try:
            answers[answer_key] = ask(ticker, question, settings)
        except FathomError as exc:
            st.error(f"{exc.code}: {exc.message}")
    st.session_state["last_answer_key"] = answer_key

filings: list[Filing] = []
try:
    firm = company(ticker, settings.data_dir)
    quote = quote_card(ticker, settings.data_dir)
    filings = filings_for(ticker, settings.data_dir)
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
)
