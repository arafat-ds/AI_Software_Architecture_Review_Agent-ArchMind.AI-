"""LangGraph node: ArchitectureAnalysisNode.

Responsibilities:
- Validate that parsed_code_representation is present in state
- Call ArchitectureService to run rule engine + Gemini generation
- Write architecture_section to AnalysisState
- On failure: append WorkflowError and raise FatalNodeError

Service is lazily initialised on first invocation to avoid loading
settings at import time (which would break tests without .env files).

Output field: architecture_section
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
from services.architecture_agent import ArchitectureService
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.logging.logger import get_logger
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution
from shared.types.pcr_types import ParsedCodeRepresentation

logger = get_logger(__name__)

_NODE_NAME = "ArchitectureAnalysisNode"
_service: ArchitectureService | None = None


def _get_service() -> ArchitectureService:
    """Return the ArchitectureService singleton, initialising it on first call."""
    global _service
    if _service is None:
        from config.constants import LLM_MAX_RETRIES, LLM_TEMPERATURE
        from config.settings import get_settings
        from infrastructure.gemini_client import GeminiClient

        settings = get_settings()
        _service = ArchitectureService(
            gemini_client=GeminiClient(
                api_key=settings.gemini_api_key,
                generation_model=settings.gemini_model,
                embedding_model=settings.gemini_embedding_model,
                temperature=LLM_TEMPERATURE,
                max_output_tokens=settings.llm_max_tokens,
                max_retries=LLM_MAX_RETRIES,
            ),
            model_id=settings.gemini_model,
        )
    return _service


def architecture_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """Run the Architecture Analysis Agent and write ArchitectureSection to state.

    Args:
        state: Current AnalysisState. Reads parsed_code_representation.

    Returns:
        Partial state dict containing:
        - architecture_section: Populated ArchitectureSection
        - workflow_status: Advanced to ANALYZING_SECURITY
        - node_execution_log: Updated with completion record
        - errors: Unchanged on success; appended on failure

    Raises:
        FatalNodeError: Always on architecture analysis failure.
    """
    pcr: ParsedCodeRepresentation = require_field(  # type: ignore[assignment]
        state, "parsed_code_representation"
    )

    execution = begin_node_execution(
        state, _NODE_NAME, output_field="architecture_section"
    )

    logger.info("ArchitectureAnalysisNode started", extra={
        "job_id": str(state["job_id"]),
        "files": len(pcr.file_analyses),
    })

    try:
        section = _get_service().run(pcr)
        _complete_execution(execution, NodeExecutionStatus.COMPLETE)

        logger.info("ArchitectureAnalysisNode complete", extra={
            "job_id": str(state["job_id"]),
            "pattern": section.detected_pattern.value,
            "confidence": section.confidence.value,
            "weaknesses": len(section.weaknesses),
            "strengths": len(section.strengths),
        })

        return {
            "architecture_section": section,
            "workflow_status": WorkflowStatus.ANALYZING_SECURITY,
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

        logger.error("ArchitectureAnalysisNode failed", extra={
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
