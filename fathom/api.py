"""FastAPI app exposing the frozen HTTP contracts behind one envelope (LLD §4).

Every response — success or error — is the envelope `{"ok", "data", "error", "meta"}`
(LLD §4). `FathomError` codes map to specific statuses; any other error (an unmapped
`FathomError` code, or a bare `Exception`) becomes a 500 with the generic `INTERNAL` body so
internals never leak to a caller (LLD §7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from fathom import __version__
from fathom.ask import ask as ask_flow
from fathom.briefing import brief as brief_flow
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.filings import filings_for
from fathom.live import data_dir_for
from fathom.live.build import materialize
from fathom.live.http import LiveHttp
from fathom.quotes import quote_card

SourceParam = Annotated[Literal["fixture", "live"] | None, Query()]

_STATUS_BY_CODE: dict[Code, int] = {
    Code.UNKNOWN_TICKER: 404,
    Code.PROVIDER_CONFIG: 503,
    Code.PROVIDER_HTTP: 502,
    Code.PROVIDER_TIMEOUT: 502,
    Code.CONTRACT_INVALID: 502,
}
_INTERNAL_ERROR: dict[str, str] = {"code": "INTERNAL", "message": "internal error"}
_VALIDATION_ERROR: dict[str, str] = {"code": "VALIDATION", "message": "invalid request"}


class AskBody(BaseModel):
    """Request body for `POST /api/ask/{ticker}` (D-008: bounded to 2 000 characters)."""

    question: str = Field(min_length=1, max_length=2000)


def create_app(settings: Settings | None = None, *, http: LiveHttp | None = None) -> FastAPI:
    """Build the Fathom FastAPI app bound to `settings` (or `Settings.from_env()`).

    `http` is a test seam: when given, a `?source=live` request routes through it (a
    `MockTransport`-backed `LiveHttp`) instead of building a real one from `settings`.
    """
    active_settings = settings if settings is not None else Settings.from_env()
    api = FastAPI(title="Fathom API")

    def _effective_settings(source: Literal["fixture", "live"] | None) -> Settings:
        if source is None:
            return active_settings
        return active_settings.model_copy(update={"data_source": source})

    def _resolve_data_dir(ticker: str, effective_settings: Settings) -> Path:
        if http is not None and effective_settings.data_source == "live":
            manifest = materialize(ticker, effective_settings, http=http)
            return Path(manifest.data_dir)
        return data_dir_for(ticker, effective_settings)

    def _meta(ticker: str | None, source: str | None = None) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "provider": active_settings.llm_provider,
            "source": source if source is not None else active_settings.data_source,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _envelope(
        ticker: str | None,
        *,
        data: Any = None,
        error: dict[str, str] | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        return {"ok": error is None, "data": data, "error": error, "meta": _meta(ticker, source)}

    def _path_ticker(request: Request) -> str | None:
        ticker = request.path_params.get("ticker")
        return ticker if isinstance(ticker, str) else None

    @api.exception_handler(FathomError)
    async def _fathom_error_handler(request: Request, exc: FathomError) -> JSONResponse:
        ticker = _path_ticker(request)
        status_code = _STATUS_BY_CODE.get(exc.code)
        if status_code is None:
            body = _envelope(ticker, error=_INTERNAL_ERROR)
            return JSONResponse(status_code=500, content=body)
        error = {"code": exc.code.value, "message": exc.message}
        return JSONResponse(status_code=status_code, content=_envelope(ticker, error=error))

    @api.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422, content=_envelope(_path_ticker(request), error=_VALIDATION_ERROR)
        )

    @api.exception_handler(Exception)
    async def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500, content=_envelope(_path_ticker(request), error=_INTERNAL_ERROR)
        )

    @api.get("/healthz")
    async def healthz() -> JSONResponse:
        data = {"status": "ok", "provider": active_settings.llm_provider, "version": __version__}
        return JSONResponse(_envelope(None, data=data))

    @api.get("/api/quote/{ticker}")
    async def get_quote(ticker: str, source: SourceParam = None) -> JSONResponse:
        effective_settings = _effective_settings(source)
        card = quote_card(ticker, _resolve_data_dir(ticker, effective_settings))
        return JSONResponse(
            _envelope(
                card.ticker,
                data=card.model_dump(mode="json"),
                source=effective_settings.data_source,
            )
        )

    @api.get("/api/filings/{ticker}")
    async def get_filings(ticker: str, source: SourceParam = None) -> JSONResponse:
        effective_settings = _effective_settings(source)
        rows = filings_for(ticker, _resolve_data_dir(ticker, effective_settings))
        ticker_norm = rows[0].ticker if rows else ticker.upper()
        data = [row.model_dump(mode="json") for row in rows]
        return JSONResponse(
            _envelope(ticker_norm, data=data, source=effective_settings.data_source)
        )

    @api.post("/api/brief/{ticker}")
    async def post_brief(ticker: str, source: SourceParam = None) -> JSONResponse:
        effective_settings = _effective_settings(source)
        result = brief_flow(ticker, effective_settings)
        return JSONResponse(
            _envelope(
                result.ticker,
                data=result.model_dump(mode="json"),
                source=effective_settings.data_source,
            )
        )

    @api.post("/api/ask/{ticker}")
    async def post_ask(ticker: str, body: AskBody, source: SourceParam = None) -> JSONResponse:
        effective_settings = _effective_settings(source)
        result = ask_flow(ticker, body.question, effective_settings)
        return JSONResponse(
            _envelope(
                result.ticker,
                data=result.model_dump(mode="json"),
                source=effective_settings.data_source,
            )
        )

    return api
