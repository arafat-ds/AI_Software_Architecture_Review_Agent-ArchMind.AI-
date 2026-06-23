"""Unit tests for the Recommendation Agent deterministic rule engine.

All tests are pure: no Gemini calls, no settings, no .env required.
Tests verify priority assignment, category mapping, MAX_RECOMMENDATIONS
truncation, RAG chunk mapping, and output consistency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from services.recommendation_agent.rule_engine import (
    RecommendationRuleOutput,
    RecommendationSpec,
    _build_counts,
    _collect_specs,
    _map_rag_chunks,
    _severity_to_priority,
    run_recommendation_rules,
)
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    OWASPCategory,
    Priority,
    RecommendationCategory,
    Severity,
    SignalLevel,
    TestCoverageSignal,
)


# ---------------------------------------------------------------------------
# Fixtures and minimal helpers
# ---------------------------------------------------------------------------


_JOB_ID = uuid4()
_SECTION_ID = uuid4()
_NOW = datetime.now(tz=timezone.utc)


def _make_arch_section(weaknesses=None):
    from shared.types.analysis_types import (
        ArchitectureSection,
        ArchitectureWeakness,
        CouplingAnalysis,
        GenerationMetadata,
    )

    if weaknesses is None:
        weaknesses = []

    return ArchitectureSection(
        section_id=_SECTION_ID,
        job_id=_JOB_ID,
        detected_pattern=ArchitecturePattern.LAYERED,
        confidence=Confidence.HIGH,
        strengths=["Clean layering"],
        weaknesses=weaknesses,
        coupling_analysis=CouplingAnalysis(
            overall_coupling_level=SignalLevel.LOW,
            high_coupling_file_count=0,
            dependency_violation_count=0,
            coupling_narrative="Low coupling detected.",
        ),
        test_coverage_signal=TestCoverageSignal.PRESENT,
        narrative="Architecture narrative." * 5,
        generated_at=_NOW,
        generation_metadata=GenerationMetadata(
            model_id="gemini-test",
            input_token_count=0,
            output_token_count=0,
            generation_timestamp=_NOW,
            retry_count=0,
        ),
    )


def _make_weakness(wid: str, severity: Severity) -> object:
    from shared.types.analysis_types import ArchitectureWeakness

    return ArchitectureWeakness(
        weakness_id=wid,
        title=f"Weakness {wid}",
        severity=severity,
        description="A weakness description for testing purposes.",
        rag_query_hint=f"query hint for {wid}",
    )


def _make_sec_section(findings=None):
    from config.constants import DISCLAIMER_TEXT
    from shared.types.analysis_types import GenerationMetadata, SecuritySection
    from shared.types.enums import Severity

    if findings is None:
        findings = []

    counts = {level.name: 0 for level in Severity}
    for f in findings:
        counts[f.severity.name] += 1

    overall = max((f.severity for f in findings), default=Severity.INFO)

    return SecuritySection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        findings=findings,
        overall_risk_level=overall,
        finding_counts_by_severity=counts,
        narrative="Security narrative." * 5,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=_NOW,
        generation_metadata=GenerationMetadata(
            model_id="gemini-test",
            input_token_count=0,
            output_token_count=0,
            generation_timestamp=_NOW,
            retry_count=0,
        ),
    )


def _make_finding(fid: str, severity: Severity) -> object:
    from shared.types.analysis_types import SecurityFinding

    return SecurityFinding(
        finding_id=fid,
        title=f"Finding {fid}",
        severity=severity,
        confidence=Confidence.HIGH,
        owasp_category=OWASPCategory.A03_INJECTION,
        cwe_id="CWE-89",
        description="A security finding description for testing purposes in unit tests.",
        rag_query_hint=f"injection prevention and parameterized queries for {fid}",
    )


# ---------------------------------------------------------------------------
# Priority assignment
# ---------------------------------------------------------------------------


def test_severity_critical_maps_to_p1():
    assert _severity_to_priority(Severity.CRITICAL) == Priority.P1


def test_severity_high_maps_to_p1():
    assert _severity_to_priority(Severity.HIGH) == Priority.P1


def test_severity_medium_maps_to_p2():
    assert _severity_to_priority(Severity.MEDIUM) == Priority.P2


def test_severity_low_maps_to_p3():
    assert _severity_to_priority(Severity.LOW) == Priority.P3


def test_severity_info_maps_to_p3():
    assert _severity_to_priority(Severity.INFO) == Priority.P3


# ---------------------------------------------------------------------------
# Category assignment
# ---------------------------------------------------------------------------


def test_architecture_weakness_maps_to_architecture_category():
    weakness = _make_weakness("AW-001", Severity.HIGH)
    arch = _make_arch_section(weaknesses=[weakness])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert len(output.specs) == 1
    assert output.specs[0].category == RecommendationCategory.ARCHITECTURE


def test_security_finding_maps_to_security_category():
    finding = _make_finding("SF-001", Severity.HIGH)
    arch = _make_arch_section()
    sec = _make_sec_section(findings=[finding])

    output = run_recommendation_rules(arch, sec, None)

    assert len(output.specs) == 1
    assert output.specs[0].category == RecommendationCategory.SECURITY


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


def test_recommendations_ordered_p1_before_p2_before_p3():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.LOW),
        _make_weakness("AW-002", Severity.MEDIUM),
        _make_weakness("AW-003", Severity.HIGH),
    ])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    priorities = [s.priority for s in output.specs]
    assert priorities == [Priority.P1, Priority.P2, Priority.P3]


def test_within_p1_sorted_by_severity_descending():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.HIGH),
        _make_weakness("AW-002", Severity.CRITICAL),
    ])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert output.specs[0].source_severity == Severity.CRITICAL
    assert output.specs[1].source_severity == Severity.HIGH


# ---------------------------------------------------------------------------
# Truncation at MAX_RECOMMENDATIONS
# ---------------------------------------------------------------------------


def test_truncation_at_max_recommendations():
    from config.constants import MAX_RECOMMENDATIONS

    weaknesses = [_make_weakness(f"AW-{i:03d}", Severity.LOW) for i in range(1, 20)]
    arch = _make_arch_section(weaknesses=weaknesses)
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert len(output.specs) == MAX_RECOMMENDATIONS
    assert output.truncated_count == len(weaknesses) - MAX_RECOMMENDATIONS


def test_p1_preserved_when_truncating():
    from config.constants import MAX_RECOMMENDATIONS

    p1_weaknesses = [_make_weakness(f"AW-{i:03d}", Severity.CRITICAL) for i in range(1, 10)]
    p3_weaknesses = [_make_weakness(f"AW-{i:03d}", Severity.LOW) for i in range(10, 25)]
    all_weaknesses = p1_weaknesses + p3_weaknesses
    arch = _make_arch_section(weaknesses=all_weaknesses)
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert len(output.specs) == MAX_RECOMMENDATIONS
    p1_specs = [s for s in output.specs if s.priority == Priority.P1]
    assert len(p1_specs) == len(p1_weaknesses)


def test_no_truncation_when_under_cap():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section(findings=[_make_finding("SF-001", Severity.MEDIUM)])

    output = run_recommendation_rules(arch, sec, None)

    assert output.truncated_count == 0
    assert len(output.specs) == 2


# ---------------------------------------------------------------------------
# Source finding count
# ---------------------------------------------------------------------------


def test_source_finding_count_is_weaknesses_plus_findings():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.HIGH),
        _make_weakness("AW-002", Severity.LOW),
    ])
    sec = _make_sec_section(findings=[_make_finding("SF-001", Severity.MEDIUM)])

    output = run_recommendation_rules(arch, sec, None)

    assert output.source_finding_count == 3


def test_zero_findings_produces_empty_specs_and_no_findings_flag():
    arch = _make_arch_section()
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert output.specs == []
    assert output.has_findings is False


def test_has_findings_true_when_items_exist():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert output.has_findings is True


# ---------------------------------------------------------------------------
# RAG context
# ---------------------------------------------------------------------------


def test_rag_context_none_produces_empty_chunk_ids():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert output.specs[0].rag_chunk_ids == []
    assert output.specs[0].rag_excerpts == []
    assert output.rag_chunks_used_count == 0


# ---------------------------------------------------------------------------
# Recommendation IDs and counts
# ---------------------------------------------------------------------------


def test_recommendation_ids_sequential_after_sort():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.LOW),
        _make_weakness("AW-002", Severity.HIGH),
    ])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    ids = [s.recommendation_id for s in output.specs]
    assert ids == ["REC-001", "REC-002"]


def test_counts_by_priority_consistent_with_specs():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.CRITICAL),
        _make_weakness("AW-002", Severity.MEDIUM),
        _make_weakness("AW-003", Severity.LOW),
    ])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, None)

    assert output.counts_by_priority["P1"] == 1
    assert output.counts_by_priority["P2"] == 1
    assert output.counts_by_priority["P3"] == 1


# ---------------------------------------------------------------------------
# _map_rag_chunks with populated RAGContext
# ---------------------------------------------------------------------------


def _make_rag_context(queries, chunks):
    from config.constants import RAG_RELEVANCE_THRESHOLD
    from datetime import datetime, timezone
    from shared.types.rag_types import RAGContext

    return RAGContext(
        context_id=uuid4(),
        job_id=_JOB_ID,
        queries=queries,
        retrieved_chunks=chunks,
        total_queries_made=len(queries),
        total_chunks_retrieved=len(chunks),
        chunks_filtered_count=0,
        retrieval_timestamp=datetime.now(tz=timezone.utc),
        relevance_threshold_used=RAG_RELEVANCE_THRESHOLD,
    )


def _make_rag_query(query_id, source_finding_ids, result_chunk_ids=None):
    from shared.types.enums import RAGDomain
    from shared.types.rag_types import RAGQuery

    return RAGQuery(
        query_id=query_id,
        query_text="test query text for unit test fixture",
        source_domain=RAGDomain.ARCHITECTURE,
        source_finding_ids=source_finding_ids,
        result_chunk_ids=result_chunk_ids or [],
    )


def _make_rag_chunk(chunk_id, content, query_ids_matched=None):
    from config.constants import RAG_RELEVANCE_THRESHOLD
    from shared.types.enums import RAGDomain
    from shared.types.rag_types import RAGChunk

    return RAGChunk(
        chunk_id=chunk_id,
        document_title="Test KB Document",
        domain=RAGDomain.ARCHITECTURE,
        content_excerpt=content,
        relevance_score=RAG_RELEVANCE_THRESHOLD,
        query_ids_matched=query_ids_matched or [],
    )


def test_map_rag_chunks_populates_chunk_ids_when_finding_matches():
    chunk = _make_rag_chunk("architecture/layered/0", "Layered architecture guidance content.")
    query = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert output.specs[0].rag_chunk_ids == ["architecture/layered/0"]


def test_map_rag_chunks_populates_rag_excerpts_from_content():
    content = "Specific guidance about dependency inversion and layer isolation."
    chunk = _make_rag_chunk("architecture/layered/0", content)
    query = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert output.specs[0].rag_excerpts == [content]


def test_map_rag_chunks_finding_with_no_matching_query_gets_empty_ids():
    chunk = _make_rag_chunk("architecture/layered/0", "Some guidance content text here.")
    query = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-999"],
        result_chunk_ids=["architecture/layered/0"],
    )
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert output.specs[0].rag_chunk_ids == []
    assert output.specs[0].rag_excerpts == []


def test_map_rag_chunks_deduplicates_same_chunk_from_multiple_queries():
    chunk = _make_rag_chunk("architecture/layered/0", "Shared guidance content for dedup test.")
    query1 = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    query2 = _make_rag_query(
        "Q-002",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    rag_context = _make_rag_context([query1, query2], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert output.specs[0].rag_chunk_ids == ["architecture/layered/0"]
    assert len(output.specs[0].rag_chunk_ids) == 1


def test_map_rag_chunks_excerpt_truncated_at_500_chars():
    long_content = "A" * 600
    chunk = _make_rag_chunk("architecture/layered/0", long_content)
    query = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert len(output.specs[0].rag_excerpts[0]) == 500


def test_run_recommendation_rules_with_rag_context_sets_chunks_used_count():
    content = "Actionable guidance content for testing rag_chunks_used_count."
    chunk = _make_rag_chunk("architecture/layered/0", content)
    query = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert output.rag_chunks_used_count == 1


def test_map_rag_chunks_capped_at_three_excerpts_per_spec():
    chunks = [
        _make_rag_chunk(
            f"architecture/layered/{i}",
            f"Guidance content number {i} for excerpt cap test.",
        )
        for i in range(5)
    ]
    chunk_ids = [c.chunk_id for c in chunks]
    query = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=chunk_ids,
    )
    rag_context = _make_rag_context([query], chunks)

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    output = run_recommendation_rules(arch, sec, rag_context)

    assert len(output.specs[0].rag_chunk_ids) == 3
    assert len(output.specs[0].rag_excerpts) == 3
