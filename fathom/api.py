"""FastAPI app exposing the frozen HTTP contracts behind one envelope (LLD §4).

Every response — success or error — is the envelope `{"ok", "data", "error", "meta"}`
(LLD §4). `FathomError` codes map to specific statuses; any other error (an unmapped
`FathomError` code, or a bare `Exception`) becomes a 500 with the generic `INTERNAL` body so
internals never leak to a caller (LLD §7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fathom import __version__
from fathom.ask import ask as ask_flow
from fathom.briefing import brief as brief_flow
from fathom.config import Settings
from fathom.errors import Code, FathomError
from fathom.filings import filings_for
from fathom.quotes import quote_card

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
    """Request body for `POST /api/ask/{ticker}`."""

    question: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the Fathom FastAPI app bound to `settings` (or `Settings.from_env()`)."""
    active_settings = settings if settings is not None else Settings.from_env()
    api = FastAPI(title="Fathom API")

    def _meta(ticker: str | None) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "provider": active_settings.llm_provider,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _envelope(
        ticker: str | None, *, data: Any = None, error: dict[str, str] | None = None
    ) -> dict[str, Any]:
        return {"ok": error is None, "data": data, "error": error, "meta": _meta(ticker)}

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
    async def get_quote(ticker: str) -> JSONResponse:
        card = quote_card(ticker, active_settings.data_dir)
        return JSONResponse(_envelope(card.ticker, data=card.model_dump(mode="json")))

    @api.get("/api/filings/{ticker}")
    async def get_filings(ticker: str) -> JSONResponse:
        rows = filings_for(ticker, active_settings.data_dir)
        ticker_norm = rows[0].ticker if rows else ticker.upper()
        data = [row.model_dump(mode="json") for row in rows]
        return JSONResponse(_envelope(ticker_norm, data=data))

    @api.post("/api/brief/{ticker}")
    async def post_brief(ticker: str) -> JSONResponse:
        result = brief_flow(ticker, active_settings)
        return JSONResponse(_envelope(result.ticker, data=result.model_dump(mode="json")))

    @api.post("/api/ask/{ticker}")
    async def post_ask(ticker: str, body: AskBody) -> JSONResponse:
        result = ask_flow(ticker, body.question, active_settings)
        return JSONResponse(_envelope(result.ticker, data=result.model_dump(mode="json")))

    return api
