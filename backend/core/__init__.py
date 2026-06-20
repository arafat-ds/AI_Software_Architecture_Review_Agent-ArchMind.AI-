"""Core orchestration package for ArchMind AI.

Contains the LangGraph workflow graph, node definitions, shared state schema,
and job lifecycle management.

Dependency rule: core/ may import from agents/, services/, rag/,
infrastructure/, shared/, and config/. core/ must not be imported by
agents/, services/, rag/, or infrastructure/.
"""
