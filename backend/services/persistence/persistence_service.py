"""Persistence service.

Serialises and persists FinalReport to Supabase, then attempts to update
the parent job record to COMPLETE.

Exception translation boundary:
  This service is the translation layer between third-party Supabase/PostgREST
  exceptions (APIError) and domain exceptions (PersistenceError subclasses).
  No APIError leaks past this module — PersistenceNode imports only domain types.

Retry strategy (insert_report only):
  - Max 3 attempts, linear backoff: 1s, 2s, 3s.
  - insert_report() uses upsert semantics in SupabaseClient — safe to retry
    with the same report_id (idempotent on primary key conflict).
  - Raises PersistenceWriteError after all attempts exhausted.

update_job() failure model:
  - JobNotFoundError → re-raised as-is (domain exception, non-fatal in node).
  - APIError or any other exception → wrapped into PersistenceError (non-fatal in node).
  - PersistenceNode decides fatality; this service just translates exceptions.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

from postgrest.exceptions import APIError

from infrastructure.supabase_client import SupabaseClient
from shared.exceptions.persistence_exceptions import PersistenceError, PersistenceWriteError
from shared.exceptions.workflow_exceptions import JobNotFoundError
from shared.logging.logger import get_logger
from shared.types.report_types import FinalReport

logger = get_logger(__name__)

_MAX_RETRIES: int = 3
_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 3.0)


class PersistenceService:
    """Persists FinalReport and updates job lifecycle in Supabase.

    Stateless — safe to call run() multiple times.
    """

    def __init__(self, supabase_client: SupabaseClient) -> None:
        self._supabase = supabase_client

    def run(self, report: FinalReport, job_id: UUID) -> None:
        """Persist the FinalReport and update job status to COMPLETE.

        insert_report() is the primary mission — fatal on failure after retries.
        update_job() is best-effort — exceptions are surfaced for the node to
        handle as non-fatal warnings.

        Args:
            report: Fully assembled and validated FinalReport from ReportAssemblyNode.
            job_id: Parent analysis job UUID from AnalysisState.

        Raises:
            PersistenceWriteError: insert_report() failed on all retry attempts.
                PersistenceNode treats this as fatal.
            JobNotFoundError: update_job() found no matching job row. Indicates
                Phase 7 standalone mode (no API pre-created the job record).
                PersistenceNode treats this as a non-fatal warning.
            PersistenceError: update_job() raised an APIError or unexpected exception.
                PersistenceNode treats this as a non-fatal warning.
        """
        self._insert_report_with_retry(report)
        self._update_job_complete(job_id, report.report_id)

    # ------------------------------------------------------------------
    # insert_report with retry — fatal on exhaustion
    # ------------------------------------------------------------------

    def _insert_report_with_retry(self, report: FinalReport) -> None:
        """Serialise and upsert FinalReport. Retries on any failure.

        Uses upsert semantics (SupabaseClient.insert_report calls .upsert()),
        making repeated calls with the same report_id idempotent.

        Raises:
            PersistenceWriteError: all retry attempts failed.
        """
        report_data = report.model_dump(mode="json")
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                self._supabase.insert_report(report_data)
                logger.info("PersistenceService: report persisted", extra={
                    "report_id": str(report.report_id),
                    "job_id": str(report.job_id),
                    "attempt": attempt,
                })
                return

            except Exception as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_SECONDS[attempt - 1]
                    logger.warning("PersistenceService: insert_report failed, retrying", extra={
                        "report_id": str(report.report_id),
                        "attempt": attempt,
                        "wait_seconds": wait,
                        "error": str(exc),
                    })
                    time.sleep(wait)
                else:
                    logger.error("PersistenceService: insert_report exhausted retries", extra={
                        "report_id": str(report.report_id),
                        "attempts": _MAX_RETRIES,
                        "error": str(exc),
                    })

        raise PersistenceWriteError(
            operation="insert_report",
            reason=str(last_error),
            attempts=_MAX_RETRIES,
        )

    # ------------------------------------------------------------------
    # update_job — best-effort, exceptions translated for node
    # ------------------------------------------------------------------

    def _update_job_complete(self, job_id: UUID, report_id: object) -> None:
        """Attempt to mark the job COMPLETE in Supabase.

        Translates third-party APIError into PersistenceError (domain).
        Re-raises JobNotFoundError as-is (already a domain exception).
        PersistenceNode handles both as non-fatal warnings.

        Raises:
            JobNotFoundError: no row found for job_id (re-raised unchanged).
            PersistenceError: APIError or unexpected exception from update_job().
        """
        from shared.types.enums import JobStatus

        completed_at = datetime.now(tz=timezone.utc).isoformat()
        try:
            self._supabase.update_job(job_id, {
                "status": JobStatus.COMPLETE.value,
                "report_id": str(report_id),
                "completed_at": completed_at,
            })
            logger.info("PersistenceService: job marked COMPLETE", extra={
                "job_id": str(job_id),
                "report_id": str(report_id),
            })

        except JobNotFoundError:
            raise

        except APIError as exc:
            raise PersistenceError(
                f"update_job failed for job_id '{job_id}': {exc}"
            ) from exc

        except Exception as exc:
            raise PersistenceError(
                f"update_job unexpected failure for job_id '{job_id}': {exc}"
            ) from exc
