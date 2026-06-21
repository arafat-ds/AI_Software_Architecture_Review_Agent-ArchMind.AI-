"""LangGraph node: RecommendationNode.

Responsibilities:
- Validate that architecture_section and security_section are present in state
- Read rag_context from state (may be None — non-fatal)
- Call RecommendationService to run rule engine + Gemini generation
- Write recommendations_section to AnalysisState
- On failure: append WorkflowError and raise FatalNodeError

Service is lazily initialised on first invocation to avoid loading
settings at import time (which would break tests without .env files).

Output field: recommendations_section
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
from services.recommendation_agent import RecommendationService
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.logging.logger import get_logger
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution
from shared.types.rag_types import RAGContext

logger = get_logger(__name__)

_NODE_NAME = "RecommendationNode"
_service: RecommendationService | None = None


def _get_service() -> RecommendationService:
    """Return the RecommendationService singleton, initialising it on first call."""
    global _service
    if _service is None:
        from config.constants import LLM_MAX_RETRIES, LLM_TEMPERATURE
        from config.settings import get_settings
        from infrastructure.gemini_client import GeminiClient

        settings = get_settings()
        _service = RecommendationService(
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


def recommendation_node(state: AnalysisState) -> dict[str, Any]:
    """Run the Recommendation Agent and write RecommendationSection to state.

    Args:
        state: Current AnalysisState. Reads architecture_section, security_section,
               and rag_context (None is valid when RAG has not run).

    Returns:
        Partial state dict containing:
        - recommendations_section: Populated RecommendationSection
        - workflow_status: Advanced to ASSEMBLING
        - node_execution_log: Updated with completion record
        - errors: Unchanged on success; appended on failure

    Raises:
        FatalNodeError: Always on recommendation synthesis failure.
    """
    arch_section: ArchitectureSection = require_field(  # type: ignore[assignment]
        state, "architecture_section"
    )
    sec_section: SecuritySection = require_field(  # type: ignore[assignment]
        state, "security_section"
    )

    rag_context: RAGContext | None = state.get("rag_context")  # type: ignore[assignment]

    execution = begin_node_execution(
        state, _NODE_NAME, output_field="recommendations_section"
    )

    logger.info("RecommendationNode started", extra={
        "job_id": str(state["job_id"]),
        "weaknesses": len(arch_section.weaknesses),
        "findings": len(sec_section.findings),
        "rag_available": rag_context is not None,
    })

    try:
        section = _get_service().run(
            architecture_section=arch_section,
            security_section=sec_section,
            rag_context=rag_context,
        )
        _complete_execution(execution, NodeExecutionStatus.COMPLETE)

        logger.info("RecommendationNode complete", extra={
            "job_id": str(state["job_id"]),
            "recommendations": len(section.recommendations),
            "rag_chunks_used": section.rag_chunks_used_count,
        })

        return {
            "recommendations_section": section,
            "workflow_status": WorkflowStatus.ASSEMBLING,
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

        logger.error("RecommendationNode failed", extra={
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
