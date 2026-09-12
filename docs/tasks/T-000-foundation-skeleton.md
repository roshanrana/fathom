---
id: T-000
title: Foundation and walking skeleton
milestone: M0
risk: low
tier: T2
complexity: high
reasoning: on
budget: {input_tokens: 80000, tool_calls: 80, wall_clock_min: 120}
depends_on: []
rtm: [NFR-003, NFR-005, NFR-009, FR-001]
status: todo
---
# T-000 — Foundation and walking skeleton

## Goal
A fresh clone runs `uv sync --all-extras` then `uv run python scripts/check.py` green, and
`uv run streamlit run app/main.py` shows a ticker selector, the company name, and the last
close from the fixtures. CI runs the same gate. No briefing logic yet.

## Spec references
`03-lld.md §1` (repository layout, dependencies, mypy/ruff settings), `§2.1` (`Settings`,
`UNIVERSE`, `DEFAULT_DISCLAIMER`), `§2.2` (`Code`, `FathomError`), `§2.3` (`load_frame`,
`require_ticker`, `company`, `Company`, fixture schemas). Key excerpt:
```python
UNIVERSE: tuple[str, ...] = ("AAPL","AMZN","BAC","CAT","CVX","GOOGL","GS","JNJ","JPM","KO","MCD","META","MSFT","NVDA","PFE","PG","TSLA","UNH","WMT","XOM")
class Settings(BaseModel):  # fields and env names exactly as LLD §2.1; from_env(env: Mapping|None)
class Code(StrEnum): UNKNOWN_TICKER, DATA_MISSING, PARSE_FAILED, PROVIDER_CONFIG, PROVIDER_HTTP, PROVIDER_TIMEOUT, CONTRACT_INVALID, AUDIT_WRITE
class FathomError(Exception): code, message, details
@functools.cache
def load_frame(name: Literal["filings","bars","quotes","companies"], data_dir: Path) -> pd.DataFrame  # missing file → DATA_MISSING
def require_ticker(ticker: str) -> str   # upper-case; UNKNOWN_TICKER message lists UNIVERSE
def company(ticker: str, data_dir: Path) -> Company   # from companies.parquet: ticker, long_name→name, full_exchange_name→exchange, sector, industry, website
```
Gate steps (mirror Lodestar's `scripts/check.py`): ruff check, ruff format --check, mypy fathom,
mypy fathom --platform linux, pytest --cov=fathom --cov-fail-under=80, secrets scan. Bench and
card steps are added in T-010.

## Scope (files this task may touch)
- pyproject.toml, uv.lock, Makefile, README.md (stub: name, one-paragraph purpose, three run commands), LICENSE (MIT, Roshan Rana 2026), .python-version
- fathom/__init__.py, fathom/py.typed, fathom/config.py, fathom/errors.py, fathom/data.py
- app/main.py (skeleton: selectbox over UNIVERSE, company name, last close from bars via load_frame, disclaimer at the bottom)
- scripts/check.py, scripts/secrets_scan.py (patterns: `PORTKEY_API_KEY\s*=\s*\S{16,}`, `sk-ant-[A-Za-z0-9_-]{10,}`, `x-portkey-api-key["']?\s*[:=]\s*["'][^"']{12,}`; excludes .git .venv caches data/ docs/evidence)
- .github/workflows/check.yml, .streamlit/config.toml (copy Lodestar's theme block)
- tests/__init__.py, tests/conftest.py (fixture `data_dir` → repo `data/`), tests/test_config.py, tests/test_errors.py, tests/test_data.py, tests/test_app_skeleton.py

## Acceptance criteria
- AC1: `uv run python scripts/check.py` exits 0 on Windows; the workflow file runs the same command on ubuntu-latest with `astral-sh/setup-uv@v5`, `uv python install 3.12`, `uv sync --all-extras`.
- AC2: `Settings.from_env({})` yields the LLD defaults; `from_env({"FATHOM_LLM_PROVIDER": "portkey", "PORTKEY_API_KEY": "k"})` sets both; `from_env({"FATHOM_LLM_PROVIDER": "nope"})` raises `FathomError` with `Code.PROVIDER_CONFIG`; `FATHOM_AUDIT_BODIES` accepts "1"/"true"/"yes" (case-insensitive) as True.
- AC3: `require_ticker("aapl") == "AAPL"`; `require_ticker("ZZZZ")` raises `UNKNOWN_TICKER` and the message contains every ticker in `UNIVERSE`.
- AC4: `company("MSFT", data_dir).name == "Microsoft Corporation"` and `.exchange == "NasdaqGS"`; `load_frame("bars", data_dir)` has columns exactly `symbol, date, open, high, low, close, volume`; a test asserts the sum of `data/*.parquet` sizes ≤ 20 MB (NFR-009).
- AC5: `streamlit.testing.v1.AppTest.from_file("app/main.py").run()` has no exception, contains a selectbox, and the page text contains "Apple Inc." for the default selection (first of UNIVERSE) and the disclaimer text.
- AC6: `pyproject.toml` declares exactly the LLD §1 dependency set (runtime + dev + optional groups `mcp`, `screenshots`), `[project.scripts] fathom = "fathom.cli:app"` may be declared now but `fathom/cli.py` is NOT created in this task (T-009 owns it) — so omit the script entry until T-009. mypy strict passes with `plugins = ["pydantic.mypy"]` and `ignore_missing_imports` limited to `streamlit.*`, `plotly.*`.
- AC7: coverage of `fathom/` ≥ 80 % from the tests in scope; no `print` in package code; `README.md` exists.

## Validation commands (targeted)
- `uv sync --all-extras`
- `uv run pytest tests -q`
- `uv run python scripts/check.py`

## Verification checklist (for the Verifier)
- [ ] scope respected (no fathom/quotes.py, filings.py, cli.py etc.)
- [ ] error taxonomy used (Code enum only; no bare exceptions raised for known failures)
- [ ] no sensitive fields logged; secrets scan runs in check.py
- [ ] tests named with RTM IDs (test_fr001_…, test_nfr009_…)
- [ ] no new dependencies beyond LLD §1
- [ ] CI workflow present and equivalent to the local gate

## Threat-model boundary touched
B3 (fixtures on disk: DATA_MISSING path); B5 (build pipeline: gate, secrets scan).

## Handoff (Implementer fills, ≤10 lines)
Implemented: pyproject/uv.lock, .python-version, LICENSE, README, Makefile, fathom/{__init__,py.typed,errors,config,data}.py, app/main.py skeleton, scripts/{check,secrets_scan}.py, .github/workflows/check.yml, .streamlit/config.toml, tests/{__init__,conftest,test_config,test_errors,test_data,test_app_skeleton}.py.
Files changed: all of the above (new files), all within Scope.
Tests run: `uv run pytest tests -q` → 25 passed; `uv run python scripts/check.py` → all checks passed (ruff check, ruff format --check, mypy fathom x2, pytest --cov=fathom --cov-fail-under=80 → 98.89%, secrets scan) all green.
Deviations from pack: none — pyarrow-stubs installed without conflict, so it was kept (not dropped). `[project.scripts]` omitted per AC6 (T-009 owns cli.py).
Open questions: none.
Budget actual: ~45k input tokens, ~30 tool calls, well under the 120 min / 80 tool-call budget.
