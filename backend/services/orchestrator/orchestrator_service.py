"""Analysis orchestrator service.

Architecture model: single-process, no distributed workers.
  This service runs the analysis workflow in a ThreadPoolExecutor within the
  same OS process as the FastAPI HTTP server. There is no Celery, RQ, or
  separate worker process.

  Implications:
  - In-flight jobs are lost if the API process restarts. Jobs left in RUNNING
    status after a restart are orphaned with no automatic recovery.
  - Concurrency is bounded by Settings.max_concurrent_jobs.
  - Suitable for MVP / single-instance deployment. Scale-out requires
    extracting the orchestrator into a separate worker process with a queue.

Responsibilities:
  create_job() — builds a PENDING JobRecord and inserts it to Supabase.
  run()        — blocking method called inside ThreadPoolExecutor:
                   1. Mark job RUNNING (fatal if fails).
                   2. Write initial current_stage="INGESTING" (non-fatal).
                   3. Create initial workflow state and stream the LangGraph graph.
                   4. After each node yields, write the next current_stage (non-fatal).
                   5. On FatalNodeError: mark job FAILED with node-scoped error_type.
                   6. On any other exception: mark job FAILED with sanitized message.
                   7. Never re-raise — the worker thread must not die with an
                      uncaught exception.

Responsibility boundary:
  PersistenceNode is solely responsible for marking the job COMPLETE and
  setting report_id in Supabase. The orchestrator does not set COMPLETE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from core.workflow.graph import get_compiled_graph
from core.workflow.state import create_initial_state
from infrastructure.supabase_client import SupabaseClient
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.logging.logger import get_logger
from shared.types.enums import JobStatus
from shared.types.job_types import JobRecord

logger = get_logger(__name__)

# Maps completed node name → current_stage value to write for the node that starts next.
# Each entry is written after the keyed node's chunk is yielded (meaning that node has
# completed and the next is starting).
# persistence_node is excluded: PersistenceNode writes COMPLETE to Supabase itself.
_NEXT_STAGE_MAP: dict[str, str] = {
    "ingest_node":                "PARSING",
    "parse_node":                 "ANALYZING_ARCHITECTURE",
    "architecture_analysis_node": "ANALYZING_SECURITY",
    "security_analysis_node":     "RETRIEVING_RAG",
    "rag_retrieval_node":         "SYNTHESIZING",
    "recommendation_node":        "ASSEMBLING",
    "report_generation_node":     "PERSISTING",
}


class AnalysisOrchestrator:
    """Manages job lifecycle and invokes the LangGraph analysis workflow.

    Stateless with respect to individual jobs — safe to share as a singleton.
    """

    def __init__(self, supabase_client: SupabaseClient) -> None:
        self._supabase = supabase_client

    # ------------------------------------------------------------------
    # Job creation (called synchronously from the API route handler)
    # ------------------------------------------------------------------

    def create_job(self, job_id: UUID, repo_url: str, repo_name: str) -> None:
        """Build a PENDING JobRecord and persist it to Supabase.

        Called synchronously by the POST /jobs route handler before the
        background task is submitted to the executor.

        Args:
            job_id: Pre-generated UUID for this job.
            repo_url: GitHub HTTPS URL already validated by the request schema.
            repo_name: Repository name extracted from repo_url by the caller.

        Raises:
            APIError: Supabase write failed. Propagated to the route handler,
                which returns a 500 to the client.
        """
        job_record = JobRecord(
            job_id=job_id,
            repo_url=repo_url,
            repo_name=repo_name,
            status=JobStatus.PENDING,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._supabase.insert_job(job_record)
        logger.info("AnalysisOrchestrator: job created", extra={
            "job_id": str(job_id),
            "repo_url": repo_url,
        })

    # ------------------------------------------------------------------
    # Workflow execution (called inside ThreadPoolExecutor)
    # ------------------------------------------------------------------

    def run(self, job_id: UUID, repo_url: str) -> None:
        """Execute the full analysis workflow for a submitted job.

        Blocking. Must be called inside a ThreadPoolExecutor, not on the
        async event loop thread.

        Exception contract: this method NEVER raises. All exceptions are
        caught, logged, and translated into a Supabase FAILED status update.
        The worker thread must never terminate with an uncaught exception.

        On success: no-op with respect to job status — PersistenceNode has
        already written COMPLETE and report_id to Supabase during graph.stream().

        Args:
            job_id: UUID of the job created by create_job().
            repo_url: GitHub HTTPS URL for the repository to analyse.
        """
        # Step 1: Transition to RUNNING.
        # If this update fails, the job remains PENDING in Supabase.
        # Attempt to mark FAILED and abort — do not invoke the graph.
        try:
            self._supabase.update_job(job_id, {
                "status": JobStatus.RUNNING.value,
                "started_at": datetime.now(tz=timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.error("AnalysisOrchestrator: failed to mark job RUNNING", extra={
                "job_id": str(job_id),
                "error": str(exc),
            })
            self._attempt_fail_update(
                job_id=job_id,
                error_type="OrchestratorSetupError",
                error_message="Failed to transition job to RUNNING before workflow start.",
            )
            return

        # Step 1b: Write initial stage. Best-effort — a missing current_stage column
        # or any Supabase error must not prevent the workflow from starting.
        self._attempt_stage_update(job_id, "INGESTING")

        # Step 2: Stream the LangGraph graph, writing current_stage after each
        # node completes. Stage updates are non-fatal; workflow continues on failure.
        logger.info("AnalysisOrchestrator: starting workflow", extra={"job_id": str(job_id)})
        try:
            state = create_initial_state(job_id=job_id, repo_url=repo_url)
            for chunk in get_compiled_graph().stream(state):
                node_name = next(iter(chunk))
                next_stage = _NEXT_STAGE_MAP.get(node_name)
                if next_stage:
                    self._attempt_stage_update(job_id, next_stage)
            logger.info("AnalysisOrchestrator: workflow completed successfully", extra={
                "job_id": str(job_id),
            })

        except FatalNodeError as exc:
            logger.error("AnalysisOrchestrator: FatalNodeError during workflow", extra={
                "job_id": str(job_id),
                "node_name": exc.node_name,
                "reason": exc.reason,
            })
            self._attempt_fail_update(
                job_id=job_id,
                error_type=f"{exc.node_name}.FatalNodeError",
                error_message=exc.reason,
            )

        except Exception as exc:
            logger.exception("AnalysisOrchestrator: unexpected exception during workflow", extra={
                "job_id": str(job_id),
                "error_type": type(exc).__name__,
            })
            self._attempt_fail_update(
                job_id=job_id,
                error_type=type(exc).__name__,
                error_message="Internal workflow error. Check server logs.",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _attempt_stage_update(self, job_id: UUID, stage: str) -> None:
        """Write current_stage to Supabase. Best-effort — never raises.

        A missing current_stage column (pre-migration deployment) or any
        Supabase error is caught, logged as a warning, and ignored. The
        workflow always continues regardless of stage update success.

        Args:
            job_id: UUID of the job to update.
            stage: WorkflowStatus string value to write (e.g. "INGESTING").
        """
        try:
            self._supabase.update_job(job_id, {"current_stage": stage})
            logger.debug("AnalysisOrchestrator: stage updated", extra={
                "job_id": str(job_id),
                "stage": stage,
            })
        except Exception as exc:
            logger.warning(
                "AnalysisOrchestrator: stage update failed (non-fatal)",
                extra={"job_id": str(job_id), "stage": stage, "error": str(exc)},
            )

    def _attempt_fail_update(
        self,
        job_id: UUID,
        error_type: str,
        error_message: str,
    ) -> None:
        """Attempt to write FAILED status to Supabase.

        If this update itself fails (secondary failure), logs the error and
        returns silently. Never raises — the caller (run()) must not propagate
        any exception to the worker thread.

        Args:
            job_id: UUID of the job to mark as FAILED.
            error_type: Short exception class or scoped identifier for the failure.
            error_message: Human-readable failure description. Must not contain
                raw exception chains or internal stack trace content.
        """
        try:
            self._supabase.update_job(job_id, {
                "status": JobStatus.FAILED.value,
                "error_type": error_type,
                "error_message": error_message,
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
            })
            logger.info("AnalysisOrchestrator: job marked FAILED", extra={
                "job_id": str(job_id),
                "error_type": error_type,
            })
        except Exception as secondary_exc:
            logger.error(
                "AnalysisOrchestrator: secondary failure — could not mark job FAILED",
                extra={
                    "job_id": str(job_id),
                    "secondary_error": str(secondary_exc),
                    "original_error_type": error_type,
                },
            )
