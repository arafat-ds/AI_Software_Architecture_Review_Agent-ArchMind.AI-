"""Unit tests for the jobs router.

Covers POST /jobs and GET /jobs/{job_id}.
Each test creates an isolated FastAPI test app with dependency overrides
for get_orchestrator, get_executor, and get_supabase_client.
No real Supabase or ThreadPoolExecutor is used.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.jobs import get_executor, get_orchestrator, get_supabase_client, router

_JOB_ID = str(uuid4())
_REPORT_ID = str(uuid4())
_NOW = "2026-06-24T10:00:00+00:00"
_LATER = "2026-06-24T10:15:00+00:00"
_VALID_URL = "https://github.com/owner/repo"


def _make_client(
    mock_orchestrator: MagicMock | None = None,
    mock_executor: MagicMock | None = None,
    mock_supabase: MagicMock | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    if mock_orchestrator is not None:
        app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    if mock_executor is not None:
        app.dependency_overrides[get_executor] = lambda: mock_executor
    if mock_supabase is not None:
        app.dependency_overrides[get_supabase_client] = lambda: mock_supabase
    return TestClient(app)


def _pending_job_dict() -> dict:
    return {
        "job_id": _JOB_ID,
        "repo_url": _VALID_URL,
        "repo_name": "repo",
        "status": "PENDING",
        "created_at": _NOW,
        "schema_version": "1.0",
        "started_at": None,
        "completed_at": None,
        "report_id": None,
        "error_message": None,
        "error_type": None,
    }


def _complete_job_dict() -> dict:
    return {
        "job_id": _JOB_ID,
        "repo_url": _VALID_URL,
        "repo_name": "repo",
        "status": "COMPLETE",
        "created_at": _NOW,
        "schema_version": "1.0",
        "started_at": _NOW,
        "completed_at": _LATER,
        "report_id": _REPORT_ID,
        "error_message": None,
        "error_type": None,
    }


# ---------------------------------------------------------------------------
# POST /jobs — happy path
# ---------------------------------------------------------------------------


def test_submit_job_returns_202():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs", json={"repo_url": _VALID_URL})
    assert resp.status_code == 202


def test_submit_job_response_has_job_id():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs", json={"repo_url": _VALID_URL})
    body = resp.json()
    assert "job_id" in body
    UUID(body["job_id"])  # must be a valid UUID string


def test_submit_job_response_status_is_pending():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs", json={"repo_url": _VALID_URL})
    assert resp.json()["status"] == "PENDING"


def test_submit_job_response_has_message():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs", json={"repo_url": _VALID_URL})
    body = resp.json()
    assert "message" in body
    assert body["message"]


# ---------------------------------------------------------------------------
# POST /jobs — orchestrator / executor interactions
# ---------------------------------------------------------------------------


def test_submit_job_calls_create_job_once():
    mock_orch = MagicMock()
    client = _make_client(mock_orch, MagicMock())
    client.post("/jobs", json={"repo_url": _VALID_URL})
    mock_orch.create_job.assert_called_once()


def test_submit_job_passes_correct_repo_url_to_create_job():
    mock_orch = MagicMock()
    client = _make_client(mock_orch, MagicMock())
    client.post("/jobs", json={"repo_url": _VALID_URL})
    _, call_repo_url, _ = mock_orch.create_job.call_args[0]
    assert call_repo_url == _VALID_URL


def test_submit_job_passes_extracted_repo_name_to_create_job():
    mock_orch = MagicMock()
    client = _make_client(mock_orch, MagicMock())
    client.post("/jobs", json={"repo_url": _VALID_URL})
    _, _, call_repo_name = mock_orch.create_job.call_args[0]
    assert call_repo_name == "repo"


def test_submit_job_passes_uuid_job_id_to_create_job():
    mock_orch = MagicMock()
    client = _make_client(mock_orch, MagicMock())
    client.post("/jobs", json={"repo_url": _VALID_URL})
    call_job_id, _, _ = mock_orch.create_job.call_args[0]
    assert isinstance(call_job_id, UUID)


def test_submit_job_submits_run_to_executor():
    mock_orch = MagicMock()
    mock_exec = MagicMock()
    client = _make_client(mock_orch, mock_exec)
    resp = client.post("/jobs", json={"repo_url": _VALID_URL})
    returned_job_id = UUID(resp.json()["job_id"])

    mock_exec.submit.assert_called_once()
    fn, submitted_job_id, submitted_url = mock_exec.submit.call_args[0]
    assert fn == mock_orch.run
    assert submitted_job_id == returned_job_id
    assert submitted_url == _VALID_URL


def test_submit_job_job_id_consistent_between_create_and_executor():
    """job_id passed to create_job and submitted to executor must match."""
    mock_orch = MagicMock()
    mock_exec = MagicMock()
    client = _make_client(mock_orch, mock_exec)
    client.post("/jobs", json={"repo_url": _VALID_URL})

    create_job_id = mock_orch.create_job.call_args[0][0]
    executor_job_id = mock_exec.submit.call_args[0][1]
    assert create_job_id == executor_job_id


def test_submit_job_strips_dot_git_from_repo_name():
    mock_orch = MagicMock()
    client = _make_client(mock_orch, MagicMock())
    client.post("/jobs", json={"repo_url": "https://github.com/owner/myrepo.git"})
    _, _, repo_name = mock_orch.create_job.call_args[0]
    assert repo_name == "myrepo"


# ---------------------------------------------------------------------------
# POST /jobs — validation errors
# ---------------------------------------------------------------------------


def test_submit_job_rejects_invalid_url_with_422():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs", json={"repo_url": "https://gitlab.com/owner/repo"})
    assert resp.status_code == 422


def test_submit_job_rejects_missing_body_with_422():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs")
    assert resp.status_code == 422


def test_submit_job_rejects_http_url_with_422():
    client = _make_client(MagicMock(), MagicMock())
    resp = client.post("/jobs", json={"repo_url": "http://github.com/owner/repo"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------


def test_get_job_status_returns_200_when_job_exists():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = _pending_job_dict()
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get(f"/jobs/{_JOB_ID}")
    assert resp.status_code == 200


def test_get_job_status_returns_404_when_job_not_found():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = None
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get(f"/jobs/{_JOB_ID}")
    assert resp.status_code == 404


def test_get_job_status_response_has_correct_job_id():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = _pending_job_dict()
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get(f"/jobs/{_JOB_ID}")
    assert resp.json()["job_id"] == _JOB_ID


def test_get_job_status_response_has_status():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = _pending_job_dict()
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get(f"/jobs/{_JOB_ID}")
    assert resp.json()["status"] == "PENDING"


def test_get_job_status_returns_422_for_invalid_uuid():
    mock_supabase = MagicMock()
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get("/jobs/not-a-valid-uuid")
    assert resp.status_code == 422


def test_get_job_status_passes_uuid_to_supabase():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = _pending_job_dict()
    client = _make_client(mock_supabase=mock_supabase)
    client.get(f"/jobs/{_JOB_ID}")
    mock_supabase.get_job.assert_called_once()
    passed_arg = mock_supabase.get_job.call_args[0][0]
    assert isinstance(passed_arg, UUID)
    assert str(passed_arg) == _JOB_ID


def test_get_job_status_response_excludes_schema_version():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = _pending_job_dict()
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get(f"/jobs/{_JOB_ID}")
    assert "schema_version" not in resp.json()


def test_get_job_status_complete_includes_report_id():
    mock_supabase = MagicMock()
    mock_supabase.get_job.return_value = _complete_job_dict()
    client = _make_client(mock_supabase=mock_supabase)
    resp = client.get(f"/jobs/{_JOB_ID}")
    assert resp.json()["report_id"] == _REPORT_ID
