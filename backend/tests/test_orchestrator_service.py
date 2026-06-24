"""Unit tests for AnalysisOrchestrator.

Covers:
  - create_job(): inserts PENDING JobRecord with correct fields
  - run(): RUNNING update precedes graph invocation
  - run(): success path — no FAILED update (PersistenceNode owns COMPLETE)
  - run(): FatalNodeError → FAILED with node-scoped error_type and exc.reason
  - run(): unexpected exception → FAILED with sanitized error_message
  - run(): never re-raises any exception (worker thread safety)
  - run(): RUNNING update failure → FAILED update attempted, graph not invoked
  - _attempt_fail_update(): secondary Supabase failure does not raise

SupabaseClient and get_compiled_graph are mocked.
No .env required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from services.orchestrator.orchestrator_service import AnalysisOrchestrator
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.types.enums import JobStatus

_JOB_ID = uuid4()
_REPO_URL = "https://github.com/test/repo"
_REPO_NAME = "repo"

_GRAPH_PATCH = "services.orchestrator.orchestrator_service.get_compiled_graph"


def _make_orchestrator() -> tuple[AnalysisOrchestrator, MagicMock]:
    mock_client = MagicMock()
    return AnalysisOrchestrator(supabase_client=mock_client), mock_client


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


def test_create_job_calls_insert_job_once():
    orchestrator, mock_client = _make_orchestrator()
    orchestrator.create_job(_JOB_ID, _REPO_URL, _REPO_NAME)
    mock_client.insert_job.assert_called_once()


def test_create_job_inserts_pending_status():
    orchestrator, mock_client = _make_orchestrator()
    orchestrator.create_job(_JOB_ID, _REPO_URL, _REPO_NAME)
    job_record = mock_client.insert_job.call_args[0][0]
    assert job_record.status == JobStatus.PENDING


def test_create_job_sets_correct_repo_url():
    orchestrator, mock_client = _make_orchestrator()
    orchestrator.create_job(_JOB_ID, _REPO_URL, _REPO_NAME)
    job_record = mock_client.insert_job.call_args[0][0]
    assert job_record.repo_url == _REPO_URL


def test_create_job_sets_correct_repo_name():
    orchestrator, mock_client = _make_orchestrator()
    orchestrator.create_job(_JOB_ID, _REPO_URL, _REPO_NAME)
    job_record = mock_client.insert_job.call_args[0][0]
    assert job_record.repo_name == _REPO_NAME


def test_create_job_sets_correct_job_id():
    orchestrator, mock_client = _make_orchestrator()
    orchestrator.create_job(_JOB_ID, _REPO_URL, _REPO_NAME)
    job_record = mock_client.insert_job.call_args[0][0]
    assert job_record.job_id == _JOB_ID


# ---------------------------------------------------------------------------
# run() — success path
# ---------------------------------------------------------------------------


def test_run_updates_job_to_running_before_graph_invocation():
    orchestrator, mock_client = _make_orchestrator()
    call_order = []

    def track_update(job_id, updates):
        call_order.append(("update_job", updates.get("status")))

    def track_invoke(state):
        call_order.append(("invoke", None))

    mock_client.update_job.side_effect = track_update
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = track_invoke

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    assert call_order[0] == ("update_job", JobStatus.RUNNING.value)
    assert call_order[1] == ("invoke", None)


def test_run_success_does_not_call_failed_update():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    # Only one update_job call: RUNNING. No FAILED update.
    assert mock_client.update_job.call_count == 1
    update_args = mock_client.update_job.call_args[0][1]
    assert update_args["status"] == JobStatus.RUNNING.value


def test_run_success_invokes_graph():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    mock_graph.invoke.assert_called_once()


def test_run_success_passes_state_with_correct_job_id():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    state_passed = mock_graph.invoke.call_args[0][0]
    assert state_passed["job_id"] == _JOB_ID
    assert state_passed["repo_url"] == _REPO_URL


# ---------------------------------------------------------------------------
# run() — FatalNodeError path
# ---------------------------------------------------------------------------


def test_run_fatal_node_error_updates_job_to_failed():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="PersistenceNode", reason="DB write exhausted")
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_call = mock_client.update_job.call_args_list[-1]
    assert failed_call[0][1]["status"] == JobStatus.FAILED.value


def test_run_fatal_node_error_uses_node_scoped_error_type():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="IngestNode", reason="clone failed")
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert failed_updates["error_type"] == "IngestNode.FatalNodeError"


def test_run_fatal_node_error_uses_reason_as_error_message():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="ParseNode", reason="zero parseable files")
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert failed_updates["error_message"] == "zero parseable files"


def test_run_fatal_node_error_does_not_use_full_exc_str():
    """str(FatalNodeError) includes the cause chain — must not reach Supabase."""
    orchestrator, mock_client = _make_orchestrator()
    cause = RuntimeError("internal detail")
    exc = FatalNodeError(node_name="ArchNode", reason="arch failed", cause=cause)
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert "internal detail" not in failed_updates["error_message"]
    assert "Caused by" not in failed_updates["error_message"]


def test_run_fatal_node_error_sets_completed_at():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="SecurityNode", reason="llm failure")
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert "completed_at" in failed_updates


# ---------------------------------------------------------------------------
# run() — unexpected exception path
# ---------------------------------------------------------------------------


def test_run_unexpected_exception_updates_job_to_failed():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("unexpected crash")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_call = mock_client.update_job.call_args_list[-1]
    assert failed_call[0][1]["status"] == JobStatus.FAILED.value


def test_run_unexpected_exception_uses_sanitized_error_message():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("sensitive internal path /etc/secrets")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert "sensitive internal path" not in failed_updates["error_message"]
    assert failed_updates["error_message"] == "Internal workflow error. Check server logs."


def test_run_unexpected_exception_uses_exception_class_name_as_error_type():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = ConnectionError("db unreachable")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert failed_updates["error_type"] == "ConnectionError"


# ---------------------------------------------------------------------------
# run() — never re-raises (worker thread safety)
# ---------------------------------------------------------------------------


def test_run_does_not_raise_on_fatal_node_error():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = FatalNodeError(node_name="N", reason="fail")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise


def test_run_does_not_raise_on_unexpected_exception():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("crash")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise


def test_run_does_not_raise_when_running_update_fails():
    orchestrator, mock_client = _make_orchestrator()
    mock_client.update_job.side_effect = Exception("supabase unreachable")

    with patch(_GRAPH_PATCH) as mock_get_graph:
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise

    # Graph must not be invoked if RUNNING update failed
    mock_get_graph.return_value.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# run() — RUNNING update failure: graph not invoked, FAILED attempted
# ---------------------------------------------------------------------------


def test_run_running_update_failure_does_not_invoke_graph():
    orchestrator, mock_client = _make_orchestrator()
    mock_client.update_job.side_effect = Exception("connection lost")

    with patch(_GRAPH_PATCH) as mock_get_graph:
        orchestrator.run(_JOB_ID, _REPO_URL)

    mock_get_graph.return_value.invoke.assert_not_called()


def test_run_running_update_failure_attempts_failed_update():
    orchestrator, mock_client = _make_orchestrator()
    # First call (RUNNING) raises; second call (FAILED) succeeds
    mock_client.update_job.side_effect = [Exception("connection lost"), None]

    with patch(_GRAPH_PATCH):
        orchestrator.run(_JOB_ID, _REPO_URL)

    assert mock_client.update_job.call_count == 2
    second_call_updates = mock_client.update_job.call_args_list[1][0][1]
    assert second_call_updates["status"] == JobStatus.FAILED.value


# ---------------------------------------------------------------------------
# _attempt_fail_update() — secondary failure does not raise
# ---------------------------------------------------------------------------


def test_attempt_fail_update_secondary_supabase_failure_does_not_raise():
    orchestrator, mock_client = _make_orchestrator()
    mock_client.update_job.side_effect = Exception("supabase completely down")

    # Must not raise regardless
    orchestrator._attempt_fail_update(
        job_id=_JOB_ID,
        error_type="TestError",
        error_message="test failure",
    )
