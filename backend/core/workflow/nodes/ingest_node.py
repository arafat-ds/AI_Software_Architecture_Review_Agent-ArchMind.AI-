"""LangGraph node: IngestNode.

Responsibilities:
- Record node execution start and completion in the audit log
- Call IngestionService to clone the repository and build a RepositoryManifest
- Write repository_manifest to AnalysisState
- On failure: append WorkflowError and raise FatalNodeError (ingestion failure
  is always fatal — no repository, no analysis)

Output field: repository_manifest
"""

from __future__ import annotations

from typing import Any

from core.workflow.state import (
    AnalysisState,
    append_workflow_error,
    begin_node_execution,
)
from services.ingestion import IngestionService
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.logging.logger import get_logger
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution

logger = get_logger(__name__)

_NODE_NAME = "IngestNode"
_ingestion_service = IngestionService()


def ingest_node(state: AnalysisState) -> dict[str, Any]:
    """Clone the repository and build a RepositoryManifest.

    Args:
        state: Current AnalysisState. Reads job_id and repo_url.

    Returns:
        Partial state dict containing:
        - repository_manifest: Populated RepositoryManifest
        - workflow_status: INGESTING → updated to PARSING on success
        - node_execution_log: Updated with completion record
        - errors: Unchanged on success; appended on failure

    Raises:
        FatalNodeError: Always on ingestion failure.
    """
    execution = begin_node_execution(
        state, _NODE_NAME, output_field="repository_manifest"
    )

    logger.info("IngestNode started", extra={
        "job_id": str(state["job_id"]),
        "repo_url": state["repo_url"],
    })

    try:
        manifest = _ingestion_service.run(
            job_id=state["job_id"],
            repo_url=state["repo_url"],
        )
        _complete_execution(execution, NodeExecutionStatus.COMPLETE)

        logger.info("IngestNode complete", extra={
            "job_id": str(state["job_id"]),
            "manifest_id": str(manifest.manifest_id),
            "analyzable_files": manifest.analyzable_file_count,
        })

        return {
            "repository_manifest": manifest,
            "workflow_status": WorkflowStatus.PARSING,
            "node_execution_log": state["node_execution_log"],
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

        logger.error("IngestNode failed", extra={
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
    from datetime import datetime, timezone
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
