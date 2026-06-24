"""Singleton dependency providers for the FastAPI application.

Each getter is lazy-initialized and cached in a module-level variable.
get_settings() is imported inside the function body (not at module top level)
to ensure this module is safely importable without environment variables.

Usage in main.py (via app.dependency_overrides):
    app.dependency_overrides[router.get_orchestrator] = get_orchestrator

Usage in tests (via app.dependency_overrides):
    app.dependency_overrides[router.get_orchestrator] = lambda: mock_orchestrator
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from config.settings import get_settings
from infrastructure.supabase_client import SupabaseClient
from services.orchestrator import AnalysisOrchestrator

_supabase_client: SupabaseClient | None = None
_orchestrator: AnalysisOrchestrator | None = None
_executor: ThreadPoolExecutor | None = None


def get_supabase_client() -> SupabaseClient:
    """Return the SupabaseClient singleton, creating it on first call."""
    global _supabase_client
    if _supabase_client is None:
        settings = get_settings()
        _supabase_client = SupabaseClient(url=settings.supabase_url, key=settings.supabase_key)
    return _supabase_client


def get_orchestrator() -> AnalysisOrchestrator:
    """Return the AnalysisOrchestrator singleton, creating it on first call."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AnalysisOrchestrator(supabase_client=get_supabase_client())
    return _orchestrator


def get_executor() -> ThreadPoolExecutor:
    """Return the ThreadPoolExecutor singleton sized from settings.max_concurrent_jobs."""
    global _executor
    if _executor is None:
        settings = get_settings()
        _executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)
    return _executor


def shutdown_executor() -> None:
    """Shut down the executor gracefully. Called during app lifespan teardown.

    Sets the module-level singleton to None so a new executor can be created
    if the app is restarted within the same process (e.g. during testing).
    Safe to call when the executor has not yet been initialized.
    """
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
