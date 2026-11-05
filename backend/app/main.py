"""FastAPI application: wiring, CORS and consistent error responses.

Run from backend/:  uv run uvicorn app.main:app --reload
Interactive API docs: http://localhost:8000/docs
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.routes import health, passages

logger = logging.getLogger("garuda")

ERROR_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 422: "invalid_request",
               429: "rate_limited", 503: "service_unavailable"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Garuda Purana Q&A API",
        description="Retrieval-augmented answers grounded in 18 verified Garuda Purana Saroddhara passages.",
        version="0.1.0",
    )
    app.state.settings = settings

    # Only the configured frontend origin may call the API from a browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # --- every error has the same shape: {"error": <code>, "message": <text>} -------------
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse({"error": ERROR_CODES.get(exc.status_code, "error"), "message": str(exc.detail)},
                            status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        problems = "; ".join(f"{'.'.join(str(x) for x in e['loc'][1:]) or 'body'}: {e['msg']}" for e in exc.errors())
        return JSONResponse({"error": "invalid_request", "message": problems}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        # Full details go to the server log only; clients never see stack traces.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"error": "internal_error", "message": "Something went wrong. Please try again."},
                            status_code=500)

    app.include_router(health.router)
    app.include_router(passages.router)
    return app


app = create_app()
