"""Unit tests for services/rag_agent/query_builder.py.

All tests are pure: no Gemini calls, no Qdrant, no settings, no .env required.
Tests verify query count, Q-NNN format, domain assignment, severity sorting,
source_finding_ids population, and MAX_RAG_QUERIES truncation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.rag_agent.query_builder import build_rag_queries
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    OWASPCategory,
    Severity,
    SignalLevel,
    TestCoverageSignal,
    RAGDomain,
)

_JOB_ID = uuid4()
_NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_gen_metadata():
    from shared.types.analysis_types import GenerationMetadata
    return GenerationMetadata(
        model_id="gemini-test",
        input_token_count=0,
        output_token_count=0,
        generation_timestamp=_NOW,
        retry_count=0,
    )


def _make_weakness(wid: str, severity: Severity, hint: str = ""):
    from shared.types.analysis_types import ArchitectureWeakness
    return ArchitectureWeakness(
        weakness_id=wid,
        title=f"Weakness {wid}",
        severity=severity,
        description="A test weakness description for query builder unit tests.",
        rag_query_hint=hint or f"architecture coupling remediation for {wid}",
    )


def _make_finding(fid: str, severity: Severity, hint: str = ""):
    from shared.types.analysis_types import SecurityFinding
    return SecurityFinding(
        finding_id=fid,
        title=f"Finding {fid}",
        severity=severity,
        confidence=Confidence.HIGH,
        owasp_category=OWASPCategory.A03_INJECTION,
        cwe_id="CWE-89",
        description="A test security finding description for query builder tests.",
        rag_query_hint=hint or f"injection prevention for {fid}",
    )


def _make_arch_section(weaknesses=None):
    from shared.types.analysis_types import ArchitectureSection, CouplingAnalysis
    return ArchitectureSection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        detected_pattern=ArchitecturePattern.LAYERED,
        confidence=Confidence.HIGH,
        strengths=["Good structure"],
        weaknesses=weaknesses or [],
        coupling_analysis=CouplingAnalysis(
            overall_coupling_level=SignalLevel.LOW,
            high_coupling_file_count=0,
            dependency_violation_count=0,
            coupling_narrative="Low coupling detected in test.",
        ),
        test_coverage_signal=TestCoverageSignal.PRESENT,
        narrative="Architecture narrative for testing." * 3,
        generated_at=_NOW,
        generation_metadata=_make_gen_metadata(),
    )


def _make_sec_section(findings=None):
    from config.constants import DISCLAIMER_TEXT
    from shared.types.analysis_types import SecuritySection
    findings = findings or []
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
        narrative="Security narrative for testing." * 3,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=_NOW,
        generation_metadata=_make_gen_metadata(),
    )


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


def test_no_weaknesses_no_findings_returns_empty():
    result = build_rag_queries(_make_arch_section(), _make_sec_section())
    assert result == []


def test_only_weaknesses_returns_architecture_queries():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    result = build_rag_queries(arch, _make_sec_section())
    assert len(result) == 1
    assert result[0].source_domain == RAGDomain.ARCHITECTURE


def test_only_findings_returns_security_queries():
    sec = _make_sec_section(findings=[_make_finding("SF-001", Severity.HIGH)])
    result = build_rag_queries(_make_arch_section(), sec)
    assert len(result) == 1
    assert result[0].source_domain == RAGDomain.SECURITY


# ---------------------------------------------------------------------------
# Query ID format
# ---------------------------------------------------------------------------


def test_query_ids_are_sequential_q_nnn():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.HIGH),
        _make_weakness("AW-002", Severity.LOW),
    ])
    sec = _make_sec_section(findings=[_make_finding("SF-001", Severity.MEDIUM)])
    result = build_rag_queries(arch, sec)
    ids = [q.query_id for q in result]
    assert ids == ["Q-001", "Q-002", "Q-003"]


# ---------------------------------------------------------------------------
# Severity sorting
# ---------------------------------------------------------------------------


def test_highest_severity_gets_first_query_slot():
    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.LOW),
        _make_weakness("AW-002", Severity.CRITICAL),
    ])
    result = build_rag_queries(_make_arch_section(), _make_sec_section())
    # With empty input, result is empty — test with actual data:
    result = build_rag_queries(arch, _make_sec_section())
    assert result[0].source_finding_ids == ["AW-002"]


def test_security_critical_ranked_above_arch_low():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.LOW)])
    sec = _make_sec_section(findings=[_make_finding("SF-001", Severity.CRITICAL)])
    result = build_rag_queries(arch, sec)
    assert result[0].source_finding_ids == ["SF-001"]
    assert result[1].source_finding_ids == ["AW-001"]


# ---------------------------------------------------------------------------
# source_finding_ids
# ---------------------------------------------------------------------------


def test_weakness_source_finding_ids_contains_weakness_id():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-042", Severity.HIGH)])
    result = build_rag_queries(arch, _make_sec_section())
    assert result[0].source_finding_ids == ["AW-042"]


def test_finding_source_finding_ids_contains_finding_id():
    sec = _make_sec_section(findings=[_make_finding("SF-007", Severity.HIGH)])
    result = build_rag_queries(_make_arch_section(), sec)
    assert result[0].source_finding_ids == ["SF-007"]


# ---------------------------------------------------------------------------
# query_text comes from rag_query_hint
# ---------------------------------------------------------------------------


def test_query_text_equals_weakness_rag_query_hint():
    hint = "circular dependency refactoring strategies"
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH, hint=hint)])
    result = build_rag_queries(arch, _make_sec_section())
    assert result[0].query_text == hint


def test_query_text_equals_finding_rag_query_hint():
    hint = "sql injection prevention parameterized queries"
    sec = _make_sec_section(findings=[_make_finding("SF-001", Severity.HIGH, hint=hint)])
    result = build_rag_queries(_make_arch_section(), sec)
    assert result[0].query_text == hint


# ---------------------------------------------------------------------------
# Truncation at MAX_RAG_QUERIES
# ---------------------------------------------------------------------------


def test_truncation_at_max_queries():
    weaknesses = [_make_weakness(f"AW-{i:03d}", Severity.LOW) for i in range(1, 20)]
    arch = _make_arch_section(weaknesses=weaknesses)
    result = build_rag_queries(arch, _make_sec_section(), max_queries=5)
    assert len(result) == 5


def test_truncation_preserves_highest_severity():
    low = [_make_weakness(f"AW-{i:03d}", Severity.LOW) for i in range(1, 10)]
    critical = [_make_weakness("AW-099", Severity.CRITICAL)]
    arch = _make_arch_section(weaknesses=low + critical)
    result = build_rag_queries(arch, _make_sec_section(), max_queries=3)
    ids = [q.source_finding_ids[0] for q in result]
    assert "AW-099" in ids
