"""API request/response schemas for job lifecycle endpoints.

Design rules:
- status fields are plain str, never JobStatus enum instances, for API contract
  stability (enum additions never break existing consumers).
- JobStatusResponse excludes schema_version (internal field).
- SubmitJobRequest validates GitHub HTTPS URLs via field_validator.
- All schemas must be constructable from SupabaseClient.get_job() raw dicts
  via model_validate() — Pydantic v2 coerces string UUIDs and ISO datetimes.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SubmitJobRequest(BaseModel):
    """Request body for POST /jobs."""

    repo_url: str = Field(..., description="GitHub HTTPS URL of the repository to analyse.")

    @field_validator("repo_url", mode="before")
    @classmethod
    def validate_github_https_url(cls, value: str) -> str:
        url = str(value).strip()
        if not url.startswith("https://github.com/"):
            raise ValueError(
                "repo_url must be a GitHub HTTPS URL starting with 'https://github.com/'."
            )
        return url


class JobSubmittedResponse(BaseModel):
    """Response body for POST /jobs (202 Accepted)."""

    job_id: UUID = Field(..., description="UUID of the newly created job.")
    status: str = Field(..., description="Initial job status. Always 'PENDING'.")
    message: str = Field(..., description="Human-readable confirmation message.")


class JobStatusResponse(BaseModel):
    """Response body for GET /jobs/{job_id}.

    Constructed via model_validate() from the raw dict returned by
    SupabaseClient.get_job(). schema_version is intentionally excluded —
    it is an internal contract field, not part of the public API response.
    """

    job_id: UUID = Field(..., description="Primary key of the job.")
    repo_url: str = Field(..., description="Repository URL as submitted.")
    repo_name: str = Field(..., description="Repository name extracted from the URL.")
    status: str = Field(..., description="Current job lifecycle status.")
    created_at: datetime = Field(..., description="UTC timestamp when the job was created.")
    started_at: datetime | None = Field(default=None, description="UTC timestamp when workflow began.")
    completed_at: datetime | None = Field(default=None, description="UTC timestamp when job reached terminal state.")
    report_id: UUID | None = Field(default=None, description="UUID of the generated report. Set when COMPLETE.")
    error_message: str | None = Field(default=None, description="Human-readable error. Set when FAILED.")
    error_type: str | None = Field(default=None, description="Exception class name. Set when FAILED.")

    model_config = {"extra": "ignore"}
