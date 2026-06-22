"""RAG query builder.

Converts ArchitectureSection weaknesses and SecuritySection findings into
a typed list of RAGQuery objects for Qdrant retrieval.

One query per ArchitectureWeakness — targets ARCHITECTURE domain.
One query per SecurityFinding    — targets SECURITY domain.

Candidates are sorted by severity descending before truncation at
MAX_RAG_QUERIES, so highest-severity items always get a retrieval slot.

No I/O, no LLM calls — pure deterministic transformation.
"""

from __future__ import annotations

from config.constants import MAX_RAG_QUERIES
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import RAGDomain
from shared.types.rag_types import RAGQuery


def build_rag_queries(
    architecture_section: ArchitectureSection,
    security_section: SecuritySection,
    max_queries: int = MAX_RAG_QUERIES,
) -> list[RAGQuery]:
    """Build RAGQuery list from architecture weaknesses and security findings.

    Args:
        architecture_section: Populated ArchitectureSection from workflow state.
        security_section: Populated SecuritySection from workflow state.
        max_queries: Maximum number of queries to generate. Defaults to
            MAX_RAG_QUERIES from config/constants.py.

    Returns:
        list[RAGQuery] with sequential Q-NNN identifiers, sorted by severity
        descending, truncated to max_queries.
        Empty list when both sections have no weaknesses/findings.
    """
    # Candidates: (severity_int, query_text, domain, source_ids)
    candidates: list[tuple[int, str, RAGDomain, list[str]]] = []

    for weakness in architecture_section.weaknesses:
        candidates.append((
            int(weakness.severity),
            weakness.rag_query_hint,
            RAGDomain.ARCHITECTURE,
            [weakness.weakness_id],
        ))

    for finding in security_section.findings:
        candidates.append((
            int(finding.severity),
            finding.rag_query_hint,
            RAGDomain.SECURITY,
            [finding.finding_id],
        ))

    candidates.sort(key=lambda c: c[0], reverse=True)
    candidates = candidates[:max_queries]

    queries: list[RAGQuery] = []
    for i, (_, query_text, domain, source_ids) in enumerate(candidates, start=1):
        queries.append(RAGQuery(
            query_id=f"Q-{i:03d}",
            query_text=query_text,
            source_domain=domain,
            source_finding_ids=source_ids,
        ))

    return queries
