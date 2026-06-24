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
