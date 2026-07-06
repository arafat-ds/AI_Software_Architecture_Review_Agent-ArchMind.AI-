"""Unit tests for SupabaseClient.list_jobs() and recover_orphaned_jobs().

All Supabase interactions are mocked via MagicMock on the internal _client.
No real Supabase connection or .env required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from postgrest.exceptions import APIError

from config.constants import ORPHAN_RECOVERY_ERROR_MESSAGE
from infrastructure.supabase_client import SupabaseClient
from shared.types.enums import JobStatus

_SUPABASE_PATCH = "infrastructure.supabase_client.create_client"


def _make_client() -> tuple[SupabaseClient, MagicMock]:
    """Return a SupabaseClient with a mocked internal _client."""
    with patch(_SUPABASE_PATCH) as mock_create:
        client = SupabaseClient(url="https://fake.supabase.co", key="fake-key")
    client._client = MagicMock()
    return client, client._client


def _api_error() -> APIError:
    return APIError({"message": "simulated supabase error", "code": "PGRST000"})


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------


def test_list_jobs_no_filter_does_not_call_eq_on_status():
    client, mock_inner = _make_client()
    mock_table = mock_inner.table.return_value
    mock_select = mock_table.select.return_value
    mock_order = mock_select.order.return_value
    mock_order.execute.return_value = MagicMock(data=[{"job_id": "abc"}])

    result = client.list_jobs()

    mock_table.select.assert_called_once_with("*")
    # eq() must NOT be called when no filter is passed
    mock_select.eq.assert_not_called()
    assert result == [{"job_id": "abc"}]


def test_list_jobs_with_status_filter_applies_eq():
    client, mock_inner = _make_client()
    mock_table = mock_inner.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_eq.order.return_value.execute.return_value = MagicMock(data=[])

    client.list_jobs(status_filter="RUNNING")

    mock_select.eq.assert_called_once_with("status", "RUNNING")


def test_list_jobs_returns_empty_list_when_data_is_empty():
    client, mock_inner = _make_client()
    mock_inner.table.return_value.select.return_value.order.return_value.execute.return_value = (
        MagicMock(data=[])
    )

    result = client.list_jobs()

    assert result == []


def test_list_jobs_returns_all_rows_from_response():
    client, mock_inner = _make_client()
    rows = [{"job_id": "a"}, {"job_id": "b"}, {"job_id": "c"}]
    mock_inner.table.return_value.select.return_value.order.return_value.execute.return_value = (
        MagicMock(data=rows)
    )

    result = client.list_jobs()

    assert result == rows


def test_list_jobs_propagates_api_error():
    client, mock_inner = _make_client()
    mock_inner.table.return_value.select.return_value.order.return_value.execute.side_effect = (
        _api_error()
    )

    with pytest.raises(APIError):
        client.list_jobs()


# ---------------------------------------------------------------------------
# recover_orphaned_jobs — no running jobs
# ---------------------------------------------------------------------------


def test_recover_orphaned_jobs_returns_zero_when_no_running_jobs():
    client, _ = _make_client()
    with patch.object(client, "list_jobs", return_value=[]):
        result = client.recover_orphaned_jobs()
    assert result == 0


def test_recover_orphaned_jobs_does_not_call_table_when_no_running_jobs():
    client, mock_inner = _make_client()
    with patch.object(client, "list_jobs", return_value=[]):
        client.recover_orphaned_jobs()
    # No update query should be issued
    mock_inner.table.assert_not_called()


# ---------------------------------------------------------------------------
# recover_orphaned_jobs — with running jobs
# ---------------------------------------------------------------------------


def _make_running_jobs(*job_ids: str) -> list[dict]:
    return [{"job_id": jid, "status": "RUNNING"} for jid in job_ids]


def _setup_update_response(mock_inner: MagicMock, data: list) -> MagicMock:
    """Wire mock_inner.table().update().eq().eq().execute() → data."""
    chain = mock_inner.table.return_value
    chain.update.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=data)
    )
    return chain


def test_recover_orphaned_jobs_returns_correct_count():
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1", "id-2", "id-3")
    _setup_update_response(mock_inner, data=[{"job_id": "x"}])

    with patch.object(client, "list_jobs", return_value=jobs):
        result = client.recover_orphaned_jobs()

    assert result == 3


def test_recover_orphaned_jobs_updates_each_job_individually():
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1", "id-2")
    _setup_update_response(mock_inner, data=[{"job_id": "x"}])

    with patch.object(client, "list_jobs", return_value=jobs):
        client.recover_orphaned_jobs()

    assert mock_inner.table.call_count == 2


def test_recover_orphaned_jobs_sets_status_to_failed():
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1")
    _setup_update_response(mock_inner, data=[{"job_id": "id-1"}])

    with patch.object(client, "list_jobs", return_value=jobs):
        client.recover_orphaned_jobs()

    update_payload = mock_inner.table.return_value.update.call_args[0][0]
    assert update_payload["status"] == JobStatus.FAILED.value


def test_recover_orphaned_jobs_uses_orphan_recovery_error_message():
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1")
    _setup_update_response(mock_inner, data=[{"job_id": "id-1"}])

    with patch.object(client, "list_jobs", return_value=jobs):
        client.recover_orphaned_jobs()

    update_payload = mock_inner.table.return_value.update.call_args[0][0]
    assert update_payload["error_message"] == ORPHAN_RECOVERY_ERROR_MESSAGE


def test_recover_orphaned_jobs_uses_orphaned_job_error_type():
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1")
    _setup_update_response(mock_inner, data=[{"job_id": "id-1"}])

    with patch.object(client, "list_jobs", return_value=jobs):
        client.recover_orphaned_jobs()

    update_payload = mock_inner.table.return_value.update.call_args[0][0]
    assert update_payload["error_type"] == "OrphanedJobError"


def test_recover_orphaned_jobs_does_not_call_update_job():
    """recover_orphaned_jobs must use a raw conditional query, not update_job()."""
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1")
    _setup_update_response(mock_inner, data=[{"job_id": "id-1"}])

    with patch.object(client, "list_jobs", return_value=jobs), \
         patch.object(client, "update_job") as mock_update_job:
        client.recover_orphaned_jobs()

    mock_update_job.assert_not_called()


# ---------------------------------------------------------------------------
# recover_orphaned_jobs — status-guard and fault isolation
# ---------------------------------------------------------------------------


def test_recover_orphaned_jobs_skips_job_when_no_rows_updated():
    """When response.data is empty, the job changed status — not counted."""
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1")
    _setup_update_response(mock_inner, data=[])

    with patch.object(client, "list_jobs", return_value=jobs):
        result = client.recover_orphaned_jobs()

    assert result == 0


def test_recover_orphaned_jobs_continues_after_individual_api_error():
    """APIError on one job must not prevent recovery of the remaining jobs."""
    client, mock_inner = _make_client()
    jobs = _make_running_jobs("id-1", "id-2")

    call_count = 0

    def update_side_effect(*args, **kwargs):
        return mock_inner.table.return_value.update.return_value

    # First job raises APIError; second succeeds
    eq_chain = mock_inner.table.return_value.update.return_value.eq.return_value.eq.return_value
    eq_chain.execute.side_effect = [
        _api_error(),
        MagicMock(data=[{"job_id": "id-2"}]),
    ]

    with patch.object(client, "list_jobs", return_value=jobs):
        result = client.recover_orphaned_jobs()

    assert result == 1
