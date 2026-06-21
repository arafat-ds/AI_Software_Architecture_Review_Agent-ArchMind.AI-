"""AnalysisState — the central LangGraph workflow state contract.

AnalysisState is a TypedDict passed through all eight nodes of the
ArchMind AI analysis workflow. Each node receives the full state, processes
its assigned inputs, and returns a partial dict containing only the fields
it writes. LangGraph merges node output back into the state before passing
it to the next node.

OWNERSHIP RULES (enforced by architecture, not by code):
- Each node writes exactly one named output field (plus errors and
  node_execution_log via the helpers below).
- No node overwrites a field written by a prior node.
- State exists only in memory during workflow execution.
- State is discarded after PersistenceNode completes.
- State is never persisted to Supabase.

NODE → FIELD WRITE MAP:
  IngestNode            → repository_manifest
  ParseNode             → parsed_code_representation (also nulls temp_clone_path)
  ArchitectureAnalysisNode → architecture_section
  SecurityAnalysisNode  → security_section
  RAGRetrievalNode      → rag_context
  RecommendationNode    → recommendations_section
  ReportAssemblyNode    → final_report, final_report_markdown
  PersistenceNode       → (writes to Supabase; no state field)

Dependency rule: core/workflow/state may import from shared/ and config/.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict
from uuid import UUID

from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import NodeExecutionStatus, WorkflowStatus
from shared.types.job_types import NodeExecution, WorkflowError
from shared.types.manifest_types import RepositoryManifest
from shared.types.pcr_types import ParsedCodeRepresentation
from shared.types.rag_types import RAGContext
from shared.types.report_types import FinalReport, RecommendationSection


class AnalysisState(TypedDict, total=True):
    """Shared state object for the ArchMind AI LangGraph workflow.

    All fields are declared here. Fields that are populated by specific nodes
    are typed as Optional[T] and initialised to None by create_initial_state().

    Use create_initial_state() to construct the initial state at the start of
    each workflow run. Never construct AnalysisState manually.

    TypedDict notes:
    - total=True means all keys must be present. All optional fields are
      initialised to None rather than being absent. This prevents KeyError
      on any state field access in nodes.
    - LangGraph node functions return dict[str, Any] containing only the keys
      they update. LangGraph merges the return value into the current state.
    """

    # ------------------------------------------------------------------
    # Required — set at workflow initialisation
    # ------------------------------------------------------------------

    job_id: UUID
    """Parent job identifier. Immutable after initialisation."""

    repo_url: str
    """Repository URL as submitted by the user. Immutable after initialisation."""

    workflow_status: WorkflowStatus
    """Current execution status. Transitions strictly forward. Updated by each node."""

    created_at: datetime
    """UTC timestamp when the workflow was initialised. Immutable after initialisation."""

    errors: list[WorkflowError]
    """Accumulated error records from all nodes. Empty list at initialisation.
    Nodes append to this list on non-fatal failures. Fatal failures also append
    before terminating the workflow."""

    node_execution_log: list[NodeExecution]
    """Ordered execution records for each node. Empty list at initialisation.
    Each node appends a NodeExecution record when it starts and updates it
    when it completes."""

    # ------------------------------------------------------------------
    # Conditionally populated — None until the producing node completes
    # ------------------------------------------------------------------

    repository_manifest: RepositoryManifest | None
    """Set by IngestNode. None until IngestNode completes successfully."""

    parsed_code_representation: ParsedCodeRepresentation | None
    """Set by ParseNode. None until ParseNode completes successfully.
    ParseNode also sets repository_manifest.temp_clone_path = None after
    deleting the cloned repository from disk."""

    architecture_section: ArchitectureSection | None
    """Set by ArchitectureAnalysisNode. None until architecture analysis completes."""

    security_section: SecuritySection | None
    """Set by SecurityAnalysisNode. None until security analysis completes."""

    rag_context: RAGContext | None
    """Set by RAGRetrievalNode. None until RAG retrieval completes.
    May contain empty retrieved_chunks if Qdrant returned no results above threshold."""

    recommendations_section: RecommendationSection | None
    """Set by RecommendationNode. None until recommendation synthesis completes."""

    final_report: FinalReport | None
    """Set by ReportAssemblyNode. None until report assembly completes.
    Contains the fully validated FinalReport Pydantic model."""

    final_report_markdown: str | None
    """Set by ReportAssemblyNode. None until report assembly completes.
    Contains final_report.markdown_content as a convenience field."""


def create_initial_state(job_id: UUID, repo_url: str) -> AnalysisState:
    """Create an AnalysisState with all required fields initialised.

    All conditionally-populated fields are set to None. The workflow_status
    is set to INITIALIZED. Errors and execution log are empty lists.

    This is the only authorised way to create a new AnalysisState.
    Never construct AnalysisState directly using dict literals.

    Args:
        job_id: UUID of the parent job record in Supabase.
        repo_url: The validated GitHub repository URL for this analysis run.

    Returns:
        A fully initialised AnalysisState ready to be passed to the LangGraph
        compiled graph's invoke() call.

    Example:
        state = create_initial_state(job_id=uuid4(), repo_url="https://github.com/owner/repo")
        result = compiled_graph.invoke(state)
    """
    return AnalysisState(
        job_id=job_id,
        repo_url=repo_url,
        workflow_status=WorkflowStatus.INITIALIZED,
        created_at=datetime.now(tz=timezone.utc),
        errors=[],
        node_execution_log=[],
        repository_manifest=None,
        parsed_code_representation=None,
        architecture_section=None,
        security_section=None,
        rag_context=None,
        recommendations_section=None,
        final_report=None,
        final_report_markdown=None,
    )


def require_field(state: AnalysisState, field_name: str) -> object:
    """Assert that a required state field is populated before a node reads it.

    Called at the start of each node that depends on a prior node's output.
    Raises NodeInputMissingError immediately if the field is None, preventing
    silent failures from propagating through the workflow.

    Args:
        state: The current AnalysisState.
        field_name: The string name of the field to validate (e.g. "repository_manifest").

    Returns:
        The field value (guaranteed non-None).

    Raises:
        NodeInputMissingError: If the named field is None in the current state.

    Example (in a node function):
        manifest = require_field(state, "repository_manifest")
    """
    from shared.exceptions.workflow_exceptions import NodeInputMissingError

    value = state.get(field_name)  # type: ignore[call-overload]
    if value is None:
        raise NodeInputMissingError(
            node_name="<caller>",
            missing_field=field_name,
        )
    return value


def append_workflow_error(
    state: AnalysisState,
    node_name: str,
    error_type: str,
    message: str,
    is_fatal: bool,
) -> WorkflowError:
    """Create a WorkflowError record and append it to state.errors.

    Handles error_id generation using the current length of the errors list
    to produce a unique scoped identifier in ERR-NNN format.

    Args:
        state: The current AnalysisState (mutated in place for the errors list).
        node_name: Name of the node where the error occurred.
        error_type: Python exception class name.
        message: Human-readable error description.
        is_fatal: True when the workflow will be terminated after this error.

    Returns:
        The created WorkflowError record (also appended to state.errors).

    Note:
        LangGraph nodes should not mutate the state TypedDict in place for
        their primary output field. However, appending to the errors list is
        a controlled exception to support non-fatal error accumulation.
        The errors list is always returned in the node's partial state dict.
    """
    error_index = len(state["errors"]) + 1
    error_id = f"ERR-{error_index:03d}"

    error = WorkflowError(
        error_id=error_id,
        node_name=node_name,
        error_type=error_type,
        message=message,
        timestamp=datetime.now(tz=timezone.utc),
        is_fatal=is_fatal,
    )
    state["errors"].append(error)
    return error


def begin_node_execution(
    state: AnalysisState,
    node_name: str,
    output_field: str | None = None,
) -> NodeExecution:
    """Record that a node has started execution in the audit log.

    Creates a NodeExecution record with status RUNNING and appends it to
    state.node_execution_log. Returns the record so the node can update it
    when execution completes.

    Args:
        state: The current AnalysisState.
        node_name: Name of the node starting execution.
        output_field: Name of the AnalysisState field this node will write to.

    Returns:
        The NodeExecution record in RUNNING status.
    """
    record = NodeExecution(
        node_name=node_name,
        started_at=datetime.now(tz=timezone.utc),
        completed_at=None,
        status=NodeExecutionStatus.RUNNING,
        output_field_written=output_field,
    )
    state["node_execution_log"].append(record)
    return record
