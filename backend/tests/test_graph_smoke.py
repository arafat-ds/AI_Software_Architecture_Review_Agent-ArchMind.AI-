"""Smoke tests for Phase 3 / Phase 4: LangGraph workflow graph structure.

Phase 4 replaces ArchitectureAnalysisNode and SecurityAnalysisNode with
real service implementations that require environment variables (.env).
This suite therefore tests only the graph structure and the remaining
placeholder nodes (RecommendationNode, ReportGenerationNode).

Rule engine unit tests live in:
  - test_architecture_rule_engine.py
  - test_security_rule_engine.py
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.workflow.graph import clear_graph_cache, get_compiled_graph
from core.workflow.nodes.recommendation_node import recommendation_node
from core.workflow.nodes.report_node import report_generation_node
from core.workflow.state.analysis_state import create_initial_state
from shared.types.enums import NodeExecutionStatus, WorkflowStatus

_TEST_REPO_URL = "https://github.com/test/smoke-test-repo"

_EXPECTED_NODES = {
    "ingest_node",
    "parse_node",
    "architecture_analysis_node",
    "security_analysis_node",
    "recommendation_node",
    "report_generation_node",
}


@pytest.fixture(autouse=True)
def reset_graph_cache():
    """Clear the compiled graph cache before and after each test."""
    clear_graph_cache()
    yield
    clear_graph_cache()


def _make_state():
    """Return a minimal valid AnalysisState for placeholder node tests."""
    return create_initial_state(job_id=uuid4(), repo_url=_TEST_REPO_URL)


# ---------------------------------------------------------------------------
# Graph compilation and structure
# ---------------------------------------------------------------------------


def test_graph_compiles_without_error():
    """get_compiled_graph() must return a non-None CompiledStateGraph."""
    compiled = get_compiled_graph()
    assert compiled is not None


def test_graph_contains_all_six_nodes():
    """Compiled graph must contain exactly the six expected named nodes."""
    compiled = get_compiled_graph()
    graph_nodes = set(compiled.get_graph().nodes.keys())
    named_nodes = {n for n in graph_nodes if not n.startswith("__")}
    assert named_nodes == _EXPECTED_NODES


def test_get_compiled_graph_returns_singleton():
    """Repeated calls to get_compiled_graph() must return the same instance."""
    first = get_compiled_graph()
    second = get_compiled_graph()
    assert first is second


def test_clear_graph_cache_forces_rebuild():
    """clear_graph_cache() must cause get_compiled_graph() to return a new instance."""
    first = get_compiled_graph()
    clear_graph_cache()
    second = get_compiled_graph()
    assert first is not second


# ---------------------------------------------------------------------------
# Remaining placeholder node status transitions
# ---------------------------------------------------------------------------


def test_recommendation_node_advances_status_to_assembling():
    """recommendation_node must set workflow_status to ASSEMBLING."""
    state = _make_state()
    result = recommendation_node(state)
    assert result["workflow_status"] == WorkflowStatus.ASSEMBLING


def test_recommendation_node_records_complete_audit_entry():
    """recommendation_node must append a COMPLETE NodeExecution to the log."""
    state = _make_state()
    recommendation_node(state)

    log = state["node_execution_log"]
    assert len(log) == 1
    entry = log[0]
    assert entry.node_name == "RecommendationNode"
    assert entry.status == NodeExecutionStatus.COMPLETE
    assert entry.completed_at is not None
    assert entry.output_field_written == "recommendations_section"


def test_report_generation_node_advances_status_to_complete():
    """report_generation_node must set workflow_status to COMPLETE."""
    state = _make_state()
    result = report_generation_node(state)
    assert result["workflow_status"] == WorkflowStatus.COMPLETE


def test_report_generation_node_records_complete_audit_entry():
    """report_generation_node must append a COMPLETE NodeExecution to the log."""
    state = _make_state()
    report_generation_node(state)

    log = state["node_execution_log"]
    assert len(log) == 1
    entry = log[0]
    assert entry.node_name == "ReportGenerationNode"
    assert entry.status == NodeExecutionStatus.COMPLETE
    assert entry.completed_at is not None
    assert entry.output_field_written == "final_report_markdown"


def test_placeholder_nodes_do_not_modify_output_fields():
    """Placeholder nodes must leave their output fields as None in state."""
    state = _make_state()

    recommendation_node(state)
    assert state["recommendations_section"] is None

    report_generation_node(state)
    assert state["final_report_markdown"] is None
