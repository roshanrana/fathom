# Fathom

Fathom summarises public SEC filings and market data so a wealth-management advisor can prepare
for a client conversation about a public company. It is not investment advice, does not make
recommendations, and every claim it produces is grounded in a verbatim quote from a cited filing.

## Run it

```bash
uv sync --all-extras
uv run streamlit run app/main.py
uv run python scripts/check.py
```
