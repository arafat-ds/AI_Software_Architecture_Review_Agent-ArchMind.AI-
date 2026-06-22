"""LangGraph node: RAGRetrievalNode.

Responsibilities:
- Validate that architecture_section and security_section are in state
- Call build_rag_queries() to derive typed Qdrant queries
- Call RAGRetrievalService.run() to retrieve knowledge base context
- Write rag_context to AnalysisState

Non-fatal failure model:
- Any exception (CollectionNotFoundError, EmbeddingError, config error)
  is caught, logged, and recorded as a non-fatal WorkflowError.
- rag_context is set to None so RecommendationNode proceeds without grounding.
- FatalNodeError is NEVER raised by this node.

Output field: rag_context
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
from services.rag_agent.query_builder import build_rag_queries
from shared.logging.logger import get_logger
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution

logger = get_logger(__name__)

_NODE_NAME = "RAGRetrievalNode"
_service = None


def _get_service():
    """Return the RAGRetrievalService singleton, initialising it on first call."""
    global _service
    if _service is None:
        from config.constants import LLM_MAX_RETRIES, LLM_TEMPERATURE
        from config.settings import get_settings
        from infrastructure.gemini_client import GeminiClient
        from infrastructure.qdrant_client import QdrantClient
        from services.rag_agent.retrieval_service import RAGRetrievalService

        settings = get_settings()
        _service = RAGRetrievalService(
            gemini_client=GeminiClient(
                api_key=settings.gemini_api_key,
                generation_model=settings.gemini_model,
                embedding_model=settings.gemini_embedding_model,
                temperature=LLM_TEMPERATURE,
                max_output_tokens=settings.llm_max_tokens,
                max_retries=LLM_MAX_RETRIES,
            ),
            qdrant_client=QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            ),
            collection_name=settings.qdrant_collection_name,
        )
    return _service


def rag_retrieval_node(state: AnalysisState) -> dict[str, Any]:
    """Run the RAG retrieval phase and write rag_context to state.

    Args:
        state: Current AnalysisState. Reads architecture_section and
               security_section to build queries.

    Returns:
        Partial state dict containing:
        - rag_context: Populated RAGContext on success, None on any failure
        - workflow_status: Advanced to SYNTHESIZING
        - node_execution_log: Updated with completion record
        - errors: Non-fatal WorkflowError appended on failure
    """
    arch_section: ArchitectureSection = require_field(  # type: ignore[assignment]
        state, "architecture_section"
    )
    sec_section: SecuritySection = require_field(  # type: ignore[assignment]
        state, "security_section"
    )

    execution = begin_node_execution(state, _NODE_NAME, output_field="rag_context")

    logger.info("RAGRetrievalNode started", extra={
        "job_id": str(state["job_id"]),
        "weaknesses": len(arch_section.weaknesses),
        "findings": len(sec_section.findings),
    })

    try:
        queries = build_rag_queries(arch_section, sec_section)

        if not queries:
            logger.info("No RAG queries generated — skipping retrieval", extra={
                "job_id": str(state["job_id"]),
            })
            _complete_execution(execution, NodeExecutionStatus.COMPLETE)
            return _result(state, rag_context=None)

        context = _get_service().run(queries, state["job_id"])
        _complete_execution(execution, NodeExecutionStatus.COMPLETE)

        logger.info("RAGRetrievalNode complete", extra={
            "job_id": str(state["job_id"]),
            "queries": context.total_queries_made,
            "chunks": context.total_chunks_retrieved,
        })
        return _result(state, rag_context=context)

    except Exception as exc:
        append_workflow_error(
            state=state,
            node_name=_NODE_NAME,
            error_type=type(exc).__name__,
            message=str(exc),
            is_fatal=False,
        )
        _complete_execution(execution, NodeExecutionStatus.FAILED)

        logger.warning("RAGRetrievalNode failed (non-fatal)", extra={
            "job_id": str(state["job_id"]),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return _result(state, rag_context=None)


def _result(state: AnalysisState, rag_context: object) -> dict[str, Any]:
    return {
        "rag_context": rag_context,
        "workflow_status": WorkflowStatus.SYNTHESIZING,
        "node_execution_log": state["node_execution_log"],
        "errors": state["errors"],
    }


def _complete_execution(execution: NodeExecution, status: NodeExecutionStatus) -> None:
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
