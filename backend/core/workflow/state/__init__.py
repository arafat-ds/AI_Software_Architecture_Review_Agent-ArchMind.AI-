"""Workflow state package.

Exports the AnalysisState TypedDict and its associated factory and helper
functions. All LangGraph nodes import from this package.
"""

from core.workflow.state.analysis_state import (
    AnalysisState,
    append_workflow_error,
    begin_node_execution,
    create_initial_state,
    require_field,
)

__all__ = [
    "AnalysisState",
    "append_workflow_error",
    "begin_node_execution",
    "create_initial_state",
    "require_field",
]
