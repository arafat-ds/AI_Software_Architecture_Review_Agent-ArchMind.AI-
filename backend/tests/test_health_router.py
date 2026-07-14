"""Unit tests for the health router.

Creates a minimal FastAPI test app including only the health router.
No dependency overrides needed — health check has no dependencies.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.health import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app)


def test_health_endpoint_returns_200():
    resp = _client.get("/health")
    assert resp.status_code == 200


def test_health_response_status_is_ok():
    resp = _client.get("/health")
    assert resp.json()["status"] == "ok"


def test_health_response_has_version():
    resp = _client.get("/health")
    body = resp.json()
    assert "version" in body
    assert body["version"]


def test_health_response_content_type_is_json():
    resp = _client.get("/health")
    assert "application/json" in resp.headers["content-type"]


def test_health_response_body_matches_schema():
    from api.schemas.health_schemas import HealthResponse
    resp = _client.get("/health")
    # Raises ValidationError if contract is broken
    model = HealthResponse.model_validate(resp.json())
    assert model.status == "ok"


# ---------------------------------------------------------------------------
# Dependency status (M6)
# ---------------------------------------------------------------------------


def _client_with_state(**state_kwargs) -> "TestClient":
    """Create a fresh test client with specific app.state values."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routers.health import router as health_router
    app = FastAPI()
    app.include_router(health_router)
    for key, value in state_kwargs.items():
        setattr(app.state, key, value)
    return TestClient(app)


def test_health_response_dependencies_key_present():
    resp = _client.get("/health")
    assert "dependencies" in resp.json()


def test_health_response_dependencies_unknown_when_no_state():
    resp = _client.get("/health")
    deps = resp.json()["dependencies"]
    assert deps["gemini"] == "unknown"
    assert deps["qdrant"] == "unknown"
    assert deps["supabase"] == "unknown"


def test_health_response_dependencies_reflect_app_state():
    client = _client_with_state(
        gemini_status="ok",
        qdrant_status="ok",
        supabase_status="ok",
    )
    deps = client.get("/health").json()["dependencies"]
    assert deps["gemini"] == "ok"
    assert deps["qdrant"] == "ok"
    assert deps["supabase"] == "ok"


def test_health_response_gemini_degraded_still_returns_200():
    client = _client_with_state(
        gemini_status="failed",
        qdrant_status="ok",
        supabase_status="ok",
    )
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["dependencies"]["gemini"] == "failed"


def test_health_response_qdrant_degraded_still_returns_200():
    client = _client_with_state(
        gemini_status="ok",
        qdrant_status="unreachable",
        supabase_status="ok",
    )
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["dependencies"]["qdrant"] == "unreachable"
