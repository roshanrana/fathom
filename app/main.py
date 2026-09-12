"""Fathom Streamlit page — walking skeleton (T-008 replaces this)."""

from __future__ import annotations

import streamlit as st

from fathom.config import UNIVERSE, Settings
from fathom.data import company, load_frame

settings = Settings.from_env()

st.title("Fathom")

ticker = st.selectbox("Ticker", UNIVERSE)

if ticker:
    firm = company(ticker, settings.data_dir)
    st.header(firm.name)

    bars = load_frame("bars", settings.data_dir)
    symbol_bars = bars[bars["symbol"] == ticker]
    if not symbol_bars.empty:
        last_row = symbol_bars.loc[symbol_bars["date"].idxmax()]
        st.metric("Last close", f"{last_row['close']:.2f}")

st.caption(settings.disclaimer)
