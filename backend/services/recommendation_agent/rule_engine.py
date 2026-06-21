"""Recommendation Agent deterministic rule engine.

Maps ArchitectureSection weaknesses and SecuritySection findings to
RecommendationSpec entries with rule-assigned priority and category.

No LLM calls. No external I/O. All classification is deterministic.

Priority rules (from Priority enum docstring in enums.py):
  CRITICAL or HIGH severity → P1
  MEDIUM severity           → P2
  LOW or INFO severity      → P3

Category rules:
  From ArchitectureWeakness → RecommendationCategory.ARCHITECTURE
  From SecurityFinding      → RecommendationCategory.SECURITY

MAX_RECOMMENDATIONS cap: all P1 first, then P2, then P3.
Lowest-priority items are dropped when the cap is reached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config.constants import MAX_RECOMMENDATIONS
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import Priority, RecommendationCategory, Severity
from shared.types.rag_types import RAGContext


# ---------------------------------------------------------------------------
# Intermediate data contracts (internal to the recommendation agent)
# ---------------------------------------------------------------------------


@dataclass
class RecommendationSpec:
    """A single recommendation identified by the rule engine before LLM enrichment.

    title, recommendation_text, rationale, estimated_effort, and context are
    empty strings here — filled in by the service after the LLM call.
    All other fields are final.
    """

    recommendation_id: str
    priority: Priority
    category: RecommendationCategory
    source_finding_ids: list[str]
    source_title: str
    source_severity: Severity
    rag_chunk_ids: list[str] = field(default_factory=list)
    rag_excerpts: list[str] = field(default_factory=list)


@dataclass
class RecommendationRuleOutput:
    """Complete output of the recommendation rule engine for one analysis job."""

    specs: list[RecommendationSpec]
    counts_by_priority: dict[str, int]
    source_finding_count: int
    rag_chunks_used_count: int
    has_findings: bool
    truncated_count: int


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_recommendation_rules(
    architecture_section: ArchitectureSection,
    security_section: SecuritySection,
    rag_context: RAGContext | None,
) -> RecommendationRuleOutput:
    """Run all deterministic recommendation rules.

    Collects architecture weaknesses and security findings, assigns priority
    and category, maps RAG chunks when available, sorts P1→P2→P3, and
    truncates at MAX_RECOMMENDATIONS (lowest-priority items dropped first).

    Args:
        architecture_section: Output of ArchitectureAnalysisNode.
        security_section: Output of SecurityAnalysisNode.
        rag_context: Output of RAGRetrievalNode. None when RAG is not yet run.

    Returns:
        RecommendationRuleOutput with sorted, capped RecommendationSpec list.
    """
    raw_specs = _collect_specs(architecture_section, security_section)

    if rag_context is not None:
        raw_specs = _map_rag_chunks(raw_specs, rag_context)

    p1 = [s for s in raw_specs if s.priority == Priority.P1]
    p2 = [s for s in raw_specs if s.priority == Priority.P2]
    p3 = [s for s in raw_specs if s.priority == Priority.P3]

    for bucket in (p1, p2, p3):
        bucket.sort(key=lambda s: s.source_severity, reverse=True)

    ordered = p1 + p2 + p3
    truncated_count = max(0, len(ordered) - MAX_RECOMMENDATIONS)
    final_specs = ordered[:MAX_RECOMMENDATIONS]

    for i, spec in enumerate(final_specs, start=1):
        spec.recommendation_id = f"REC-{i:03d}"

    rag_chunks_used = sum(len(s.rag_chunk_ids) for s in final_specs)

    return RecommendationRuleOutput(
        specs=final_specs,
        counts_by_priority=_build_counts(final_specs),
        source_finding_count=len(architecture_section.weaknesses) + len(security_section.findings),
        rag_chunks_used_count=rag_chunks_used,
        has_findings=bool(raw_specs),
        truncated_count=truncated_count,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_MAX_EXCERPTS_PER_SPEC = 3
_MAX_EXCERPT_CHARS = 500


def _severity_to_priority(severity: Severity) -> Priority:
    if severity in (Severity.CRITICAL, Severity.HIGH):
        return Priority.P1
    if severity == Severity.MEDIUM:
        return Priority.P2
    return Priority.P3


def _collect_specs(
    architecture_section: ArchitectureSection,
    security_section: SecuritySection,
) -> list[RecommendationSpec]:
    specs: list[RecommendationSpec] = []
    counter = 1

    for weakness in architecture_section.weaknesses:
        specs.append(RecommendationSpec(
            recommendation_id=f"REC-{counter:03d}",
            priority=_severity_to_priority(weakness.severity),
            category=RecommendationCategory.ARCHITECTURE,
            source_finding_ids=[weakness.weakness_id],
            source_title=weakness.title,
            source_severity=weakness.severity,
        ))
        counter += 1

    for finding in security_section.findings:
        specs.append(RecommendationSpec(
            recommendation_id=f"REC-{counter:03d}",
            priority=_severity_to_priority(finding.severity),
            category=RecommendationCategory.SECURITY,
            source_finding_ids=[finding.finding_id],
            source_title=finding.title,
            source_severity=finding.severity,
        ))
        counter += 1

    return specs


def _map_rag_chunks(
    specs: list[RecommendationSpec],
    rag_context: RAGContext,
) -> list[RecommendationSpec]:
    chunk_lookup = {c.chunk_id: c.content_excerpt for c in rag_context.retrieved_chunks}

    finding_to_chunks: dict[str, list[str]] = {}
    for query in rag_context.queries:
        for fid in query.source_finding_ids:
            if fid not in finding_to_chunks:
                finding_to_chunks[fid] = []
            finding_to_chunks[fid].extend(query.result_chunk_ids)

    finding_to_chunks = {k: list(dict.fromkeys(v)) for k, v in finding_to_chunks.items()}

    for spec in specs:
        chunk_ids: list[str] = []
        for fid in spec.source_finding_ids:
            chunk_ids.extend(finding_to_chunks.get(fid, []))
        chunk_ids = list(dict.fromkeys(chunk_ids))[:_MAX_EXCERPTS_PER_SPEC]

        spec.rag_chunk_ids = chunk_ids
        spec.rag_excerpts = [
            chunk_lookup[cid][:_MAX_EXCERPT_CHARS]
            for cid in chunk_ids
            if cid in chunk_lookup
        ]

    return specs


def _build_counts(specs: list[RecommendationSpec]) -> dict[str, int]:
    counts = {p.value: 0 for p in Priority}
    for spec in specs:
        counts[spec.priority.value] += 1
    return counts
