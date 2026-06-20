"""LangGraph node: ReportGenerationNode — Phase 3 placeholder.

Full Report Generation service will be implemented in Phase 6.
This placeholder advances workflow_status to COMPLETE and
records the node execution in the audit log.

Output field: final_report_markdown (remains None until Phase 6).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.workflow.state import AnalysisState, begin_node_execution
from shared.logging.logger import get_logger
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution

logger = get_logger(__name__)

_NODE_NAME = "ReportGenerationNode"


def report_generation_node(state: AnalysisState) -> dict[str, Any]:
    """Placeholder: Report Generation service.

    Phase 6 replaces this with the full report assembly and persistence
    service that assembles a FinalReport from all agent outputs and
    writes it to Supabase.
    final_report_markdown remains None in AnalysisState until Phase 6.

    Args:
        state: Current AnalysisState.

    Returns:
        Partial state dict containing:
        - workflow_status: Advanced to COMPLETE
        - node_execution_log: Updated with completion record
        - errors: Unchanged (no-op placeholder cannot fail)
    """
    execution = begin_node_execution(
        state, _NODE_NAME, output_field="final_report_markdown"
    )

    logger.info(
        "ReportGenerationNode started (placeholder — Phase 6 pending)",
        extra={"job_id": str(state["job_id"])},
    )

    _complete_execution(execution, NodeExecutionStatus.COMPLETE)

    logger.info(
        "ReportGenerationNode complete (placeholder)",
        extra={"job_id": str(state["job_id"])},
    )

    return {
        "workflow_status": WorkflowStatus.COMPLETE,
        "node_execution_log": state["node_execution_log"],
        "errors": state["errors"],
    }


def _complete_execution(execution: NodeExecution, status: NodeExecutionStatus) -> None:
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
