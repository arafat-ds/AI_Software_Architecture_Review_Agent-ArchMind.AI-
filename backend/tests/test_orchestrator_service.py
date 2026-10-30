"""Unit tests for AnalysisOrchestrator.

Covers:
  - create_job(): inserts PENDING JobRecord with correct fields
  - run(): RUNNING update precedes graph streaming
  - run(): RUNNING update includes status and started_at (not current_stage)
  - run(): initial stage INGESTING written after RUNNING update (best-effort)
  - run(): success path — no FAILED update (PersistenceNode owns COMPLETE)
  - run(): stage written after each node yields
  - run(): stage update failure is non-fatal (workflow continues)
  - run(): FatalNodeError → FAILED with node-scoped error_type and exc.reason
  - run(): unexpected exception → FAILED with sanitized error_message
  - run(): never re-raises any exception (worker thread safety)
  - run(): RUNNING update failure → FAILED update attempted, graph not streamed
  - run(): FatalNodeError mid-stream (after node yields) → FAILED
  - run(): stage written before mid-stream exception propagates
  - run(): mid-stream unexpected exception → does not raise
  - _attempt_fail_update(): secondary Supabase failure does not raise

SupabaseClient and get_compiled_graph are mocked.
No .env required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

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


def test_run_updates_job_to_running_before_graph_streaming():
    orchestrator, mock_client = _make_orchestrator()
    call_order = []

    def track_update(_job_id, updates):
        call_order.append(("update_job", updates.get("status")))

    def track_stream(_state):
        call_order.append(("stream", None))
        return iter([])

    mock_client.update_job.side_effect = track_update
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = track_stream

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    # RUNNING update must be the first update_job call
    assert call_order[0] == ("update_job", JobStatus.RUNNING.value)
    # stream() call must come after all update_job calls for RUNNING
    stream_pos = call_order.index(("stream", None))
    assert stream_pos > 0


def test_run_running_update_does_not_include_current_stage():
    """RUNNING update must not include current_stage — column may not exist yet."""
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([])

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    running_update = mock_client.update_job.call_args_list[0][0][1]
    assert "status" in running_update
    assert "current_stage" not in running_update


def test_run_success_does_not_call_failed_update():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([])

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    for call_args in mock_client.update_job.call_args_list:
        updates = call_args[0][1]
        assert updates.get("status") != JobStatus.FAILED.value


def test_run_success_streams_graph():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([])

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    mock_graph.stream.assert_called_once()


def test_run_success_passes_state_with_correct_job_id():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([])

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    state_passed = mock_graph.stream.call_args[0][0]
    assert state_passed["job_id"] == _JOB_ID
    assert state_passed["repo_url"] == _REPO_URL


# ---------------------------------------------------------------------------
# run() — stage tracking
# ---------------------------------------------------------------------------


def test_run_writes_initial_ingesting_stage_after_running_update():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([])

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    # Second update_job call (after RUNNING) should be the initial stage
    calls = mock_client.update_job.call_args_list
    assert len(calls) >= 2
    initial_stage_update = calls[1][0][1]
    assert initial_stage_update == {"current_stage": "INGESTING"}


def test_run_writes_next_stage_after_node_completes():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([{"ingest_node": {}}])

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    all_updates = [c[0][1] for c in mock_client.update_job.call_args_list]
    stage_only = [u for u in all_updates if list(u.keys()) == ["current_stage"]]
    # Expect: INGESTING (initial) then PARSING (after ingest_node)
    assert stage_only[0]["current_stage"] == "INGESTING"
    assert stage_only[1]["current_stage"] == "PARSING"


def test_run_stage_update_failure_is_nonfatal():
    """Supabase error on a stage update must not prevent workflow completion."""
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([{"ingest_node": {}}])

    # First call (RUNNING) succeeds; all subsequent calls (stage updates) fail
    from postgrest.exceptions import APIError
    _err = APIError({"message": "column current_stage not found", "code": "42703", "details": None, "hint": None})
    mock_client.update_job.side_effect = [None, _err, _err]

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise


# ---------------------------------------------------------------------------
# run() — FatalNodeError path
# ---------------------------------------------------------------------------


def test_run_fatal_node_error_updates_job_to_failed():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="PersistenceNode", reason="DB write exhausted")
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_call = mock_client.update_job.call_args_list[-1]
    assert failed_call[0][1]["status"] == JobStatus.FAILED.value


def test_run_fatal_node_error_uses_node_scoped_error_type():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="IngestNode", reason="clone failed")
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert failed_updates["error_type"] == "IngestNode.FatalNodeError"


def test_run_fatal_node_error_uses_reason_as_error_message():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="ParseNode", reason="zero parseable files")
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = exc

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
    mock_graph.stream.side_effect = exc

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert "internal detail" not in failed_updates["error_message"]
    assert "Caused by" not in failed_updates["error_message"]


def test_run_fatal_node_error_sets_completed_at():
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="SecurityNode", reason="llm failure")
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = exc

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
    mock_graph.stream.side_effect = RuntimeError("unexpected crash")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_call = mock_client.update_job.call_args_list[-1]
    assert failed_call[0][1]["status"] == JobStatus.FAILED.value


def test_run_unexpected_exception_uses_sanitized_error_message():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = RuntimeError("sensitive internal path /etc/secrets")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    failed_updates = mock_client.update_job.call_args_list[-1][0][1]
    assert "sensitive internal path" not in failed_updates["error_message"]
    assert failed_updates["error_message"] == "Internal workflow error. Check server logs."


def test_run_unexpected_exception_uses_exception_class_name_as_error_type():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = ConnectionError("db unreachable")

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
    mock_graph.stream.side_effect = FatalNodeError(node_name="N", reason="fail")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise


def test_run_does_not_raise_on_unexpected_exception():
    orchestrator, mock_client = _make_orchestrator()
    mock_graph = MagicMock()
    mock_graph.stream.side_effect = RuntimeError("crash")

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise


def test_run_does_not_raise_when_running_update_fails():
    orchestrator, mock_client = _make_orchestrator()
    mock_client.update_job.side_effect = Exception("supabase unreachable")

    with patch(_GRAPH_PATCH) as mock_get_graph:
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise

    # Graph must not be streamed if RUNNING update failed
    mock_get_graph.return_value.stream.assert_not_called()


# ---------------------------------------------------------------------------
# run() — RUNNING update failure: graph not streamed, FAILED attempted
# ---------------------------------------------------------------------------


def test_run_running_update_failure_does_not_stream_graph():
    orchestrator, mock_client = _make_orchestrator()
    mock_client.update_job.side_effect = Exception("connection lost")

    with patch(_GRAPH_PATCH) as mock_get_graph:
        orchestrator.run(_JOB_ID, _REPO_URL)

    mock_get_graph.return_value.stream.assert_not_called()


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
# run() — mid-stream exception (node yields, then later node raises)
# ---------------------------------------------------------------------------


def test_run_fatal_node_error_mid_stream_updates_job_to_failed():
    """FatalNodeError raised after at least one node has already yielded."""
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="ParseNode", reason="parse failed mid-stream")

    def _yielding_stream(_):
        yield {"ingest_node": {}}
        raise exc

    mock_graph = MagicMock()
    mock_graph.stream.side_effect = _yielding_stream

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    last_update = mock_client.update_job.call_args_list[-1][0][1]
    assert last_update["status"] == JobStatus.FAILED.value
    assert last_update["error_message"] == "parse failed mid-stream"
    assert last_update["error_type"] == "ParseNode.FatalNodeError"


def test_run_mid_stream_exception_stage_was_updated_before_failure():
    """Stage update for PARSING was written (ingest_node yielded) before exception."""
    orchestrator, mock_client = _make_orchestrator()
    exc = FatalNodeError(node_name="ParseNode", reason="parse failed")

    def _yielding_stream(_):
        yield {"ingest_node": {}}
        raise exc

    mock_graph = MagicMock()
    mock_graph.stream.side_effect = _yielding_stream

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)

    all_updates = [c[0][1] for c in mock_client.update_job.call_args_list]
    stage_only = [u for u in all_updates if list(u.keys()) == ["current_stage"]]
    assert any(u["current_stage"] == "PARSING" for u in stage_only)


def test_run_mid_stream_unexpected_exception_does_not_raise():
    """Worker thread must not propagate unexpected mid-stream exceptions."""
    orchestrator, mock_client = _make_orchestrator()

    def _yielding_stream(_):
        yield {"ingest_node": {}}
        raise RuntimeError("unexpected mid-stream crash")

    mock_graph = MagicMock()
    mock_graph.stream.side_effect = _yielding_stream

    with patch(_GRAPH_PATCH, return_value=mock_graph):
        orchestrator.run(_JOB_ID, _REPO_URL)  # must not raise


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
