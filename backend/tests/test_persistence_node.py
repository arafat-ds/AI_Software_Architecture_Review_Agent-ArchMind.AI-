"""Unit tests for PersistenceNode.

Covers:
  - Success path: COMPLETE status, execution log COMPLETE, no errors
  - PersistenceWriteError (fatal): FatalNodeError raised, FAILED log, fatal error appended
  - JobNotFoundError (non-fatal): node returns COMPLETE, non-fatal error appended
  - PersistenceError (non-fatal): node returns COMPLETE, non-fatal error appended
  - NodeInputMissingError when final_report is None
  - Unrecognized exceptions propagate uncaught (node handles only domain types)

PersistenceService is mocked via singleton injection. No Supabase connection required.
FinalReport is stubbed via MagicMock: node only accesses report.report_id for logging
and passes report to the mocked service — no model_dump or schema validation occurs here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.workflow.state import AnalysisState, create_initial_state
from shared.exceptions.persistence_exceptions import PersistenceError, PersistenceWriteError
from shared.exceptions.workflow_exceptions import FatalNodeError, JobNotFoundError, NodeInputMissingError
from shared.types.enums import NodeExecutionStatus, WorkflowStatus

_JOB_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report() -> MagicMock:
    """Return a minimal report stub.

    PersistenceNode accesses report.report_id for logging and passes report
    to the mocked PersistenceService. MagicMock suffices.
    """
    mock = MagicMock()
    mock.report_id = uuid4()
    return mock


def _make_state(final_report: Any = None) -> AnalysisState:
    state = create_initial_state(job_id=_JOB_ID, repo_url="https://github.com/test/repo")
    if final_report is not None:
        state["final_report"] = final_report
    return state


def _run_node(state: AnalysisState, service_side_effect: Any = None) -> dict[str, Any]:
    """Run persistence_node with a mocked PersistenceService injected as singleton."""
    import core.workflow.nodes.persistence_node as node_module

    mock_service = MagicMock()
    if service_side_effect is not None:
        mock_service.run.side_effect = service_side_effect

    original = node_module._service
    node_module._service = mock_service
    try:
        return node_module.persistence_node(state)
    finally:
        node_module._service = original


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_persistence_node_success_returns_complete_status():
    state = _make_state(final_report=_make_report())
    result = _run_node(state)
    assert result["workflow_status"] == WorkflowStatus.COMPLETE


def test_persistence_node_success_no_errors_appended():
    state = _make_state(final_report=_make_report())
    result = _run_node(state)
    assert result["errors"] == []


def test_persistence_node_success_execution_log_has_one_complete_record():
    state = _make_state(final_report=_make_report())
    result = _run_node(state)
    log = result["node_execution_log"]
    assert len(log) == 1
    assert log[0].node_name == "PersistenceNode"
    assert log[0].status == NodeExecutionStatus.COMPLETE


def test_persistence_node_success_completed_at_is_set():
    state = _make_state(final_report=_make_report())
    result = _run_node(state)
    assert result["node_execution_log"][0].completed_at is not None


def test_persistence_node_success_calls_service_run():
    import core.workflow.nodes.persistence_node as node_module

    mock_service = MagicMock()
    report = _make_report()
    state = _make_state(final_report=report)

    original = node_module._service
    node_module._service = mock_service
    try:
        node_module.persistence_node(state)
    finally:
        node_module._service = original

    mock_service.run.assert_called_once_with(report=report, job_id=_JOB_ID)


# ---------------------------------------------------------------------------
# Fatal path — PersistenceWriteError
# ---------------------------------------------------------------------------


def test_persistence_node_write_error_raises_fatal_node_error():
    state = _make_state(final_report=_make_report())
    exc = PersistenceWriteError(operation="insert_report", reason="DB unavailable", attempts=3)

    with pytest.raises(FatalNodeError):
        _run_node(state, service_side_effect=exc)


def test_persistence_node_write_error_appends_fatal_workflow_error():
    state = _make_state(final_report=_make_report())
    exc = PersistenceWriteError(operation="insert_report", reason="timeout", attempts=3)

    with pytest.raises(FatalNodeError):
        _run_node(state, service_side_effect=exc)

    assert len(state["errors"]) == 1
    assert state["errors"][0].is_fatal is True
    assert state["errors"][0].node_name == "PersistenceNode"


def test_persistence_node_write_error_execution_log_marked_failed():
    """Fatal path sets FAILED on execution record before raising — check state directly."""
    state = _make_state(final_report=_make_report())
    exc = PersistenceWriteError(operation="insert_report", reason="error", attempts=3)

    with pytest.raises(FatalNodeError):
        _run_node(state, service_side_effect=exc)

    assert state["node_execution_log"][0].status == NodeExecutionStatus.FAILED


def test_persistence_node_write_error_fatal_node_error_contains_cause():
    state = _make_state(final_report=_make_report())
    exc = PersistenceWriteError(operation="insert_report", reason="disk full", attempts=3)

    with pytest.raises(FatalNodeError) as exc_info:
        _run_node(state, service_side_effect=exc)

    assert exc_info.value.cause is exc


# ---------------------------------------------------------------------------
# Non-fatal path — JobNotFoundError (standalone / no pre-created job row)
# ---------------------------------------------------------------------------


def test_persistence_node_job_not_found_returns_complete():
    state = _make_state(final_report=_make_report())
    exc = JobNotFoundError(job_id=str(_JOB_ID))
    result = _run_node(state, service_side_effect=exc)
    assert result["workflow_status"] == WorkflowStatus.COMPLETE


def test_persistence_node_job_not_found_appends_non_fatal_error():
    state = _make_state(final_report=_make_report())
    exc = JobNotFoundError(job_id=str(_JOB_ID))
    result = _run_node(state, service_side_effect=exc)

    assert len(result["errors"]) == 1
    assert result["errors"][0].is_fatal is False
    assert result["errors"][0].node_name == "PersistenceNode"


def test_persistence_node_job_not_found_execution_log_marked_complete():
    state = _make_state(final_report=_make_report())
    exc = JobNotFoundError(job_id=str(_JOB_ID))
    result = _run_node(state, service_side_effect=exc)

    assert result["node_execution_log"][0].status == NodeExecutionStatus.COMPLETE


# ---------------------------------------------------------------------------
# Non-fatal path — PersistenceError (update_job failure, already translated)
# ---------------------------------------------------------------------------


def test_persistence_node_persistence_error_returns_complete():
    state = _make_state(final_report=_make_report())
    exc = PersistenceError("update_job failed: connection reset")
    result = _run_node(state, service_side_effect=exc)
    assert result["workflow_status"] == WorkflowStatus.COMPLETE


def test_persistence_node_persistence_error_appends_non_fatal_error():
    state = _make_state(final_report=_make_report())
    exc = PersistenceError("update_job failed: connection reset")
    result = _run_node(state, service_side_effect=exc)

    assert len(result["errors"]) == 1
    assert result["errors"][0].is_fatal is False


def test_persistence_node_persistence_error_execution_log_marked_complete():
    state = _make_state(final_report=_make_report())
    exc = PersistenceError("update_job failed")
    result = _run_node(state, service_side_effect=exc)

    assert result["node_execution_log"][0].status == NodeExecutionStatus.COMPLETE


# ---------------------------------------------------------------------------
# PersistenceWriteError is a subclass of PersistenceError —
# verify it takes the FATAL path, not the non-fatal path
# ---------------------------------------------------------------------------


def test_persistence_node_write_error_is_fatal_not_non_fatal():
    """PersistenceWriteError must match the PersistenceWriteError handler, not PersistenceError."""
    state = _make_state(final_report=_make_report())
    exc = PersistenceWriteError(operation="insert_report", reason="out of disk", attempts=3)

    with pytest.raises(FatalNodeError):
        _run_node(state, service_side_effect=exc)

    assert state["errors"][0].is_fatal is True


# ---------------------------------------------------------------------------
# Missing input — final_report is None
# ---------------------------------------------------------------------------


def test_persistence_node_missing_final_report_raises_node_input_missing():
    """require_field() raises NodeInputMissingError when final_report is None."""
    state = _make_state(final_report=None)

    with pytest.raises(NodeInputMissingError):
        _run_node(state)


# ---------------------------------------------------------------------------
# Exception boundary — node handles only domain exception types
# ---------------------------------------------------------------------------


def test_persistence_node_unrecognized_exception_propagates_uncaught():
    """Node catch blocks cover PersistenceWriteError, JobNotFoundError, PersistenceError only.
    Any other exception propagates unchanged, proving no catch-all exists.
    """
    state = _make_state(final_report=_make_report())

    with pytest.raises(ConnectionError):
        _run_node(state, service_side_effect=ConnectionError("unexpected failure"))
