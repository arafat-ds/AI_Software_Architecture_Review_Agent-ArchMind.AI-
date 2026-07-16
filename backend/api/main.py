"""FastAPI application factory for ArchMind AI.

Usage:
  Development:  uvicorn api.main:create_app --factory --reload
  Production:   uvicorn api.main:create_app --factory --workers 1

No module-level `app` singleton — using the factory pattern keeps this module
safely importable without environment variables, which is required for tests.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.dependencies import get_executor, get_orchestrator, get_supabase_client, shutdown_executor
from api.routers import health
from api.security import require_auth
from api.routers import jobs as jobs_router
from api.routers import reports as reports_router
from config.settings import get_settings
from infrastructure.gemini_client import GeminiClient
from infrastructure.qdrant_client import QdrantClient
from shared.exceptions.rag_exceptions import QdrantConnectionError
from shared.logging.logger import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: configure logging, recover orphaned jobs, run connectivity probes, clean up on shutdown."""
    configure_logging()

    # Default probe state — updated by each probe block below
    app.state.supabase_status = "unknown"
    app.state.gemini_status = "unknown"
    app.state.qdrant_status = "unknown"

    # Supabase: orphan recovery doubles as the connectivity probe
    try:
        t0 = time.monotonic()
        recovered = get_supabase_client().recover_orphaned_jobs()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Startup orphan recovery complete",
            extra={"recovered": recovered, "elapsed_ms": elapsed_ms},
        )
        if recovered:
            logger.warning(
                "Orphaned jobs recovered on startup",
                extra={"count": recovered},
            )
        app.state.supabase_status = "ok"
    except Exception as exc:
        logger.critical(
            "Startup orphan recovery failed — server continuing",
            extra={"error": str(exc)},
        )
        app.state.supabase_status = "failed"

    # Gemini connectivity probe — non-fatal
    try:
        _settings = get_settings()
        _gemini_probe = GeminiClient(
            api_key=_settings.gemini_api_key,
            generation_model=_settings.gemini_model,
            embedding_model=_settings.gemini_embedding_model,
            temperature=0.0,
            max_output_tokens=1,
            max_retries=0,
        )
        if _gemini_probe.probe():
            logger.info("Gemini connectivity probe: OK", extra={"model": _settings.gemini_model})
            app.state.gemini_status = "ok"
        else:
            logger.warning("Gemini connectivity probe: FAILED", extra={"model": _settings.gemini_model})
            app.state.gemini_status = "failed"
    except Exception as exc:
        logger.warning("Gemini probe failed", extra={"error": str(exc)})
        app.state.gemini_status = "failed"

    # Qdrant connectivity + collection probe — non-fatal, distinct failure modes
    try:
        _settings = get_settings()
        _qdrant_probe = QdrantClient(host=_settings.qdrant_host, port=_settings.qdrant_port)
        _exists = _qdrant_probe.collection_exists(_settings.qdrant_collection_name)
        if _exists:
            logger.info("Qdrant probe: OK", extra={"collection": _settings.qdrant_collection_name})
            app.state.qdrant_status = "ok"
        else:
            logger.warning(
                "Qdrant collection missing — knowledge base not loaded",
                extra={
                    "collection": _settings.qdrant_collection_name,
                    "qdrant_status": "collection_missing",
                },
            )
            app.state.qdrant_status = "collection_missing"
    except QdrantConnectionError as exc:
        logger.warning(
            "Qdrant connectivity probe: FAILED",
            extra={"qdrant_status": "unreachable", "error": str(exc)},
        )
        app.state.qdrant_status = "unreachable"
    except Exception as exc:
        logger.warning("Qdrant probe failed", extra={"error": str(exc)})
        app.state.qdrant_status = "failed"

    yield
    shutdown_executor()


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Reads settings once to configure CORS. All other service dependencies
    (SupabaseClient, AnalysisOrchestrator, ThreadPoolExecutor) are lazy-loaded
    on first request via the singleton providers in api/dependencies.py.

    Returns:
        Fully wired FastAPI application ready for mounting or testing.
    """
    settings = get_settings()

    app = FastAPI(
        title="ArchMind AI",
        version="1.0",
        description="AI-powered software architecture review agent.",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            extra={
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(jobs_router.router, prefix="/api/v1", dependencies=[Depends(require_auth)])
    app.include_router(reports_router.router, prefix="/api/v1", dependencies=[Depends(require_auth)])

    app.dependency_overrides[jobs_router.get_supabase_client] = get_supabase_client
    app.dependency_overrides[jobs_router.get_orchestrator] = get_orchestrator
    app.dependency_overrides[jobs_router.get_executor] = get_executor
    app.dependency_overrides[reports_router.get_supabase_client] = get_supabase_client

    return app
