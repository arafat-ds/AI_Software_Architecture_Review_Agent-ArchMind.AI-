"""API request/response schemas for report endpoints.

Design rules:
- Enum fields (detected_architecture_pattern, architecture_confidence,
  highest_severity_finding, section_key) are typed as str, not actual enum
  instances. Values arrive as plain strings from Supabase JSONB columns and
  must remain strings in the response for API contract stability.
- All schemas are constructable from SupabaseClient.get_report() raw dicts
  via model_validate().
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReportMetadataResponse(BaseModel):
    """Structured metadata about the analysis run, nested inside ReportResponse."""

    primary_language: str = Field(..., description="Primary programming language detected.")
    detected_architecture_pattern: str = Field(..., description="Architecture pattern identified.")
    architecture_confidence: str = Field(..., description="Confidence level for architecture detection.")
    security_finding_count: int = Field(..., description="Total number of security findings.")
    finding_counts_by_severity: dict = Field(..., description="Finding counts keyed by severity label.")
    highest_severity_finding: str | None = Field(
        default=None, description="Highest severity level found. None if no findings."
    )
    recommendation_count: int = Field(..., description="Total number of recommendations generated.")
    p1_recommendation_count: int = Field(..., description="Number of P1 (critical) recommendations.")
    rag_chunks_used_count: int = Field(..., description="Number of RAG knowledge base chunks used.")
    analysis_duration_seconds: int = Field(..., description="Total workflow duration in seconds.")
    total_files_analyzed: int = Field(..., description="Number of source files analysed.")
    total_llm_tokens_used: int = Field(..., description="Total LLM tokens consumed across all calls.")

    model_config = {"extra": "ignore"}


class ReportSectionResponse(BaseModel):
    """A single report section, ordered by section_order."""

    section_order: int = Field(..., description="Display order index (1-based).")
    section_key: str = Field(..., description="Section identifier key.")
    section_title: str = Field(..., description="Human-readable section title.")
    content_markdown: str = Field(..., description="Section content in Markdown.")

    model_config = {"extra": "ignore"}


class ReportResponse(BaseModel):
    """Response body for GET /reports/{report_id}.

    Constructed via model_validate() from the raw dict returned by
    SupabaseClient.get_report(). Nested metadata and sections are
    coerced from JSONB dicts automatically by Pydantic v2.
    """

    report_id: UUID = Field(..., description="Primary key of the report.")
    job_id: UUID = Field(..., description="UUID of the job that produced this report.")
    repo_url: str = Field(..., description="Repository URL that was analysed.")
    repo_name: str = Field(..., description="Repository name.")
    generated_at: datetime = Field(..., description="UTC timestamp when the report was generated.")
    schema_version: str = Field(..., description="Report schema version.")
    markdown_content: str = Field(..., description="Full report in Markdown format.")
    metadata: ReportMetadataResponse = Field(..., description="Analysis run metadata.")
    sections: list[ReportSectionResponse] = Field(..., description="Ordered report sections.")

    model_config = {"extra": "ignore"}
