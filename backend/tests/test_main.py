"""Unit tests for api/main.py — FastAPI app factory and wiring.

Covers:
  - All routers mounted at /api/v1 prefix.
  - Routes not accessible without the prefix.
  - configure_logging() called once during startup (lifespan).
  - CORS middleware installed and uses settings.cors_origins.
  - Dependency overrides wire real providers from api/dependencies.py.
  - App title metadata.

create_app() is called inside each test with get_settings patched to avoid
requiring real environment variables.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

_SETTINGS_PATCH = "api.main.get_settings"


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.cors_origins = ["http://localhost:3000"]
    return settings


@pytest.fixture
def test_app(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        return create_app()


# ---------------------------------------------------------------------------
# Router mounting: /api/v1 prefix
# ---------------------------------------------------------------------------


def test_health_route_accessible_at_api_v1_prefix(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_routes_not_mounted_without_prefix(test_app):
    client = TestClient(test_app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 404


def test_jobs_route_registered_at_api_v1(test_app):
    client = TestClient(test_app)
    openapi = client.get("/openapi.json").json()
    assert "/api/v1/jobs" in openapi["paths"]
    assert "/api/v1/jobs/{job_id}" in openapi["paths"]


def test_reports_route_registered_at_api_v1(test_app):
    client = TestClient(test_app)
    openapi = client.get("/openapi.json").json()
    assert "/api/v1/reports/{report_id}" in openapi["paths"]


# ---------------------------------------------------------------------------
# Startup: configure_logging called once
# ---------------------------------------------------------------------------


def test_configure_logging_called_on_startup(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch("api.main.configure_logging") as mock_configure, \
         patch("api.main.shutdown_executor"):
        app = create_app()
        with TestClient(app):
            mock_configure.assert_called_once()


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------


def test_cors_allows_configured_origin(mock_settings):
    mock_settings.cors_origins = ["http://localhost:3000"]
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_uses_origins_from_settings(mock_settings):
    mock_settings.cors_origins = ["http://my-frontend.example.com"]
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        app = create_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/health",
        headers={"Origin": "http://my-frontend.example.com"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://my-frontend.example.com"


# ---------------------------------------------------------------------------
# Dependency override wiring
# ---------------------------------------------------------------------------


def test_dependency_override_jobs_get_orchestrator_wired(test_app):
    from api import dependencies
    from api.routers import jobs as jobs_router
    assert test_app.dependency_overrides.get(jobs_router.get_orchestrator) is dependencies.get_orchestrator


def test_dependency_override_jobs_get_executor_wired(test_app):
    from api import dependencies
    from api.routers import jobs as jobs_router
    assert test_app.dependency_overrides.get(jobs_router.get_executor) is dependencies.get_executor


def test_dependency_override_jobs_get_supabase_client_wired(test_app):
    from api import dependencies
    from api.routers import jobs as jobs_router
    assert test_app.dependency_overrides.get(jobs_router.get_supabase_client) is dependencies.get_supabase_client


def test_dependency_override_reports_get_supabase_client_wired(test_app):
    from api import dependencies
    from api.routers import reports as reports_router
    assert test_app.dependency_overrides.get(reports_router.get_supabase_client) is dependencies.get_supabase_client


# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------


def test_app_title_is_archmind_ai(test_app):
    assert test_app.title == "ArchMind AI"


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_json_500(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        app = create_app()

    @app.get("/test-boom")
    def boom():
        raise RuntimeError("test explosion")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test-boom")
    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Internal server error."}


def test_exception_handler_does_not_intercept_422(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        app = create_app()
    from api.routers import jobs as jobs_router
    app.dependency_overrides[jobs_router.get_orchestrator] = lambda: MagicMock()
    app.dependency_overrides[jobs_router.get_executor] = lambda: MagicMock()
    client = TestClient(app)
    resp = client.post("/api/v1/jobs", json={"repo_url": "https://gitlab.com/owner/repo"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


def test_exception_handler_does_not_intercept_404(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        app = create_app()
    from api.routers import jobs as jobs_router
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = None
    app.dependency_overrides[jobs_router.get_supabase_client] = lambda: mock_supabase
    client = TestClient(app)
    resp = client.get(f"/api/v1/jobs/{uuid4()}")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# Startup: orphan recovery called during lifespan
# ---------------------------------------------------------------------------


def test_startup_calls_recover_orphaned_jobs(mock_settings):
    mock_supabase = MagicMock()
    mock_supabase.recover_orphaned_jobs.return_value = 0
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch("api.main.get_supabase_client", return_value=mock_supabase), \
         patch("api.main.shutdown_executor"):
        app = create_app()
        with TestClient(app):
            pass
    mock_supabase.recover_orphaned_jobs.assert_called_once()


def test_startup_orphan_recovery_failure_does_not_crash_server(mock_settings):
    mock_supabase = MagicMock()
    mock_supabase.recover_orphaned_jobs.side_effect = Exception("supabase down")
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch("api.main.get_supabase_client", return_value=mock_supabase), \
         patch("api.main.shutdown_executor"):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
    assert resp.status_code == 200
