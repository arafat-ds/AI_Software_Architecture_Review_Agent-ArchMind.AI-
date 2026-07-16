"""Tests for M9.1 — Static API Key Authentication.

Coverage:
  - _check_api_key: valid, missing, empty, whitespace-only, wrong key
  - Response contract: status code, body, WWW-Authenticate header
  - Timing-safe comparison via hmac.compare_digest
  - require_auth abstraction: overridable without touching routers
  - Route protection: jobs and reports routers require auth
  - Health endpoint: unauthenticated regardless of key state
  - Settings: api_key field validation

All tests patch api.security.get_settings to avoid real environment
variables. Integration tests that use create_app() patch api.main.get_settings.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.security import _check_api_key, require_auth

_TEST_KEY = "test-api-key-minimum-32-chars-abc"   # 33 chars
_WRONG_KEY = "wrong-api-key-minimum-32-chars-xx"  # 33 chars
_SHORT_KEY = "too-short"                           # < 32 chars

_SECURITY_PATCH = "api.security.get_settings"
_MAIN_SETTINGS_PATCH = "api.main.get_settings"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.api_key = _TEST_KEY
    return s


@pytest.fixture
def settings_patch(mock_settings):
    """Patch get_settings inside api.security for the duration of a test."""
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        yield mock_settings


def _make_protected_client(mock_settings) -> TestClient:
    """Minimal app with a single protected endpoint wired via require_auth."""
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_auth)])
    def protected():
        return {"ok": True}

    with patch(_SECURITY_PATCH, return_value=mock_settings):
        return TestClient(app)


# ---------------------------------------------------------------------------
# Valid key — happy path
# ---------------------------------------------------------------------------


def test_valid_api_key_allows_request(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    assert resp.status_code == 200


def test_valid_api_key_response_body_correct(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    assert resp.json() == {"ok": True}


def test_valid_api_key_strips_surrounding_whitespace(mock_settings):
    """Key with surrounding whitespace is accepted after strip."""
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": f"  {_TEST_KEY}  "})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Missing header — 401
# ---------------------------------------------------------------------------


def test_missing_header_returns_401(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected")
    assert resp.status_code == 401


def test_missing_header_response_body(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected")
    assert resp.json() == {"detail": "Authentication required."}


def test_missing_header_includes_www_authenticate(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected")
    assert "WWW-Authenticate" in resp.headers
    assert resp.headers["WWW-Authenticate"] == 'ApiKey realm="ArchMind AI"'


def test_missing_header_content_type_is_json(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected")
    assert resp.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# Empty / whitespace-only header — 401 (same as missing)
# ---------------------------------------------------------------------------


def test_empty_header_value_returns_401(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": ""})
    assert resp.status_code == 401


def test_whitespace_only_header_value_returns_401(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": "   "})
    assert resp.status_code == 401


def test_empty_header_response_body_matches_missing_body(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": ""})
    assert resp.json() == {"detail": "Authentication required."}


# ---------------------------------------------------------------------------
# Wrong key — 401, same response as missing (no state leak)
# ---------------------------------------------------------------------------


def test_wrong_api_key_returns_401(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": _WRONG_KEY})
    assert resp.status_code == 401


def test_wrong_api_key_response_body_identical_to_missing(mock_settings):
    """Missing and invalid keys must produce identical responses — no state leak."""
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        missing_resp = client.get("/protected")
        wrong_resp = client.get("/protected", headers={"X-API-Key": _WRONG_KEY})
    assert missing_resp.status_code == wrong_resp.status_code
    assert missing_resp.json() == wrong_resp.json()
    assert missing_resp.headers.get("WWW-Authenticate") == wrong_resp.headers.get("WWW-Authenticate")


def test_wrong_key_includes_www_authenticate(mock_settings):
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/protected", headers={"X-API-Key": _WRONG_KEY})
    assert resp.headers.get("WWW-Authenticate") == 'ApiKey realm="ArchMind AI"'


# ---------------------------------------------------------------------------
# Timing-safe comparison
# ---------------------------------------------------------------------------


def test_auth_uses_hmac_compare_digest(mock_settings):
    """_check_api_key must use hmac.compare_digest, not == operator."""
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings), \
         patch("api.security.hmac.compare_digest", return_value=True) as mock_digest:
        resp = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    mock_digest.assert_called_once()
    assert resp.status_code == 200


def test_hmac_compare_digest_called_with_configured_key_first(mock_settings):
    """compare_digest(configured, provided) — configured key is first arg."""
    client = _make_protected_client(mock_settings)
    with patch(_SECURITY_PATCH, return_value=mock_settings), \
         patch("api.security.hmac.compare_digest", return_value=True) as mock_digest:
        client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    configured, provided = mock_digest.call_args[0]
    assert configured == _TEST_KEY


# ---------------------------------------------------------------------------
# require_auth abstraction — overridable without router changes
# ---------------------------------------------------------------------------


def test_require_auth_override_bypasses_auth_entirely():
    """Overriding require_auth in tests skips _check_api_key completely."""
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_auth)])
    def ep():
        return {"ok": True}

    app.dependency_overrides[require_auth] = lambda: None
    client = TestClient(app)
    resp = client.get("/protected")  # no key — should pass
    assert resp.status_code == 200


def test_require_auth_without_override_blocks_missing_key(mock_settings):
    """Without override, missing key is rejected even on a minimal app."""
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_auth)])
    def ep():
        return {"ok": True}

    with patch(_SECURITY_PATCH, return_value=mock_settings):
        client = TestClient(app)
        resp = client.get("/protected")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Route protection via create_app() — integration
# ---------------------------------------------------------------------------


def _make_integration_client() -> TestClient:
    from api.main import create_app

    mock_settings = MagicMock()
    mock_settings.cors_origins = ["http://localhost:3000"]
    mock_settings.api_key = _TEST_KEY

    mock_supabase = MagicMock()
    mock_supabase.recover_orphaned_jobs.return_value = 0

    with patch(_MAIN_SETTINGS_PATCH, return_value=mock_settings), \
         patch("api.main.get_supabase_client", return_value=mock_supabase), \
         patch("api.main.GeminiClient") as mock_gemini_cls, \
         patch("api.main.QdrantClient") as mock_qdrant_cls, \
         patch("api.main.shutdown_executor"), \
         patch(_SECURITY_PATCH, return_value=mock_settings):
        mock_gemini_cls.return_value.probe.return_value = True
        mock_qdrant_cls.return_value.collection_exists.return_value = True
        app = create_app()

    return app, mock_settings


def test_post_jobs_requires_auth():
    app, mock_settings = _make_integration_client()
    client = TestClient(app)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.post("/api/v1/jobs", json={"repo_url": "https://github.com/o/r"})
    assert resp.status_code == 401


def test_get_jobs_requires_auth():
    app, mock_settings = _make_integration_client()
    client = TestClient(app)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/api/v1/jobs")
    assert resp.status_code == 401


def test_get_job_status_requires_auth():
    from uuid import uuid4
    app, mock_settings = _make_integration_client()
    client = TestClient(app)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get(f"/api/v1/jobs/{uuid4()}")
    assert resp.status_code == 401


def test_get_report_requires_auth():
    from uuid import uuid4
    app, mock_settings = _make_integration_client()
    client = TestClient(app)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get(f"/api/v1/reports/{uuid4()}")
    assert resp.status_code == 401


def test_valid_key_reaches_jobs_endpoint():
    """Valid key passes auth; 404 from Supabase (not 401) confirms auth passed."""
    from api.routers.jobs import get_supabase_client
    from uuid import uuid4

    app, mock_settings = _make_integration_client()
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = None
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase

    client = TestClient(app)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get(
            f"/api/v1/jobs/{uuid4()}",
            headers={"X-API-Key": _TEST_KEY},
        )
    assert resp.status_code == 404  # auth passed; job not found


# ---------------------------------------------------------------------------
# Health endpoint — unauthenticated at all times (integration)
# ---------------------------------------------------------------------------


def test_health_accessible_without_api_key_via_create_app():
    app, mock_settings = _make_integration_client()
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_health_accessible_with_wrong_api_key_via_create_app():
    app, mock_settings = _make_integration_client()
    client = TestClient(app)
    with patch(_SECURITY_PATCH, return_value=mock_settings):
        resp = client.get("/api/v1/health", headers={"X-API-Key": _WRONG_KEY})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Settings: api_key field validation
# ---------------------------------------------------------------------------


def test_settings_api_key_empty_string_raises_validation_error():
    """Empty string is equivalent to missing — must fail validation."""
    from config.settings import Settings
    with pytest.raises(ValidationError):
        Settings(
            gemini_api_key="k" * 32,
            supabase_url="https://x.supabase.co",
            supabase_key="k" * 32,
            api_key="",
        )


def test_settings_api_key_too_short_raises_validation_error():
    from config.settings import Settings
    with pytest.raises(ValidationError):
        Settings(
            gemini_api_key="k" * 32,
            supabase_url="https://x.supabase.co",
            supabase_key="k" * 32,
            api_key=_SHORT_KEY,  # < 32 chars
        )


def test_settings_api_key_exactly_32_chars_accepted():
    from config.settings import Settings
    key = "a" * 32
    s = Settings(
        gemini_api_key="k" * 32,
        supabase_url="https://x.supabase.co",
        supabase_key="k" * 32,
        api_key=key,
    )
    assert s.api_key == key


def test_settings_api_key_strips_whitespace():
    from config.settings import Settings
    key = "a" * 32
    s = Settings(
        gemini_api_key="k" * 32,
        supabase_url="https://x.supabase.co",
        supabase_key="k" * 32,
        api_key=f"  {key}  ",
    )
    assert s.api_key == key


def test_settings_api_key_longer_than_32_accepted():
    from config.settings import Settings
    key = "a" * 64
    s = Settings(
        gemini_api_key="k" * 32,
        supabase_url="https://x.supabase.co",
        supabase_key="k" * 32,
        api_key=key,
    )
    assert s.api_key == key
