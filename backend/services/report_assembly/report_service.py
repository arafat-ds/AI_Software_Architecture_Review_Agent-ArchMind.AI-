"""Report Assembly Service.

Orchestrates all section builders and the metadata builder into a fully
validated FinalReport. No LLM calls. Pure deterministic assembly.

The assembled FinalReport is the terminal artifact of the ArchMind AI
analysis workflow. It is written to AnalysisState by ReportAssemblyNode
and persisted to Supabase by the PersistenceNode (Phase 6).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from services.report_assembly.metadata_builder import build_report_metadata
from services.report_assembly.section_builders import (
    build_actionable_next_steps_section,
    build_architecture_assessment_section,
    build_executive_summary_section,
    build_recommendations_section,
    build_repository_overview_section,
    build_security_findings_section,
)
from shared.logging.logger import get_logger
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.manifest_types import RepositoryManifest
from shared.types.pcr_types import ParsedCodeRepresentation
from shared.types.report_types import FinalReport, RecommendationSection, ReportSection

logger = get_logger(__name__)


class ReportService:
    """Assembles the FinalReport from all analysis outputs.

    Stateless — safe to instantiate once and call run() multiple times.
    No external clients required; no constructor arguments.
    """

    def run(
        self,
        job_id: UUID,
        repo_url: str,
        architecture_section: ArchitectureSection,
        security_section: SecuritySection,
        recommendations_section: RecommendationSection,
        repository_manifest: RepositoryManifest,
        pcr: ParsedCodeRepresentation,
        workflow_start: datetime,
    ) -> FinalReport:
        """Assemble and validate the complete FinalReport.

        Args:
            job_id: UUID of the parent analysis job.
            repo_url: Repository URL as submitted by the user.
            architecture_section: Output of ArchitectureAnalysisNode.
            security_section: Output of SecurityAnalysisNode.
            recommendations_section: Output of RecommendationNode.
            repository_manifest: Output of IngestNode.
            pcr: Output of ParseNode.
            workflow_start: AnalysisState.created_at (workflow initialisation time).

        Returns:
            Validated FinalReport ready to write to AnalysisState.

        Raises:
            ValidationError: If any assembled section fails schema invariants.
                             Indicates a programming bug, not a runtime failure.
        """
        workflow_end = datetime.now(tz=timezone.utc)

        logger.debug("ReportService: building sections", extra={"job_id": str(job_id)})

        sections: list[ReportSection] = [
            build_executive_summary_section(recommendations_section, security_section),
            build_repository_overview_section(repository_manifest, pcr),
            build_architecture_assessment_section(architecture_section),
            build_security_findings_section(security_section),
            build_recommendations_section(recommendations_section),
            build_actionable_next_steps_section(recommendations_section),
        ]

        metadata = build_report_metadata(
            architecture_section=architecture_section,
            security_section=security_section,
            recommendations_section=recommendations_section,
            pcr=pcr,
            workflow_start=workflow_start,
            workflow_end=workflow_end,
        )

        markdown_content = "\n\n".join(s.content_markdown for s in sections)
        repo_name = _extract_repo_name(repo_url)

        report = FinalReport(
            report_id=uuid4(),
            job_id=job_id,
            repo_url=repo_url,
            repo_name=repo_name,
            generated_at=workflow_end,
            markdown_content=markdown_content,
            metadata=metadata,
            sections=sections,
        )

        logger.debug("ReportService: FinalReport assembled", extra={
            "job_id": str(job_id),
            "sections": len(sections),
            "markdown_chars": len(markdown_content),
        })
        return report


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_repo_name(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub HTTPS URL.

    The URL is always https://github.com/owner/repo (enforced by validators).
    Strips trailing slashes and .git suffix before extraction.
    """
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return parts[-1]
