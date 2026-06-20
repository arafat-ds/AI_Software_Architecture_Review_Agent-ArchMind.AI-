"""LangGraph node: ParseNode.

Responsibilities:
- Record node execution start and completion in the audit log
- Call ParserService to parse all repository files and produce a PCR
- Delete the cloned repository from disk after parsing completes (success or failure)
- Write parsed_code_representation to AnalysisState
- On failure: append WorkflowError and raise FatalNodeError (zero parseable
  files is fatal; partial failures with successful parses continue)

Output field: parsed_code_representation
"""

from __future__ import annotations

import shutil
from typing import Any

from core.workflow.state import (
    AnalysisState,
    append_workflow_error,
    begin_node_execution,
    require_field,
)
from services.parser import ParserService
from shared.exceptions.workflow_exceptions import FatalNodeError
from shared.logging.logger import get_logger
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution
from shared.types.manifest_types import RepositoryManifest

logger = get_logger(__name__)

_NODE_NAME = "ParseNode"
_parser_service = ParserService()


def parse_node(state: AnalysisState) -> dict[str, Any]:
    """Parse all repository files and produce a ParsedCodeRepresentation.

    Cleans up the cloned repository from disk after parsing, regardless of
    whether parsing succeeded or failed.

    Args:
        state: Current AnalysisState. Reads repository_manifest.

    Returns:
        Partial state dict containing:
        - parsed_code_representation: Populated PCR
        - workflow_status: Updated to ANALYZING_ARCHITECTURE on success
        - node_execution_log: Updated with completion record
        - errors: Unchanged on success; appended on partial/full failure

    Raises:
        FatalNodeError: When zero files were successfully parsed.
    """
    manifest: RepositoryManifest = require_field(state, "repository_manifest")  # type: ignore[assignment]

    execution = begin_node_execution(
        state, _NODE_NAME, output_field="parsed_code_representation"
    )

    logger.info("ParseNode started", extra={
        "job_id": str(state["job_id"]),
        "manifest_id": str(manifest.manifest_id),
        "analyzable_files": manifest.analyzable_file_count,
    })

    clone_path = manifest.temp_clone_path

    try:
        pcr = _parser_service.run(manifest)
        _complete_execution(execution, NodeExecutionStatus.COMPLETE)

        logger.info("ParseNode complete", extra={
            "job_id": str(state["job_id"]),
            "pcr_id": str(pcr.pcr_id),
            "files_parsed": pcr.parse_metadata.files_parsed_successfully,
        })

        return {
            "parsed_code_representation": pcr,
            "workflow_status": WorkflowStatus.ANALYZING_ARCHITECTURE,
            "node_execution_log": state["node_execution_log"],
            "errors": state["errors"],
        }

    except Exception as exc:
        error = append_workflow_error(
            state=state,
            node_name=_NODE_NAME,
            error_type=type(exc).__name__,
            message=str(exc),
            is_fatal=True,
        )
        _complete_execution(execution, NodeExecutionStatus.FAILED)

        logger.error("ParseNode failed", extra={
            "job_id": str(state["job_id"]),
            "error_type": error.error_type,
            "error_id": error.error_id,
        })

        raise FatalNodeError(
            node_name=_NODE_NAME,
            reason=str(exc),
            cause=exc,
        ) from exc

    finally:
        _delete_clone(clone_path, state["job_id"])


def _delete_clone(clone_path: str | None, job_id: object) -> None:
    if not clone_path:
        return
    try:
        shutil.rmtree(clone_path, ignore_errors=True)
        logger.info("Clone directory removed", extra={
            "job_id": str(job_id),
            "clone_path": clone_path,
        })
    except Exception as exc:
        logger.warning("Failed to remove clone directory", extra={
            "job_id": str(job_id),
            "clone_path": clone_path,
            "error": str(exc),
        })


def _complete_execution(execution: NodeExecution, status: NodeExecutionStatus) -> None:
    from datetime import datetime, timezone
    object.__setattr__(execution, "status", status)
    object.__setattr__(execution, "completed_at", datetime.now(tz=timezone.utc))
