"""Unit tests for the reports router.

Covers GET /reports/{report_id}.
Uses dependency override for get_supabase_client — no real Supabase needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.reports import get_supabase_client, router

_REPORT_ID = str(uuid4())
_JOB_ID = str(uuid4())
_NOW = "2026-06-24T10:00:00+00:00"
_LATER = "2026-06-24T10:15:00+00:00"


def _make_client(mock_supabase: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase
    return TestClient(app)


def _report_dict() -> dict:
    return {
        "report_id": _REPORT_ID,
        "job_id": _JOB_ID,
        "repo_url": "https://github.com/owner/repo",
        "repo_name": "repo",
        "generated_at": _LATER,
        "schema_version": "1.0",
        "markdown_content": "# ArchMind AI Report\n\nTest content.",
        "metadata": {
            "primary_language": "Python",
            "detected_architecture_pattern": "LAYERED",
            "architecture_confidence": "HIGH",
            "security_finding_count": 2,
            "finding_counts_by_severity": {
                "CRITICAL": 0, "HIGH": 1, "MEDIUM": 1, "LOW": 0, "INFO": 0,
            },
            "highest_severity_finding": "HIGH",
            "recommendation_count": 3,
            "p1_recommendation_count": 1,
            "rag_chunks_used_count": 4,
            "analysis_duration_seconds": 90,
            "total_files_analyzed": 25,
            "total_llm_tokens_used": 12000,
        },
        "sections": [
            {
                "section_order": i,
                "section_key": key,
                "section_title": key.replace("_", " ").title(),
                "content_markdown": f"## {key}\n\nContent for section {i}.",
            }
            for i, key in enumerate([
                "EXECUTIVE_SUMMARY",
                "REPOSITORY_OVERVIEW",
                "ARCHITECTURE_ASSESSMENT",
                "SECURITY_FINDINGS",
                "RECOMMENDATIONS",
                "ACTIONABLE_NEXT_STEPS",
            ], start=1)
        ],
    }


# ---------------------------------------------------------------------------
# GET /reports/{report_id}
# ---------------------------------------------------------------------------


def test_get_report_returns_200_when_found():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    assert resp.status_code == 200


def test_get_report_returns_404_when_not_found():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = None
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    assert resp.status_code == 404


def test_get_report_returns_422_for_invalid_uuid():
    mock_supabase = MagicMock()
    client = _make_client(mock_supabase)
    resp = client.get("/reports/not-a-valid-uuid")
    assert resp.status_code == 422


def test_get_report_response_has_correct_report_id():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    assert resp.json()["report_id"] == _REPORT_ID


def test_get_report_response_has_correct_job_id():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    assert resp.json()["job_id"] == _JOB_ID


def test_get_report_passes_uuid_to_supabase():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    client.get(f"/reports/{_REPORT_ID}")
    mock_supabase.get_report.assert_called_once()
    passed_arg = mock_supabase.get_report.call_args[0][0]
    assert isinstance(passed_arg, UUID)
    assert str(passed_arg) == _REPORT_ID


def test_get_report_response_has_markdown_content():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    assert "ArchMind AI Report" in resp.json()["markdown_content"]


def test_get_report_response_metadata_is_nested():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    metadata = resp.json()["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["primary_language"] == "Python"
    assert metadata["security_finding_count"] == 2


def test_get_report_response_sections_is_list():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    sections = resp.json()["sections"]
    assert isinstance(sections, list)
    assert len(sections) == 6


def test_get_report_response_sections_first_is_executive_summary():
    mock_supabase = MagicMock()
    mock_supabase.get_report.return_value = _report_dict()
    client = _make_client(mock_supabase)
    resp = client.get(f"/reports/{_REPORT_ID}")
    assert resp.json()["sections"][0]["section_key"] == "EXECUTIVE_SUMMARY"
