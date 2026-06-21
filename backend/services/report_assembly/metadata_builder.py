"""Report metadata builder.

Extracts structured key signals from all analysis outputs to populate
ReportMetadata. No LLM calls, no external I/O. Pure computation.

ReportMetadata enables lightweight querying of report signals without
parsing the full markdown content.
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import Severity
from shared.types.pcr_types import ParsedCodeRepresentation
from shared.types.report_types import RecommendationSection, ReportMetadata


def build_report_metadata(
    architecture_section: ArchitectureSection,
    security_section: SecuritySection,
    recommendations_section: RecommendationSection,
    pcr: ParsedCodeRepresentation,
    workflow_start: datetime,
    workflow_end: datetime,
) -> ReportMetadata:
    """Build ReportMetadata from all analysis outputs.

    Args:
        architecture_section: Architecture Agent output.
        security_section: Security Agent output.
        recommendations_section: Recommendation Agent output.
        pcr: ParsedCodeRepresentation for file count and language data.
        workflow_start: UTC datetime when the workflow was initialised.
        workflow_end: UTC datetime when report assembly began.

    Returns:
        Populated ReportMetadata instance.
    """
    primary_language = (
        pcr.parse_metadata.languages_parsed[0]
        if pcr.parse_metadata.languages_parsed
        else "unknown"
    )

    highest_severity = _highest_severity(security_section)

    p1_count = recommendations_section.recommendation_counts_by_priority.get("P1", 0)

    total_tokens = _sum_tokens(architecture_section, security_section, recommendations_section)

    duration_seconds = _duration_seconds(workflow_start, workflow_end)

    return ReportMetadata(
        primary_language=primary_language,
        detected_architecture_pattern=architecture_section.detected_pattern,
        architecture_confidence=architecture_section.confidence,
        security_finding_count=len(security_section.findings),
        finding_counts_by_severity=security_section.finding_counts_by_severity,
        highest_severity_finding=highest_severity,
        recommendation_count=len(recommendations_section.recommendations),
        p1_recommendation_count=p1_count,
        rag_chunks_used_count=recommendations_section.rag_chunks_used_count,
        analysis_duration_seconds=duration_seconds,
        total_files_analyzed=pcr.parse_metadata.files_parsed_successfully,
        total_llm_tokens_used=total_tokens,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _highest_severity(security_section: SecuritySection) -> Severity | None:
    if not security_section.findings:
        return None
    return max(f.severity for f in security_section.findings)


def _sum_tokens(
    architecture_section: ArchitectureSection,
    security_section: SecuritySection,
    recommendations_section: RecommendationSection,
) -> int:
    total = 0
    for section in (architecture_section, security_section, recommendations_section):
        meta = section.generation_metadata
        total += meta.input_token_count + meta.output_token_count
    return total


def _duration_seconds(workflow_start: datetime, workflow_end: datetime) -> int:
    start = _to_aware(workflow_start)
    end = _to_aware(workflow_end)
    delta = (end - start).total_seconds()
    return max(1, int(delta))


def _to_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
