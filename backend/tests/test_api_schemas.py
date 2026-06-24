"""Unit tests for API request/response schemas.

Pure Pydantic validation tests — no FastAPI, no HTTP, no routers.
Tests verify field presence, type coercion from Supabase raw dicts,
URL validation rules, and stability of API contracts.

All schemas must be constructable from the raw dicts returned by
SupabaseClient.get_job() and SupabaseClient.get_report(), which return
plain Python dicts with string UUIDs and ISO 8601 datetime strings.
Pydantic v2 coerces these automatically via model_validate().
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.schemas.health_schemas import HealthResponse
from api.schemas.job_schemas import (
    JobStatusResponse,
    JobSubmittedResponse,
    SubmitJobRequest,
)
from api.schemas.report_schemas import (
    ReportMetadataResponse,
    ReportResponse,
    ReportSectionResponse,
)

_JOB_ID = str(uuid4())
_REPORT_ID = str(uuid4())
_NOW = "2026-06-24T10:00:00+00:00"
_LATER = "2026-06-24T10:15:00+00:00"


# ---------------------------------------------------------------------------
# Supabase raw dict helpers — simulates get_job() / get_report() output
# ---------------------------------------------------------------------------


def _pending_job_dict() -> dict:
    return {
        "job_id": _JOB_ID,
        "repo_url": "https://github.com/owner/repo",
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
        "repo_url": "https://github.com/owner/repo",
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


def _failed_job_dict() -> dict:
    return {
        "job_id": _JOB_ID,
        "repo_url": "https://github.com/owner/repo",
        "repo_name": "repo",
        "status": "FAILED",
        "created_at": _NOW,
        "schema_version": "1.0",
        "started_at": _NOW,
        "completed_at": _LATER,
        "report_id": None,
        "error_message": "Internal workflow error. Check server logs.",
        "error_type": "RuntimeError",
    }


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
                "CRITICAL": 0, "HIGH": 1, "MEDIUM": 1, "LOW": 0, "INFO": 0
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
# SubmitJobRequest — URL validation
# ---------------------------------------------------------------------------


def test_submit_job_request_valid_github_https_url():
    req = SubmitJobRequest(repo_url="https://github.com/owner/repo")
    assert req.repo_url == "https://github.com/owner/repo"


def test_submit_job_request_strips_whitespace_before_validation():
    req = SubmitJobRequest(repo_url="  https://github.com/owner/repo  ")
    assert req.repo_url == "https://github.com/owner/repo"


def test_submit_job_request_rejects_non_github_domain():
    with pytest.raises(ValidationError):
        SubmitJobRequest(repo_url="https://gitlab.com/owner/repo")


def test_submit_job_request_rejects_http_not_https():
    with pytest.raises(ValidationError):
        SubmitJobRequest(repo_url="http://github.com/owner/repo")


def test_submit_job_request_rejects_ftp_scheme():
    with pytest.raises(ValidationError):
        SubmitJobRequest(repo_url="ftp://github.com/owner/repo")


def test_submit_job_request_rejects_empty_string():
    with pytest.raises(ValidationError):
        SubmitJobRequest(repo_url="")


def test_submit_job_request_rejects_missing_field():
    with pytest.raises(ValidationError):
        SubmitJobRequest()


def test_submit_job_request_rejects_bitbucket_url():
    with pytest.raises(ValidationError):
        SubmitJobRequest(repo_url="https://bitbucket.org/owner/repo")


# ---------------------------------------------------------------------------
# JobSubmittedResponse
# ---------------------------------------------------------------------------


def test_job_submitted_response_has_job_id():
    job_id = uuid4()
    resp = JobSubmittedResponse(job_id=job_id, status="PENDING", message="Job submitted.")
    assert resp.job_id == job_id


def test_job_submitted_response_status_is_string():
    resp = JobSubmittedResponse(job_id=uuid4(), status="PENDING", message="Job submitted.")
    assert isinstance(resp.status, str)
    assert resp.status == "PENDING"


def test_job_submitted_response_has_message():
    resp = JobSubmittedResponse(job_id=uuid4(), status="PENDING", message="Analysis queued.")
    assert resp.message == "Analysis queued."


# ---------------------------------------------------------------------------
# JobStatusResponse — from Supabase raw dict
# ---------------------------------------------------------------------------


def test_job_status_response_from_pending_dict():
    resp = JobStatusResponse.model_validate(_pending_job_dict())
    assert str(resp.job_id) == _JOB_ID
    assert resp.status == "PENDING"
    assert resp.repo_url == "https://github.com/owner/repo"
    assert resp.repo_name == "repo"


def test_job_status_response_pending_has_null_optional_fields():
    resp = JobStatusResponse.model_validate(_pending_job_dict())
    assert resp.started_at is None
    assert resp.completed_at is None
    assert resp.report_id is None
    assert resp.error_message is None
    assert resp.error_type is None


def test_job_status_response_complete_has_report_id():
    resp = JobStatusResponse.model_validate(_complete_job_dict())
    assert resp.status == "COMPLETE"
    assert resp.report_id is not None
    assert str(resp.report_id) == _REPORT_ID


def test_job_status_response_complete_has_timestamps():
    resp = JobStatusResponse.model_validate(_complete_job_dict())
    assert resp.started_at is not None
    assert resp.completed_at is not None


def test_job_status_response_failed_has_error_fields():
    resp = JobStatusResponse.model_validate(_failed_job_dict())
    assert resp.status == "FAILED"
    assert resp.error_message == "Internal workflow error. Check server logs."
    assert resp.error_type == "RuntimeError"


def test_job_status_response_status_is_plain_string_not_enum():
    """API contract: status must be a str, not a JobStatus enum instance."""
    resp = JobStatusResponse.model_validate(_pending_job_dict())
    assert type(resp.status) is str


def test_job_status_response_coerces_string_uuid_to_uuid_type():
    resp = JobStatusResponse.model_validate(_pending_job_dict())
    from uuid import UUID
    assert isinstance(resp.job_id, UUID)


def test_job_status_response_coerces_iso_string_to_datetime():
    from datetime import datetime
    resp = JobStatusResponse.model_validate(_pending_job_dict())
    assert isinstance(resp.created_at, datetime)


def test_job_status_response_excludes_schema_version():
    """schema_version is an internal field; must not appear in API response."""
    resp = JobStatusResponse.model_validate(_pending_job_dict())
    assert not hasattr(resp, "schema_version")


# ---------------------------------------------------------------------------
# ReportMetadataResponse
# ---------------------------------------------------------------------------


def test_report_metadata_response_from_dict():
    data = _report_dict()["metadata"]
    meta = ReportMetadataResponse.model_validate(data)
    assert meta.primary_language == "Python"
    assert meta.security_finding_count == 2
    assert meta.recommendation_count == 3


def test_report_metadata_response_enum_fields_are_strings():
    """Enum values arrive as strings from JSONB — must remain strings in response."""
    data = _report_dict()["metadata"]
    meta = ReportMetadataResponse.model_validate(data)
    assert type(meta.detected_architecture_pattern) is str
    assert type(meta.architecture_confidence) is str


def test_report_metadata_response_highest_severity_nullable():
    data = _report_dict()["metadata"]
    data["highest_severity_finding"] = None
    meta = ReportMetadataResponse.model_validate(data)
    assert meta.highest_severity_finding is None


def test_report_metadata_response_finding_counts_is_dict():
    data = _report_dict()["metadata"]
    meta = ReportMetadataResponse.model_validate(data)
    assert isinstance(meta.finding_counts_by_severity, dict)
    assert meta.finding_counts_by_severity["HIGH"] == 1


# ---------------------------------------------------------------------------
# ReportSectionResponse
# ---------------------------------------------------------------------------


def test_report_section_response_from_dict():
    section_data = _report_dict()["sections"][0]
    section = ReportSectionResponse.model_validate(section_data)
    assert section.section_order == 1
    assert section.section_key == "EXECUTIVE_SUMMARY"
    assert section.section_title == "Executive Summary"
    assert "Content for section 1" in section.content_markdown


def test_report_section_response_section_key_is_string():
    """section_key must be a plain string — not a SectionKey enum instance."""
    section_data = _report_dict()["sections"][0]
    section = ReportSectionResponse.model_validate(section_data)
    assert type(section.section_key) is str


# ---------------------------------------------------------------------------
# ReportResponse — from Supabase raw dict
# ---------------------------------------------------------------------------


def test_report_response_from_supabase_dict():
    resp = ReportResponse.model_validate(_report_dict())
    assert str(resp.report_id) == _REPORT_ID
    assert str(resp.job_id) == _JOB_ID
    assert resp.repo_url == "https://github.com/owner/repo"
    assert resp.schema_version == "1.0"


def test_report_response_has_markdown_content():
    resp = ReportResponse.model_validate(_report_dict())
    assert "ArchMind AI Report" in resp.markdown_content


def test_report_response_metadata_is_nested_model():
    resp = ReportResponse.model_validate(_report_dict())
    assert isinstance(resp.metadata, ReportMetadataResponse)
    assert resp.metadata.primary_language == "Python"


def test_report_response_sections_are_list_of_models():
    resp = ReportResponse.model_validate(_report_dict())
    assert isinstance(resp.sections, list)
    assert len(resp.sections) == 6
    assert all(isinstance(s, ReportSectionResponse) for s in resp.sections)


def test_report_response_sections_ordered_correctly():
    resp = ReportResponse.model_validate(_report_dict())
    assert resp.sections[0].section_key == "EXECUTIVE_SUMMARY"
    assert resp.sections[5].section_key == "ACTIONABLE_NEXT_STEPS"


def test_report_response_coerces_string_uuid_to_uuid():
    from uuid import UUID
    resp = ReportResponse.model_validate(_report_dict())
    assert isinstance(resp.report_id, UUID)
    assert isinstance(resp.job_id, UUID)


def test_report_response_coerces_iso_string_to_datetime():
    from datetime import datetime
    resp = ReportResponse.model_validate(_report_dict())
    assert isinstance(resp.generated_at, datetime)


# ---------------------------------------------------------------------------
# HealthResponse
# ---------------------------------------------------------------------------


def test_health_response_status_ok():
    resp = HealthResponse(status="ok", version="1.0")
    assert resp.status == "ok"


def test_health_response_version_present():
    resp = HealthResponse(status="ok", version="1.0")
    assert resp.version == "1.0"


def test_health_response_requires_both_fields():
    with pytest.raises(ValidationError):
        HealthResponse(status="ok")
