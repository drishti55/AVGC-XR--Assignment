"""FastAPI application: wiring, CORS and consistent error responses.

Run from backend/:  uv run uvicorn app.main:app --reload
Interactive API docs: http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db
from app.config import Settings, get_settings
from app.routes import ask, health, passages
from app.services.answer import AnswerService
from app.services.llm.gemini import GeminiProvider
from app.services.llm.ollama import OllamaProvider
from app.services.llm.router import LLMRouter
from app.services.retrieval import Retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("garuda")

ERROR_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 422: "invalid_request",
               429: "rate_limited", 503: "service_unavailable"}


def build_answer_service(settings: Settings) -> AnswerService | None:
    """Load the embedding model and search index once, at startup (takes a few seconds)."""
    if not settings.db_file.exists():
        logger.error("Database %s not found. Run: uv run python scripts/ingest.py", settings.db_file)
        return None
    from app.services.embeddings import get_embedder   # heavy import (torch) only when needed

    embedder = get_embedder(settings.embedding_model)
    with db.connection(settings.db_file) as conn:
        retriever = Retriever.from_db(conn, embedder.embed_query, settings.semantic_threshold,
                                      settings.bm25_threshold, settings.top_k, settings.strong_semantic_threshold)
    # Fallback chain: Gemini Flash -> Gemini Flash-Lite (often less loaded) -> local Ollama (offline).
    providers = [GeminiProvider(settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds,
                                settings.gemini_thinking_level)]
    if settings.gemini_fallback_model:
        providers.append(GeminiProvider(settings.gemini_api_key, settings.gemini_fallback_model,
                                        settings.gemini_timeout_seconds, settings.gemini_thinking_level,
                                        name="gemini-lite"))
    providers.append(OllamaProvider(settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds))
    llm = LLMRouter(providers)
    logger.info("Answer service ready: %d passages indexed", len(retriever.ids))
    return AnswerService(retriever, llm)


def create_app(settings: Settings | None = None, answer_service: AnswerService | None = None) -> FastAPI:
    """answer_service can be injected (tests use a fake); otherwise it is built at startup."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.answer_service is None:
            app.state.answer_service = build_answer_service(settings)
        yield

    app = FastAPI(
        title="Garuda Purana Q&A API",
        description="Retrieval-augmented answers grounded in 18 verified Garuda Purana Saroddhara passages.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.answer_service = answer_service

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
    app.include_router(ask.router)
    return app


app = create_app()
