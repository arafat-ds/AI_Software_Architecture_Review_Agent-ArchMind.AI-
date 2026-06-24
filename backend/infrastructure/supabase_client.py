"""Supabase persistence client wrapper.

Wraps the supabase-py client for job record and report persistence.
All table names are defined as constants here. No SQL or query logic
lives outside this module.

Callers must not import supabase directly — all Supabase-specific logic
is contained here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client, create_client

from shared.exceptions.workflow_exceptions import JobNotFoundError
from shared.logging.logger import get_logger
from shared.types.job_types import JobRecord

logger = get_logger(__name__)

_TABLE_JOBS: str = "jobs"
_TABLE_REPORTS: str = "reports"


class SupabaseClient:
    """Thin wrapper around the Supabase Postgres client.

    Exposes only the operations used by the ArchMind AI job lifecycle.
    Does not expose raw query builders or execute arbitrary SQL.
    """

    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)

    def insert_job(self, job_record: JobRecord) -> None:
        """Persist a new job record to the jobs table.

        Args:
            job_record: Fully validated JobRecord to insert.

        Raises:
            APIError: Supabase returned an error response.
        """
        data = job_record.model_dump(mode="json")
        try:
            self._client.table(_TABLE_JOBS).insert(data).execute()
            logger.info("Job inserted", extra={"job_id": str(job_record.job_id)})
        except APIError as exc:
            logger.error("Supabase insert_job failed", extra={
                "job_id": str(job_record.job_id),
                "error": str(exc),
            })
            raise

    def update_job(self, job_id: UUID, updates: dict[str, Any]) -> None:
        """Apply a partial update to an existing job record.

        Args:
            job_id: UUID of the job to update.
            updates: Dict of column names to new values. Caller is
                responsible for serializing enums and datetimes to JSON-safe
                types before passing (use str(value) or .isoformat()).

        Raises:
            JobNotFoundError: No row matched the given job_id.
            APIError: Supabase returned an error response.
        """
        try:
            response = (
                self._client.table(_TABLE_JOBS)
                .update(updates)
                .eq("job_id", str(job_id))
                .execute()
            )
            if not response.data:
                raise JobNotFoundError(job_id=job_id)
            logger.info("Job updated", extra={
                "job_id": str(job_id),
                "fields": list(updates.keys()),
            })
        except JobNotFoundError:
            raise
        except APIError as exc:
            logger.error("Supabase update_job failed", extra={
                "job_id": str(job_id),
                "error": str(exc),
            })
            raise

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        """Fetch a job record by ID.

        Args:
            job_id: UUID of the job to retrieve.

        Returns:
            Raw row dict from Supabase, or None if not found.

        Raises:
            APIError: Supabase returned an error response.
        """
        try:
            response = (
                self._client.table(_TABLE_JOBS)
                .select("*")
                .eq("job_id", str(job_id))
                .maybe_single()
                .execute()
            )
            return response.data
        except APIError as exc:
            logger.error("Supabase get_job failed", extra={
                "job_id": str(job_id),
                "error": str(exc),
            })
            raise

    def get_report(self, report_id: UUID) -> dict[str, Any] | None:
        """Fetch a persisted report by report_id.

        Args:
            report_id: UUID of the FinalReport to retrieve.

        Returns:
            Raw row dict from Supabase, or None if not found.

        Raises:
            APIError: Supabase returned an error response.
        """
        try:
            response = (
                self._client.table(_TABLE_REPORTS)
                .select("*")
                .eq("report_id", str(report_id))
                .maybe_single()
                .execute()
            )
            return response.data
        except APIError as exc:
            logger.error("Supabase get_report failed", extra={
                "report_id": str(report_id),
                "error": str(exc),
            })
            raise

    def insert_report(self, report_data: dict[str, Any]) -> str:
        """Persist a final report and return its report_id.

        Args:
            report_data: Serialized report dict. Must include a ``report_id``
                key with a string UUID value.

        Returns:
            The ``report_id`` string from the inserted row.

        Raises:
            ValueError: ``report_data`` is missing the ``report_id`` key.
            APIError: Supabase returned an error response.
        """
        report_id = report_data.get("report_id")
        if not report_id:
            raise ValueError("report_data must contain a non-empty 'report_id' key.")

        try:
            self._client.table(_TABLE_REPORTS).upsert(report_data).execute()
            logger.info("Report upserted", extra={"report_id": str(report_id)})
            return str(report_id)
        except APIError as exc:
            logger.error("Supabase insert_report failed", extra={
                "report_id": str(report_id),
                "error": str(exc),
            })
            raise
