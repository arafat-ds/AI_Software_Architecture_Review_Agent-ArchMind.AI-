"""LangGraph node: PersistenceNode.

Responsibilities:
- Read final_report from state via require_field()
- Call PersistenceService.run() to upsert report and mark job COMPLETE
- insert_report() failure is FATAL — raises FatalNodeError after retries exhausted
- update_job() failure is NON-FATAL — logs warning, node succeeds
- Return workflow_status=COMPLETE on success

PersistenceNode imports only domain exceptions. postgrest.APIError never
leaks past PersistenceService (translation boundary rule).

Service is lazily initialised on first invocation to avoid loading
settings at import time (which would break tests without .env files).

Output field: none (writes to Supabase; AnalysisState is unchanged)
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
from services.persistence import PersistenceService
from shared.exceptions.persistence_exceptions import PersistenceError, PersistenceWriteError
from shared.exceptions.workflow_exceptions import FatalNodeError, JobNotFoundError
from shared.logging.logger import get_logger
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution
from shared.types.report_types import FinalReport

logger = get_logger(__name__)

_NODE_NAME = "PersistenceNode"
_service: PersistenceService | None = None


def _get_service() -> PersistenceService:
    """Return the PersistenceService singleton, initialising it on first call."""
    global _service
    if _service is None:
        from config.settings import get_settings
        from infrastructure.supabase_client import SupabaseClient

        settings = get_settings()
        _service = PersistenceService(
            supabase_client=SupabaseClient(
                url=settings.supabase_url,
                key=settings.supabase_key,
            )
        )
    return _service


def persistence_node(state: AnalysisState) -> dict[str, Any]:
    """Persist FinalReport to Supabase and mark job COMPLETE.

    insert_report() is the primary mission — failure is fatal after all
    retry attempts because a report that cannot be saved is unrecoverable.

    update_job() is best-effort — JobNotFoundError (standalone mode, no
    pre-created job row) and PersistenceError (Supabase write failure) are
    logged as warnings. The node still succeeds because the report is saved.

    Args:
        state: Current AnalysisState. Reads final_report and job_id.

    Returns:
        Partial state dict containing:
        - workflow_status: Advanced to COMPLETE on success
        - node_execution_log: Updated with completion record
        - errors: Unchanged on success; appended on fatal failure

    Raises:
        FatalNodeError: insert_report() failed on all retry attempts.
    """
    report: FinalReport = require_field(state, "final_report")  # type: ignore[assignment]

    execution = begin_node_execution(state, _NODE_NAME, output_field=None)

    logger.info("PersistenceNode started", extra={
        "job_id": str(state["job_id"]),
        "report_id": str(report.report_id),
    })

    try:
        _get_service().run(report=report, job_id=state["job_id"])

    except PersistenceWriteError as exc:
        error = append_workflow_error(
            state=state,
            node_name=_NODE_NAME,
            error_type=type(exc).__name__,
            message=str(exc),
            is_fatal=True,
        )
        _complete_execution(execution, NodeExecutionStatus.FAILED)

        logger.error("PersistenceNode fatal: insert_report exhausted retries", extra={
            "job_id": str(state["job_id"]),
            "report_id": str(report.report_id),
            "error_id": error.error_id,
            "operation": exc.operation,
            "attempts": exc.attempts,
        })

        raise FatalNodeError(
            node_name=_NODE_NAME,
            reason=str(exc),
            cause=exc,
        ) from exc

    except JobNotFoundError as exc:
        append_workflow_error(
            state=state,
            node_name=_NODE_NAME,
            error_type=type(exc).__name__,
            message=str(exc),
            is_fatal=False,
        )
        logger.warning(
            "PersistenceNode: update_job skipped — no job row found "
            "(standalone mode; report is persisted)",
            extra={
                "job_id": str(state["job_id"]),
                "report_id": str(report.report_id),
            },
        )

    except PersistenceError as exc:
        append_workflow_error(
            state=state,
            node_name=_NODE_NAME,
            error_type=type(exc).__name__,
            message=str(exc),
            is_fatal=False,
        )
        logger.warning(
            "PersistenceNode: update_job failed (non-fatal; report is persisted)",
            extra={
                "job_id": str(state["job_id"]),
                "report_id": str(report.report_id),
                "error": str(exc),
            },
        )

    _complete_execution(execution, NodeExecutionStatus.COMPLETE)

    logger.info("PersistenceNode complete", extra={
        "job_id": str(state["job_id"]),
        "report_id": str(report.report_id),
    })

    return {
        "workflow_status": WorkflowStatus.COMPLETE,
        "node_execution_log": state["node_execution_log"],
        "errors": state["errors"],
    }


def _complete_execution(execution: NodeExecution, status: NodeExecutionStatus) -> None:
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
