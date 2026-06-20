"""ArchMind AI LangGraph workflow graph construction.

Builds and compiles the six-node analysis workflow as a LangGraph
StateGraph. The compiled graph is cached as a process-lifetime singleton.

Workflow sequence (Phase 3):
    IngestNode → ParseNode → ArchitectureAnalysisNode →
    SecurityAnalysisNode → RecommendationNode → ReportGenerationNode

Phase 4 will replace placeholder nodes with full agent services.
Phase 5 will insert RAGRetrievalNode between SecurityAnalysisNode
and RecommendationNode.

Usage:
    from core.workflow.graph import get_compiled_graph

    graph = get_compiled_graph()
    result = graph.invoke(initial_state)
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from core.workflow.nodes.architecture_node import architecture_analysis_node
from core.workflow.nodes.ingest_node import ingest_node
from core.workflow.nodes.parse_node import parse_node
from core.workflow.nodes.recommendation_node import recommendation_node
from core.workflow.nodes.report_node import report_generation_node
from core.workflow.nodes.security_node import security_analysis_node
from core.workflow.state.analysis_state import AnalysisState


@lru_cache(maxsize=1)
def get_compiled_graph() -> CompiledStateGraph:
    """Build and compile the ArchMind AI analysis workflow graph.

    The compiled graph is created once and cached for the process lifetime.
    Subsequent calls return the same instance.

    In tests, call clear_graph_cache() before each test that needs a fresh
    graph instance, or between tests that modify graph configuration.

    Returns:
        CompiledStateGraph ready to invoke with an AnalysisState dict.

    Example:
        state = create_initial_state(job_id=uuid4(), repo_url="https://github.com/owner/repo")
        result = get_compiled_graph().invoke(state)
    """
    graph: StateGraph = StateGraph(AnalysisState)

    graph.add_node("ingest_node", ingest_node)
    graph.add_node("parse_node", parse_node)
    graph.add_node("architecture_analysis_node", architecture_analysis_node)
    graph.add_node("security_analysis_node", security_analysis_node)
    graph.add_node("recommendation_node", recommendation_node)
    graph.add_node("report_generation_node", report_generation_node)

    graph.set_entry_point("ingest_node")
    graph.add_edge("ingest_node", "parse_node")
    graph.add_edge("parse_node", "architecture_analysis_node")
    graph.add_edge("architecture_analysis_node", "security_analysis_node")
    graph.add_edge("security_analysis_node", "recommendation_node")
    graph.add_edge("recommendation_node", "report_generation_node")
    graph.add_edge("report_generation_node", END)

    return graph.compile()


def clear_graph_cache() -> None:
    """Clear the compiled graph singleton cache.

    Forces get_compiled_graph() to rebuild the graph on the next call.
    Use in tests to ensure isolation between test cases.

    Example:
        def teardown_function():
            clear_graph_cache()
    """
    get_compiled_graph.cache_clear()
