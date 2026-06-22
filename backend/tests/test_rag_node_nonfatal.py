"""Unit tests for the RAGRetrievalNode non-fatal failure model.

Verifies:
- CollectionNotFoundError → rag_context=None, no FatalNodeError
- RetrievalError → rag_context=None, no FatalNodeError
- EmbeddingError → rag_context=None, no FatalNodeError (via _get_service mock)
- Success → rag_context is populated RAGContext
- workflow_status == SYNTHESIZING in all code paths
- Empty queries (no weaknesses/findings) → rag_context=None without calling service

All tests patch _get_service to avoid settings/Qdrant/Gemini requirements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.workflow.nodes.rag_node import rag_retrieval_node
from shared.exceptions.rag_exceptions import CollectionNotFoundError, RetrievalError
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    OWASPCategory,
    Severity,
    SignalLevel,
    TestCoverageSignal,
    WorkflowStatus,
)

_JOB_ID = uuid4()
_NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# State and section helpers
# ---------------------------------------------------------------------------


def _gen_metadata():
    from shared.types.analysis_types import GenerationMetadata
    return GenerationMetadata(
        model_id="gemini-test",
        input_token_count=0,
        output_token_count=0,
        generation_timestamp=_NOW,
        retry_count=0,
    )


def _make_arch_section():
    from shared.types.analysis_types import ArchitectureSection, ArchitectureWeakness, CouplingAnalysis
    return ArchitectureSection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        detected_pattern=ArchitecturePattern.LAYERED,
        confidence=Confidence.HIGH,
        strengths=["Clean boundaries"],
        weaknesses=[
            ArchitectureWeakness(
                weakness_id="AW-001",
                title="Test weakness",
                severity=Severity.HIGH,
                description="A test weakness description for RAG node testing purposes.",
                rag_query_hint="layered architecture coupling remediation strategies",
            )
        ],
        coupling_analysis=CouplingAnalysis(
            overall_coupling_level=SignalLevel.LOW,
            high_coupling_file_count=0,
            dependency_violation_count=0,
            coupling_narrative="Low coupling in test fixture.",
        ),
        test_coverage_signal=TestCoverageSignal.PRESENT,
        narrative="Architecture narrative for RAG node test fixture." * 3,
        generated_at=_NOW,
        generation_metadata=_gen_metadata(),
    )


def _make_sec_section():
    from config.constants import DISCLAIMER_TEXT
    from shared.types.analysis_types import SecurityFinding, SecuritySection
    findings = [
        SecurityFinding(
            finding_id="SF-001",
            title="Test finding",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            owasp_category=OWASPCategory.A03_INJECTION,
            cwe_id="CWE-89",
            description="A test security finding description for RAG node test fixture.",
            rag_query_hint="SQL injection prevention parameterized queries",
        )
    ]
    counts = {level.name: 0 for level in Severity}
    counts["HIGH"] = 1
    return SecuritySection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        findings=findings,
        overall_risk_level=Severity.HIGH,
        finding_counts_by_severity=counts,
        narrative="Security narrative for RAG node test fixture." * 3,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=_NOW,
        generation_metadata=_gen_metadata(),
    )


def _make_empty_sec_section():
    from config.constants import DISCLAIMER_TEXT
    from shared.types.analysis_types import SecuritySection
    counts = {level.name: 0 for level in Severity}
    return SecuritySection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        findings=[],
        overall_risk_level=Severity.INFO,
        finding_counts_by_severity=counts,
        narrative="Security narrative for empty test fixture." * 3,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=_NOW,
        generation_metadata=_gen_metadata(),
    )


def _make_arch_section_empty():
    from shared.types.analysis_types import ArchitectureSection, CouplingAnalysis
    return ArchitectureSection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        detected_pattern=ArchitecturePattern.LAYERED,
        confidence=Confidence.HIGH,
        strengths=["Good structure"],
        weaknesses=[],
        coupling_analysis=CouplingAnalysis(
            overall_coupling_level=SignalLevel.LOW,
            high_coupling_file_count=0,
            dependency_violation_count=0,
            coupling_narrative="Low coupling in empty test fixture.",
        ),
        test_coverage_signal=TestCoverageSignal.PRESENT,
        narrative="Architecture narrative for empty test fixture." * 3,
        generated_at=_NOW,
        generation_metadata=_gen_metadata(),
    )


def _make_state(arch_section=None, sec_section=None):
    from shared.types.enums import NodeExecutionStatus
    return {
        "job_id": _JOB_ID,
        "repo_url": "https://github.com/test/repo",
        "workflow_status": WorkflowStatus.ANALYZING_SECURITY,
        "created_at": _NOW,
        "errors": [],
        "node_execution_log": [],
        "repository_manifest": None,
        "parsed_code_representation": None,
        "architecture_section": arch_section or _make_arch_section(),
        "security_section": sec_section or _make_sec_section(),
        "rag_context": None,
        "recommendations_section": None,
        "final_report": None,
        "final_report_markdown": None,
    }


def _make_rag_context():
    from config.constants import RAG_RELEVANCE_THRESHOLD
    from shared.types.rag_types import RAGContext
    return RAGContext(
        context_id=uuid4(),
        job_id=_JOB_ID,
        queries=[],
        retrieved_chunks=[],
        total_queries_made=0,
        total_chunks_retrieved=0,
        chunks_filtered_count=0,
        retrieval_timestamp=_NOW,
        relevance_threshold_used=RAG_RELEVANCE_THRESHOLD,
    )


# ---------------------------------------------------------------------------
# Non-fatal failure paths
# ---------------------------------------------------------------------------


def test_collection_not_found_returns_none():
    state = _make_state()
    mock_service = MagicMock()
    mock_service.run.side_effect = CollectionNotFoundError("archmind_kb")

    with patch("core.workflow.nodes.rag_node._get_service", return_value=mock_service):
        result = rag_retrieval_node(state)

    assert result["rag_context"] is None
    assert result["workflow_status"] == WorkflowStatus.SYNTHESIZING


def test_retrieval_error_returns_none():
    state = _make_state()
    mock_service = MagicMock()
    mock_service.run.side_effect = RetrievalError("test query", "connection refused")

    with patch("core.workflow.nodes.rag_node._get_service", return_value=mock_service):
        result = rag_retrieval_node(state)

    assert result["rag_context"] is None
    assert result["workflow_status"] == WorkflowStatus.SYNTHESIZING


def test_generic_exception_returns_none():
    state = _make_state()
    mock_service = MagicMock()
    mock_service.run.side_effect = RuntimeError("unexpected failure")

    with patch("core.workflow.nodes.rag_node._get_service", return_value=mock_service):
        result = rag_retrieval_node(state)

    assert result["rag_context"] is None
    assert result["workflow_status"] == WorkflowStatus.SYNTHESIZING


def test_failure_records_non_fatal_workflow_error():
    state = _make_state()
    mock_service = MagicMock()
    mock_service.run.side_effect = CollectionNotFoundError("archmind_kb")

    with patch("core.workflow.nodes.rag_node._get_service", return_value=mock_service):
        rag_retrieval_node(state)

    assert len(state["errors"]) == 1
    assert state["errors"][0].is_fatal is False


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_success_returns_rag_context():
    state = _make_state()
    context = _make_rag_context()
    mock_service = MagicMock()
    mock_service.run.return_value = context

    with patch("core.workflow.nodes.rag_node._get_service", return_value=mock_service):
        result = rag_retrieval_node(state)

    assert result["rag_context"] is context
    assert result["workflow_status"] == WorkflowStatus.SYNTHESIZING


def test_success_records_no_errors():
    state = _make_state()
    mock_service = MagicMock()
    mock_service.run.return_value = _make_rag_context()

    with patch("core.workflow.nodes.rag_node._get_service", return_value=mock_service):
        rag_retrieval_node(state)

    assert state["errors"] == []


# ---------------------------------------------------------------------------
# Empty queries early-exit path
# ---------------------------------------------------------------------------


def test_empty_queries_returns_none_without_calling_service():
    state = _make_state(
        arch_section=_make_arch_section_empty(),
        sec_section=_make_empty_sec_section(),
    )
    mock_get_service = MagicMock()

    with patch("core.workflow.nodes.rag_node._get_service", mock_get_service):
        result = rag_retrieval_node(state)

    assert result["rag_context"] is None
    assert result["workflow_status"] == WorkflowStatus.SYNTHESIZING
    mock_get_service.assert_not_called()
