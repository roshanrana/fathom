.PHONY: sync check app

sync:
	uv sync --all-extras

check:
	uv run python scripts/check.py

app:
	uv run streamlit run app/main.py

graph:
	graphify update . && graphify cluster-only . --no-viz --no-label
