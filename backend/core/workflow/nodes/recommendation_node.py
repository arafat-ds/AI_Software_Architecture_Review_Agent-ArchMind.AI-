"""LangGraph node: RecommendationNode — Phase 3 placeholder.

Full Recommendation Agent service will be implemented in Phase 4.
This placeholder advances workflow_status to ASSEMBLING and
records the node execution in the audit log.

Output field: recommendations_section (remains None until Phase 4).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.workflow.state import AnalysisState, begin_node_execution
from shared.logging.logger import get_logger
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution

logger = get_logger(__name__)

_NODE_NAME = "RecommendationNode"


def recommendation_node(state: AnalysisState) -> dict[str, Any]:
    """Placeholder: Recommendation Agent.

    Phase 4 replaces this with the full Gemini agent that synthesises
    ArchitectureSection, SecuritySection, and RAGContext into a
    prioritised RecommendationSection.
    recommendations_section remains None in AnalysisState until Phase 4.

    Args:
        state: Current AnalysisState.

    Returns:
        Partial state dict containing:
        - workflow_status: Advanced to ASSEMBLING
        - node_execution_log: Updated with completion record
        - errors: Unchanged (no-op placeholder cannot fail)
    """
    execution = begin_node_execution(
        state, _NODE_NAME, output_field="recommendations_section"
    )

    logger.info(
        "RecommendationNode started (placeholder — Phase 4 pending)",
        extra={"job_id": str(state["job_id"])},
    )

    _complete_execution(execution, NodeExecutionStatus.COMPLETE)

    logger.info(
        "RecommendationNode complete (placeholder)",
        extra={"job_id": str(state["job_id"])},
    )

    return {
        "workflow_status": WorkflowStatus.ASSEMBLING,
        "node_execution_log": state["node_execution_log"],
        "errors": state["errors"],
    }


def _complete_execution(execution: NodeExecution, status: NodeExecutionStatus) -> None:
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
