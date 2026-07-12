"""Integration tests for RecommendationService with populated RAGContext.

Verifies that when a non-None RAGContext is passed to RecommendationService.run():
  - KB excerpts appear in the Gemini prompt (captured via mock)
  - Returned Recommendation.rag_chunk_ids_used matches RAGContext chunks
  - RecommendationSection.rag_chunks_used_count is correct
  - rag_context=None path continues to work (backward-compatibility guard)
  - RAGContext with no chunk matches for a finding → rag_chunk_ids_used=[]

Gemini is mocked. Qdrant and Supabase are not involved.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from infrastructure.gemini_client import GenerationResult
from services.recommendation_agent.recommendation_service import RecommendationService
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    OWASPCategory,
    Severity,
    SignalLevel,
    TestCoverageSignal,
)

_JOB_ID = uuid4()
_NOW = datetime.now(tz=timezone.utc)
_MODEL_ID = "gemini-test-model"


# ---------------------------------------------------------------------------
# Section / context helpers
# ---------------------------------------------------------------------------


def _gen_metadata():
    from shared.types.analysis_types import GenerationMetadata

    return GenerationMetadata(
        model_id=_MODEL_ID,
        input_token_count=0,
        output_token_count=0,
        generation_timestamp=_NOW,
        retry_count=0,
    )


def _make_arch_section(weaknesses=None):
    from shared.types.analysis_types import ArchitectureSection, CouplingAnalysis

    return ArchitectureSection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        detected_pattern=ArchitecturePattern.LAYERED,
        confidence=Confidence.HIGH,
        strengths=["Clean structure"],
        weaknesses=weaknesses or [],
        coupling_analysis=CouplingAnalysis(
            overall_coupling_level=SignalLevel.LOW,
            high_coupling_file_count=0,
            dependency_violation_count=0,
            coupling_narrative="Low coupling in service test fixture.",
        ),
        test_coverage_signal=TestCoverageSignal.PRESENT,
        narrative="Architecture narrative for service RAG integration test." * 3,
        generated_at=_NOW,
        generation_metadata=_gen_metadata(),
    )


def _make_weakness(wid: str, severity: Severity):
    from shared.types.analysis_types import ArchitectureWeakness

    return ArchitectureWeakness(
        weakness_id=wid,
        title=f"Weakness {wid}",
        severity=severity,
        description="A weakness description for service RAG integration tests.",
        rag_query_hint=f"layered architecture coupling remediation for {wid}",
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
        narrative="Security narrative for service RAG integration test." * 3,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=_NOW,
        generation_metadata=_gen_metadata(),
    )


def _make_finding(fid: str, severity: Severity):
    from shared.types.analysis_types import SecurityFinding

    return SecurityFinding(
        finding_id=fid,
        title=f"Finding {fid}",
        severity=severity,
        confidence=Confidence.HIGH,
        owasp_category=OWASPCategory.A03_INJECTION,
        cwe_id="CWE-89",
        description="A security finding description for service RAG integration tests.",
        rag_query_hint=f"SQL injection prevention parameterized queries for {fid}",
    )


def _make_rag_context(queries, chunks):
    from config.constants import RAG_RELEVANCE_THRESHOLD
    from shared.types.rag_types import RAGContext

    return RAGContext(
        context_id=uuid4(),
        job_id=_JOB_ID,
        queries=queries,
        retrieved_chunks=chunks,
        total_queries_made=len(queries),
        total_chunks_retrieved=len(chunks),
        chunks_filtered_count=0,
        retrieval_timestamp=_NOW,
        relevance_threshold_used=RAG_RELEVANCE_THRESHOLD,
    )


def _make_rag_query(query_id, source_finding_ids, result_chunk_ids=None):
    from shared.types.enums import RAGDomain
    from shared.types.rag_types import RAGQuery

    return RAGQuery(
        query_id=query_id,
        query_text="architecture coupling remediation test query",
        source_domain=RAGDomain.ARCHITECTURE,
        source_finding_ids=source_finding_ids,
        result_chunk_ids=result_chunk_ids or [],
    )


def _make_rag_chunk(chunk_id, content):
    from config.constants import RAG_RELEVANCE_THRESHOLD
    from shared.types.enums import RAGDomain
    from shared.types.rag_types import RAGChunk

    return RAGChunk(
        chunk_id=chunk_id,
        document_title="Layered Architecture Patterns",
        domain=RAGDomain.ARCHITECTURE,
        content_excerpt=content,
        relevance_score=RAG_RELEVANCE_THRESHOLD,
        query_ids_matched=[],
    )


def _make_valid_llm_response(rec_ids: list[str]) -> str:
    """Build a minimal valid LLM JSON response for the given recommendation IDs."""
    recs = {
        rid: {
            "title": f"Fix {rid}",
            "recommendation_text": "Refactor the affected components to enforce proper layering and reduce coupling between modules.",
            "rationale": "Unresolved coupling increases fragility and makes future changes significantly harder.",
            "estimated_effort": "MEDIUM (estimate)",
            "context": "Knowledge base guidance recommends enforcing strict layer boundaries and using dependency inversion.",
        }
        for rid in rec_ids
    }
    return json.dumps({
        "executive_summary": (
            "The codebase exhibits moderate architectural coupling that requires refactoring. "
            "Security findings indicate injection risks that must be addressed immediately to "
            "prevent data exposure and unauthorized access."
        ),
        "actionable_next_steps": [
            "Enforce strict layer boundaries across all service modules.",
            "Replace raw SQL string concatenation with parameterized queries.",
            "Add integration tests for all data access paths.",
        ],
        "recommendations": recs,
    })


def _make_service() -> tuple[RecommendationService, MagicMock]:
    """Return (service, mock_gemini_client)."""
    mock_gemini = MagicMock()
    service = RecommendationService(gemini_client=mock_gemini, model_id=_MODEL_ID)
    return service, mock_gemini


# ---------------------------------------------------------------------------
# KB excerpt appears in Gemini prompt
# ---------------------------------------------------------------------------


def test_service_run_with_rag_context_passes_excerpt_to_gemini():
    excerpt = "Enforce strict layer isolation: never allow presentation layer to call data layer directly."
    chunk = _make_rag_chunk("architecture/layered/0", excerpt)
    query = _make_rag_query("Q-001", source_finding_ids=["AW-001"], result_chunk_ids=["architecture/layered/0"])
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    call_args = mock_gemini.generate.call_args
    prompt_passed = call_args[1]["prompt"] if "prompt" in call_args[1] else call_args[0][0]
    assert excerpt in prompt_passed


def test_service_run_with_rag_context_shows_kb_context_header_in_prompt():
    chunk = _make_rag_chunk("architecture/layered/0", "Layer isolation guidance for prompt header test.")
    query = _make_rag_query("Q-001", source_finding_ids=["AW-001"], result_chunk_ids=["architecture/layered/0"])
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    call_args = mock_gemini.generate.call_args
    prompt_passed = call_args[1]["prompt"] if "prompt" in call_args[1] else call_args[0][0]
    assert "Knowledge base context:" in prompt_passed


# ---------------------------------------------------------------------------
# rag_chunk_ids_used propagation
# ---------------------------------------------------------------------------


def test_service_run_with_rag_context_sets_rag_chunk_ids_used_on_recommendation():
    chunk = _make_rag_chunk("architecture/layered/0", "KB guidance for chunk ID propagation test.")
    query = _make_rag_query("Q-001", source_finding_ids=["AW-001"], result_chunk_ids=["architecture/layered/0"])
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    section = service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    assert section.recommendations[0].rag_chunk_ids_used == ["architecture/layered/0"]


def test_service_run_rag_chunks_used_count_nonzero_when_context_provided():
    chunk = _make_rag_chunk("architecture/layered/0", "KB guidance for chunk count test.")
    query = _make_rag_query("Q-001", source_finding_ids=["AW-001"], result_chunk_ids=["architecture/layered/0"])
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    section = service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    assert section.rag_chunks_used_count == 1


# ---------------------------------------------------------------------------
# No chunk match for finding → empty rag_chunk_ids_used
# ---------------------------------------------------------------------------


def test_service_run_with_rag_context_no_chunk_match_gives_empty_ids():
    chunk = _make_rag_chunk("architecture/layered/0", "KB guidance unrelated to AW-001.")
    # Query targets AW-999, not AW-001
    query = _make_rag_query("Q-001", source_finding_ids=["AW-999"], result_chunk_ids=["architecture/layered/0"])
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    section = service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    assert section.recommendations[0].rag_chunk_ids_used == []
    assert section.rag_chunks_used_count == 0


def test_service_run_with_rag_context_no_match_shows_none_retrieved_in_prompt():
    chunk = _make_rag_chunk("architecture/layered/0", "KB content for unrelated finding.")
    query = _make_rag_query("Q-001", source_finding_ids=["AW-999"], result_chunk_ids=["architecture/layered/0"])
    rag_context = _make_rag_context([query], [chunk])

    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    call_args = mock_gemini.generate.call_args
    prompt_passed = call_args[1]["prompt"] if "prompt" in call_args[1] else call_args[0][0]
    assert "Knowledge base context: none retrieved" in prompt_passed


# ---------------------------------------------------------------------------
# Backward compatibility — rag_context=None
# ---------------------------------------------------------------------------


def test_service_run_with_rag_context_none_succeeds():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    section = service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=None,
    )

    assert section is not None
    assert len(section.recommendations) == 1


def test_service_run_with_rag_context_none_gives_empty_chunk_ids():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    section = service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=None,
    )

    assert section.recommendations[0].rag_chunk_ids_used == []
    assert section.rag_chunks_used_count == 0


def test_service_run_with_rag_context_none_shows_none_retrieved_in_prompt():
    arch = _make_arch_section(weaknesses=[_make_weakness("AW-001", Severity.HIGH)])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001"]), input_tokens=0, output_tokens=0)

    service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=None,
    )

    call_args = mock_gemini.generate.call_args
    prompt_passed = call_args[1]["prompt"] if "prompt" in call_args[1] else call_args[0][0]
    assert "Knowledge base context: none retrieved" in prompt_passed


# ---------------------------------------------------------------------------
# Multiple findings with mixed RAG coverage
# ---------------------------------------------------------------------------


def test_service_run_mixed_rag_coverage_per_finding():
    """One finding has KB chunks, one does not. Verify per-recommendation chunk ID assignment."""
    chunk = _make_rag_chunk("architecture/layered/0", "Guidance for AW-001 specifically.")
    # Q-001 covers AW-001 (gets chunks); Q-002 covers AW-002 (no result chunks)
    query_with_chunks = _make_rag_query(
        "Q-001",
        source_finding_ids=["AW-001"],
        result_chunk_ids=["architecture/layered/0"],
    )
    query_no_chunks = _make_rag_query(
        "Q-002",
        source_finding_ids=["AW-002"],
        result_chunk_ids=[],
    )
    rag_context = _make_rag_context([query_with_chunks, query_no_chunks], [chunk])

    arch = _make_arch_section(weaknesses=[
        _make_weakness("AW-001", Severity.HIGH),
        _make_weakness("AW-002", Severity.MEDIUM),
    ])
    sec = _make_sec_section()

    service, mock_gemini = _make_service()
    mock_gemini.generate.return_value = GenerationResult(text=_make_valid_llm_response(["REC-001", "REC-002"]), input_tokens=0, output_tokens=0)

    section = service.run(
        architecture_section=arch,
        security_section=sec,
        rag_context=rag_context,
    )

    rec_001 = next(r for r in section.recommendations if r.recommendation_id == "REC-001")
    rec_002 = next(r for r in section.recommendations if r.recommendation_id == "REC-002")

    assert rec_001.rag_chunk_ids_used == ["architecture/layered/0"]
    assert rec_002.rag_chunk_ids_used == []
