"""FastAPI application factory for ArchMind AI.

Usage:
  Development:  uvicorn api.main:create_app --factory --reload
  Production:   uvicorn api.main:create_app --factory --workers 1

No module-level `app` singleton — using the factory pattern keeps this module
safely importable without environment variables, which is required for tests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_executor, get_orchestrator, get_supabase_client, shutdown_executor
from api.routers import health
from api.routers import jobs as jobs_router
from api.routers import reports as reports_router
from config.settings import get_settings
from shared.logging.logger import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: configure logging on startup, clean up on shutdown."""
    configure_logging()
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(jobs_router.router, prefix="/api/v1")
    app.include_router(reports_router.router, prefix="/api/v1")

    app.dependency_overrides[jobs_router.get_supabase_client] = get_supabase_client
    app.dependency_overrides[jobs_router.get_orchestrator] = get_orchestrator
    app.dependency_overrides[jobs_router.get_executor] = get_executor
    app.dependency_overrides[reports_router.get_supabase_client] = get_supabase_client

    return app
