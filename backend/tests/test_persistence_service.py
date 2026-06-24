"""Unit tests for PersistenceService.

Covers:
  - insert_report_with_retry: success on first attempt, retry on failure,
    exhaustion raises PersistenceWriteError, backoff timing (mocked)
  - update_job_complete: success, JobNotFoundError re-raised,
    APIError → PersistenceError, unexpected Exception → PersistenceError
  - run(): insert failure before update_job (insert is primary mission)

SupabaseClient is mocked. FinalReport is stubbed via MagicMock because
PersistenceService only accesses report.model_dump(mode="json"),
report.report_id, and report.job_id — no schema validation is exercised here.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from services.persistence.persistence_service import (
    PersistenceService,
    _BACKOFF_SECONDS,
    _MAX_RETRIES,
)
from shared.exceptions.persistence_exceptions import PersistenceError, PersistenceWriteError
from shared.exceptions.workflow_exceptions import JobNotFoundError
from shared.types.enums import JobStatus

_JOB_ID = uuid4()


def _make_service() -> tuple[PersistenceService, MagicMock]:
    mock_client = MagicMock()
    service = PersistenceService(supabase_client=mock_client)
    return service, mock_client


def _make_report() -> MagicMock:
    """Return a minimal report stub.

    PersistenceService only uses report.model_dump(mode="json"),
    report.report_id, and report.job_id — a MagicMock suffices.
    SupabaseClient.insert_report() is mocked so the dict content is irrelevant.
    """
    report_id = uuid4()
    mock = MagicMock()
    mock.report_id = report_id
    mock.job_id = _JOB_ID
    mock.model_dump.return_value = {
        "report_id": str(report_id),
        "job_id": str(_JOB_ID),
    }
    return mock


# ---------------------------------------------------------------------------
# insert_report — success on first attempt
# ---------------------------------------------------------------------------


def test_insert_report_success_on_first_attempt():
    service, mock_client = _make_service()
    report = _make_report()

    with patch("services.persistence.persistence_service.time.sleep") as mock_sleep:
        service._insert_report_with_retry(report)

    mock_client.insert_report.assert_called_once()
    mock_sleep.assert_not_called()


def test_insert_report_passes_model_dump_data():
    service, mock_client = _make_service()
    report = _make_report()

    with patch("services.persistence.persistence_service.time.sleep"):
        service._insert_report_with_retry(report)

    call_data = mock_client.insert_report.call_args[0][0]
    assert call_data["report_id"] == str(report.report_id)
    assert call_data["job_id"] == str(report.job_id)


# ---------------------------------------------------------------------------
# insert_report — retry on transient failure
# ---------------------------------------------------------------------------


def test_insert_report_retries_on_failure():
    service, mock_client = _make_service()
    report = _make_report()
    mock_client.insert_report.side_effect = [RuntimeError("transient"), None]

    with patch("services.persistence.persistence_service.time.sleep"):
        service._insert_report_with_retry(report)

    assert mock_client.insert_report.call_count == 2


def test_insert_report_sleeps_between_retries():
    service, mock_client = _make_service()
    report = _make_report()
    mock_client.insert_report.side_effect = [RuntimeError("fail1"), RuntimeError("fail2"), None]

    with patch("services.persistence.persistence_service.time.sleep") as mock_sleep:
        service._insert_report_with_retry(report)

    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(_BACKOFF_SECONDS[0])
    mock_sleep.assert_any_call(_BACKOFF_SECONDS[1])


# ---------------------------------------------------------------------------
# insert_report — exhaustion raises PersistenceWriteError
# ---------------------------------------------------------------------------


def test_insert_report_raises_persistence_write_error_after_exhaustion():
    service, mock_client = _make_service()
    report = _make_report()
    mock_client.insert_report.side_effect = RuntimeError("always fails")

    with patch("services.persistence.persistence_service.time.sleep"):
        with pytest.raises(PersistenceWriteError) as exc_info:
            service._insert_report_with_retry(report)

    assert exc_info.value.operation == "insert_report"
    assert exc_info.value.attempts == _MAX_RETRIES
    assert "always fails" in exc_info.value.reason


def test_insert_report_attempts_exactly_max_retries():
    service, mock_client = _make_service()
    report = _make_report()
    mock_client.insert_report.side_effect = RuntimeError("fail")

    with patch("services.persistence.persistence_service.time.sleep"):
        with pytest.raises(PersistenceWriteError):
            service._insert_report_with_retry(report)

    assert mock_client.insert_report.call_count == _MAX_RETRIES


def test_insert_report_no_sleep_on_final_attempt():
    service, mock_client = _make_service()
    report = _make_report()
    mock_client.insert_report.side_effect = RuntimeError("fail")

    with patch("services.persistence.persistence_service.time.sleep") as mock_sleep:
        with pytest.raises(PersistenceWriteError):
            service._insert_report_with_retry(report)

    assert mock_sleep.call_count == _MAX_RETRIES - 1


# ---------------------------------------------------------------------------
# update_job — success
# ---------------------------------------------------------------------------


def test_update_job_calls_supabase_update():
    service, mock_client = _make_service()
    report = _make_report()

    service._update_job_complete(_JOB_ID, report.report_id)

    mock_client.update_job.assert_called_once()
    call_kwargs = mock_client.update_job.call_args[0]
    assert call_kwargs[0] == _JOB_ID
    updates = call_kwargs[1]
    assert updates["status"] == JobStatus.COMPLETE.value
    assert updates["report_id"] == str(report.report_id)
    assert "completed_at" in updates


# ---------------------------------------------------------------------------
# update_job — JobNotFoundError re-raised as-is
# ---------------------------------------------------------------------------


def test_update_job_reraises_job_not_found_error():
    service, mock_client = _make_service()
    mock_client.update_job.side_effect = JobNotFoundError(job_id=str(_JOB_ID))

    with pytest.raises(JobNotFoundError):
        service._update_job_complete(_JOB_ID, uuid4())


def test_update_job_job_not_found_is_not_wrapped():
    service, mock_client = _make_service()
    mock_client.update_job.side_effect = JobNotFoundError(job_id=str(_JOB_ID))

    with pytest.raises(JobNotFoundError) as exc_info:
        service._update_job_complete(_JOB_ID, uuid4())

    assert not isinstance(exc_info.value, PersistenceError)


# ---------------------------------------------------------------------------
# update_job — APIError → PersistenceError
# ---------------------------------------------------------------------------


def test_update_job_api_error_raises_persistence_error():
    service, mock_client = _make_service()
    api_err = APIError({"message": "constraint violation", "code": "23505", "details": None, "hint": None})
    mock_client.update_job.side_effect = api_err

    with pytest.raises(PersistenceError):
        service._update_job_complete(_JOB_ID, uuid4())


def test_update_job_api_error_not_leaked_as_api_error():
    service, mock_client = _make_service()
    api_err = APIError({"message": "foreign key", "code": "23503", "details": None, "hint": None})
    mock_client.update_job.side_effect = api_err

    with pytest.raises(PersistenceError):
        service._update_job_complete(_JOB_ID, uuid4())

    # verify the caller only ever sees PersistenceError, not APIError
    # (APIError is a third-party exception; it must not leak past this service)


# ---------------------------------------------------------------------------
# update_job — unexpected Exception → PersistenceError
# ---------------------------------------------------------------------------


def test_update_job_unexpected_exception_raises_persistence_error():
    service, mock_client = _make_service()
    mock_client.update_job.side_effect = RuntimeError("unexpected DB failure")

    with pytest.raises(PersistenceError):
        service._update_job_complete(_JOB_ID, uuid4())


# ---------------------------------------------------------------------------
# run() — insert failure prevents update_job
# ---------------------------------------------------------------------------


def test_run_insert_failure_raises_before_update_job():
    service, mock_client = _make_service()
    report = _make_report()
    mock_client.insert_report.side_effect = RuntimeError("insert always fails")

    with patch("services.persistence.persistence_service.time.sleep"):
        with pytest.raises(PersistenceWriteError):
            service.run(report=report, job_id=_JOB_ID)

    mock_client.update_job.assert_not_called()


def test_run_success_calls_both_operations():
    service, mock_client = _make_service()
    report = _make_report()

    with patch("services.persistence.persistence_service.time.sleep"):
        service.run(report=report, job_id=_JOB_ID)

    mock_client.insert_report.assert_called_once()
    mock_client.update_job.assert_called_once()
