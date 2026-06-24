"""Smoke tests for the LangGraph workflow graph structure.

Tests only graph compilation, node registration, and singleton caching.
Deterministic rule engine logic is covered in:
  - test_architecture_rule_engine.py
  - test_security_rule_engine.py
  - test_recommendation_rule_engine.py
Section builder logic is covered in:
  - test_report_section_builders.py

All six nodes now have full service implementations requiring environment
variables (.env). Direct node invocation with empty state would raise
FatalNodeError and is not tested here.
"""

from __future__ import annotations

import pytest

from core.workflow.graph import clear_graph_cache, get_compiled_graph

_EXPECTED_NODES = {
    "ingest_node",
    "parse_node",
    "architecture_analysis_node",
    "security_analysis_node",
    "rag_retrieval_node",
    "recommendation_node",
    "report_generation_node",
    "persistence_node",
}


@pytest.fixture(autouse=True)
def reset_graph_cache():
    """Clear the compiled graph cache before and after each test."""
    clear_graph_cache()
    yield
    clear_graph_cache()


def test_graph_compiles_without_error():
    """get_compiled_graph() must return a non-None CompiledStateGraph."""
    compiled = get_compiled_graph()
    assert compiled is not None


def test_graph_contains_all_eight_nodes():
    """Compiled graph must contain exactly the eight expected named nodes."""
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
