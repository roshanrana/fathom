.PHONY: sync check app

sync:
	uv sync --all-extras

check:
	uv run python scripts/check.py

app:
	uv run streamlit run app/main.py
