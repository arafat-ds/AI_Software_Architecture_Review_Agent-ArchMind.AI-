"""Exceptions raised during LangGraph workflow orchestration.

These exceptions represent failures in the workflow graph itself, as distinct
from failures in the underlying services (ingestion, parsing, LLM, RAG).

Dependency rule: no imports from other application modules.
"""

from __future__ import annotations


class WorkflowException(Exception):
    """Base exception for all LangGraph workflow orchestration failures.

    Distinct from the WorkflowError data contract (shared/types/job_types.py),
    which is a structured audit record stored in AnalysisState. This exception
    class is raised and caught during Python execution.
    """

    def __init__(self, message: str, node_name: str | None = None) -> None:
        self.node_name = node_name
        super().__init__(message)


class FatalNodeError(WorkflowException):
    """Raised when a LangGraph node encounters an unrecoverable error.

    Signals to the orchestrator that the workflow must be terminated and the
    job must be marked FAILED. The originating exception is recorded in the
    error message for debugging.
    """

    def __init__(self, node_name: str, reason: str, cause: Exception | None = None) -> None:
        msg = f"Fatal error in node '{node_name}': {reason}"
        if cause is not None:
            msg += f" Caused by: {type(cause).__name__}: {cause}"
        super().__init__(msg, node_name=node_name)
        self.reason = reason
        self.cause = cause


class NodeInputMissingError(WorkflowException):
    """Raised when a node's required input field is None in AnalysisState.

    Indicates either a programming error in the graph wiring (a node was
    invoked before its dependency node completed) or a non-fatal upstream
    failure that left a required field unpopulated.
    """

    def __init__(self, node_name: str, missing_field: str) -> None:
        super().__init__(
            f"Node '{node_name}' requires AnalysisState.{missing_field} but it is None. "
            "Ensure all dependency nodes complete before this node executes.",
            node_name=node_name,
        )
        self.missing_field = missing_field


class WorkflowStateError(WorkflowException):
    """Raised when an invalid state transition is attempted.

    Enforces the forward-only workflow_status transition rule. No node may
    move the workflow status backward or to an invalid state.
    """

    def __init__(self, current_status: str, attempted_status: str) -> None:
        super().__init__(
            f"Invalid workflow status transition: '{current_status}' → '{attempted_status}'. "
            "Status transitions are strictly forward and cannot be reversed."
        )
        self.current_status = current_status
        self.attempted_status = attempted_status


class JobNotFoundError(WorkflowException):
    """Raised when a job_id lookup in Supabase returns no matching record.

    Typically indicates a race condition or a stale job_id reference.
    """

    def __init__(self, job_id: str) -> None:
        super().__init__(
            f"No job record found for job_id '{job_id}'. "
            "The job may have been deleted or the ID is incorrect."
        )
        self.job_id = job_id
