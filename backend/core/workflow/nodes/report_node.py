"""LangGraph node: ReportAssemblyNode.

Responsibilities:
- Validate that all required sections are present in state
- Call ReportService to assemble the FinalReport (no LLM calls)
- Write final_report and final_report_markdown to AnalysisState
- On failure: append WorkflowError and raise FatalNodeError

ReportService requires no external clients (no Gemini, no Qdrant).
It is instantiated once as a process-lifetime singleton.

Output fields: final_report, final_report_markdown
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.workflow.state import (
    AnalysisState,
    append_workflow_error,
    begin_node_execution,
    require_field,
)
from services.report_assembly import ReportService
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.logging.logger import get_logger
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution
from shared.types.manifest_types import RepositoryManifest
from shared.types.pcr_types import ParsedCodeRepresentation
from shared.types.report_types import RecommendationSection

logger = get_logger(__name__)

_NODE_NAME = "ReportGenerationNode"
_service: ReportService | None = None


def _get_service() -> ReportService:
    """Return the ReportService singleton, initialising it on first call."""
    global _service
    if _service is None:
        _service = ReportService()
    return _service


def report_generation_node(state: AnalysisState) -> dict[str, Any]:
    """Assemble the FinalReport and write it to state.

    Args:
        state: Current AnalysisState. Reads all agent outputs and manifest.

    Returns:
        Partial state dict containing:
        - final_report: Validated FinalReport instance
        - final_report_markdown: final_report.markdown_content string
        - workflow_status: Advanced to COMPLETE
        - node_execution_log: Updated with completion record
        - errors: Unchanged on success; appended on failure

    Raises:
        FatalNodeError: Always on report assembly failure.
    """
    arch_section: ArchitectureSection = require_field(  # type: ignore[assignment]
        state, "architecture_section"
    )
    sec_section: SecuritySection = require_field(  # type: ignore[assignment]
        state, "security_section"
    )
    rec_section: RecommendationSection = require_field(  # type: ignore[assignment]
        state, "recommendations_section"
    )
    manifest: RepositoryManifest = require_field(  # type: ignore[assignment]
        state, "repository_manifest"
    )
    pcr: ParsedCodeRepresentation = require_field(  # type: ignore[assignment]
        state, "parsed_code_representation"
    )

    execution = begin_node_execution(
        state, _NODE_NAME, output_field="final_report"
    )

    logger.info("ReportGenerationNode started", extra={
        "job_id": str(state["job_id"]),
        "recommendations": len(rec_section.recommendations),
    })

    try:
        report = _get_service().run(
            job_id=state["job_id"],
            repo_url=state["repo_url"],
            architecture_section=arch_section,
            security_section=sec_section,
            recommendations_section=rec_section,
            repository_manifest=manifest,
            pcr=pcr,
            workflow_start=state["created_at"],
        )
        _complete_execution(execution, NodeExecutionStatus.COMPLETE)

        logger.info("ReportGenerationNode complete", extra={
            "job_id": str(state["job_id"]),
            "report_id": str(report.report_id),
            "markdown_chars": len(report.markdown_content),
        })

        return {
            "final_report": report,
            "final_report_markdown": report.markdown_content,
            "workflow_status": WorkflowStatus.COMPLETE,
            "node_execution_log": state["node_execution_log"],
            "errors": state["errors"],
        }

    except Exception as exc:
        error = append_workflow_error(
            state=state,
            node_name=_NODE_NAME,
            error_type=type(exc).__name__,
            message=str(exc),
            is_fatal=True,
        )
        _complete_execution(execution, NodeExecutionStatus.FAILED)

        logger.error("ReportGenerationNode failed", extra={
            "job_id": str(state["job_id"]),
            "error_type": error.error_type,
            "error_id": error.error_id,
        })

        raise FatalNodeError(
            node_name=_NODE_NAME,
            reason=str(exc),
            cause=exc,
        ) from exc


def _complete_execution(execution: NodeExecution, status: NodeExecutionStatus) -> None:
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
