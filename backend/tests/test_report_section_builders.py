"""Unit tests for report assembly section builders and metadata builder.

All tests are pure: no Gemini calls, no settings, no .env required.
Tests verify correct SectionKey, section_order, required content,
and ReportMetadata calculation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.report_assembly.metadata_builder import build_report_metadata
from services.report_assembly.section_builders import (
    build_actionable_next_steps_section,
    build_architecture_assessment_section,
    build_executive_summary_section,
    build_recommendations_section,
    build_repository_overview_section,
    build_security_findings_section,
)
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    ManifestType,
    Priority,
    RecommendationCategory,
    SectionKey,
    Severity,
    SignalLevel,
    TestCoverageSignal,
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
        input_token_count=100,
        output_token_count=50,
        generation_timestamp=_NOW,
        retry_count=0,
    )


def _make_arch_section(weaknesses=None, strengths=None):
    from shared.types.analysis_types import ArchitectureSection, CouplingAnalysis

    return ArchitectureSection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        detected_pattern=ArchitecturePattern.LAYERED,
        confidence=Confidence.HIGH,
        strengths=strengths or ["Clean module boundaries"],
        weaknesses=weaknesses or [],
        coupling_analysis=CouplingAnalysis(
            overall_coupling_level=SignalLevel.LOW,
            high_coupling_file_count=0,
            dependency_violation_count=0,
            coupling_narrative="Coupling is acceptable.",
        ),
        test_coverage_signal=TestCoverageSignal.PRESENT,
        narrative="Architecture is well-structured with clear layers." * 3,
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
        narrative="Security analysis indicates low risk overall." * 3,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=_NOW,
        generation_metadata=_make_gen_metadata(),
    )


def _make_rec_section(recs=None):
    from shared.types.report_types import RecommendationSection

    recs = recs or []
    counts = {p.value: 0 for p in Priority}
    for r in recs:
        counts[r.priority.value] += 1
    no_note = "No significant findings." if not recs else None
    # no_significant_findings_note must be set when source_finding_count == 0
    src_count = len(recs)

    return RecommendationSection(
        section_id=uuid4(),
        job_id=_JOB_ID,
        executive_summary="This codebase demonstrates strong structural practices. "
                          "Key areas reviewed include coupling, security, and test coverage. "
                          "Overall risk is low and maintainability appears healthy.",
        recommendations=recs,
        actionable_next_steps=["Step 1", "Step 2", "Step 3"],
        recommendation_counts_by_priority=counts,
        generated_at=_NOW,
        generation_metadata=_make_gen_metadata(),
        source_finding_count=src_count,
        rag_chunks_used_count=0,
        no_significant_findings_note=no_note if src_count == 0 else None,
    )


def _make_manifest():
    from shared.types.manifest_types import (
        LanguageStats,
        RepositoryManifest,
    )

    return RepositoryManifest(
        manifest_id=uuid4(),
        job_id=_JOB_ID,
        repo_url="https://github.com/test/repo",
        repo_name="test/repo",
        default_branch="main",
        primary_language="Python",
        languages={
            "Python": LanguageStats(
                language="Python",
                file_count=20,
                estimated_line_count=4000,
                percentage_of_codebase=1.0,
            )
        },
        file_list=[],
        directory_tree=[],
        total_file_count=20,
        analyzable_file_count=20,
        skipped_file_count=0,
        clone_timestamp=_NOW - timedelta(minutes=5),
    )


def _make_pcr():
    from shared.types.enums import NamingConsistencySignal
    from shared.types.pcr_types import (
        ArchitectureSignals,
        CrossFileSignals,
        FileAnalysis,
        ParsedCodeRepresentation,
        ParseMetadata,
        QualitySignals,
        SecuritySignals,
    )

    file_a = FileAnalysis(
        path="main.py",
        language="Python",
        import_list=[],
        export_list=[],
        definition_summaries=[],
        max_nesting_depth=2,
        complexity_proxy=1,
        is_test_file=False,
        parse_succeeded=True,
    )

    return ParsedCodeRepresentation(
        pcr_id=uuid4(),
        job_id=_JOB_ID,
        source_manifest_id=uuid4(),
        file_analyses=[file_a],
        architecture_signals=ArchitectureSignals(cohesion_assessment=SignalLevel.HIGH),
        cross_file_signals=CrossFileSignals(),
        security_signals=SecuritySignals(),
        quality_signals=QualitySignals(
            test_presence_ratio=0.35,
            test_coverage_signal=TestCoverageSignal.PRESENT,
            naming_consistency_signal=NamingConsistencySignal.CONSISTENT,
        ),
        parse_metadata=ParseMetadata(
            files_attempted=1,
            files_parsed_successfully=1,
            files_skipped=0,
            files_with_parse_errors=0,
            languages_parsed=["Python"],
            parse_duration_ms=100,
        ),
        produced_at=_NOW - timedelta(seconds=10),
    )


# ---------------------------------------------------------------------------
# Section key and order tests
# ---------------------------------------------------------------------------


def test_executive_summary_section_key_and_order():
    sec = build_executive_summary_section(_make_rec_section(), _make_sec_section())
    assert sec.section_key == SectionKey.EXECUTIVE_SUMMARY
    assert sec.section_order == 1


def test_repository_overview_section_key_and_order():
    sec = build_repository_overview_section(_make_manifest(), _make_pcr())
    assert sec.section_key == SectionKey.REPOSITORY_OVERVIEW
    assert sec.section_order == 2


def test_architecture_assessment_section_key_and_order():
    sec = build_architecture_assessment_section(_make_arch_section())
    assert sec.section_key == SectionKey.ARCHITECTURE_ASSESSMENT
    assert sec.section_order == 3


def test_security_findings_section_key_and_order():
    sec = build_security_findings_section(_make_sec_section())
    assert sec.section_key == SectionKey.SECURITY_FINDINGS
    assert sec.section_order == 4


def test_recommendations_section_key_and_order():
    sec = build_recommendations_section(_make_rec_section())
    assert sec.section_key == SectionKey.RECOMMENDATIONS
    assert sec.section_order == 5


def test_actionable_next_steps_section_key_and_order():
    sec = build_actionable_next_steps_section(_make_rec_section())
    assert sec.section_key == SectionKey.ACTIONABLE_NEXT_STEPS
    assert sec.section_order == 6


# ---------------------------------------------------------------------------
# Content correctness
# ---------------------------------------------------------------------------


def test_security_findings_contains_disclaimer():
    from config.constants import DISCLAIMER_TEXT

    sec = build_security_findings_section(_make_sec_section())
    assert DISCLAIMER_TEXT in sec.content_markdown


def test_empty_security_findings_handled_gracefully():
    sec = build_security_findings_section(_make_sec_section(findings=[]))
    assert "No findings detected" in sec.content_markdown
    assert sec.content_markdown  # non-empty


def test_executive_summary_contains_executive_summary_text():
    rec = _make_rec_section()
    sec = build_executive_summary_section(rec, _make_sec_section())
    assert rec.executive_summary in sec.content_markdown


def test_repository_overview_contains_repo_name():
    manifest = _make_manifest()
    sec = build_repository_overview_section(manifest, _make_pcr())
    assert "test/repo" in sec.content_markdown


def test_architecture_assessment_contains_pattern():
    sec = build_architecture_assessment_section(_make_arch_section())
    assert "LAYERED" in sec.content_markdown


def test_actionable_next_steps_contains_all_steps():
    rec = _make_rec_section()
    sec = build_actionable_next_steps_section(rec)
    for step in rec.actionable_next_steps:
        assert step in sec.content_markdown


def test_all_section_content_is_non_empty_string():
    arch = _make_arch_section()
    sec_s = _make_sec_section()
    rec = _make_rec_section()
    manifest = _make_manifest()
    pcr = _make_pcr()

    sections = [
        build_executive_summary_section(rec, sec_s),
        build_repository_overview_section(manifest, pcr),
        build_architecture_assessment_section(arch),
        build_security_findings_section(sec_s),
        build_recommendations_section(rec),
        build_actionable_next_steps_section(rec),
    ]

    for section in sections:
        assert isinstance(section.content_markdown, str)
        assert len(section.content_markdown) > 0


# ---------------------------------------------------------------------------
# Metadata builder
# ---------------------------------------------------------------------------


def test_build_report_metadata_sums_tokens():
    arch = _make_arch_section()
    sec_s = _make_sec_section()
    rec = _make_rec_section()
    pcr = _make_pcr()

    start = _NOW - timedelta(seconds=30)
    end = _NOW

    meta = build_report_metadata(arch, sec_s, rec, pcr, start, end)

    # Each GenerationMetadata has input=100, output=50; 3 sections → 450
    assert meta.total_llm_tokens_used == 450


def test_build_report_metadata_duration_at_least_one():
    arch = _make_arch_section()
    sec_s = _make_sec_section()
    rec = _make_rec_section()
    pcr = _make_pcr()

    start = _NOW
    end = _NOW  # same time → delta = 0 → floor to 1

    meta = build_report_metadata(arch, sec_s, rec, pcr, start, end)
    assert meta.analysis_duration_seconds >= 1


def test_build_report_metadata_highest_severity_none_when_no_findings():
    arch = _make_arch_section()
    sec_s = _make_sec_section(findings=[])
    rec = _make_rec_section()
    pcr = _make_pcr()

    meta = build_report_metadata(arch, sec_s, rec, pcr, _NOW - timedelta(seconds=10), _NOW)
    assert meta.highest_severity_finding is None


def test_build_report_metadata_primary_language_from_pcr():
    arch = _make_arch_section()
    sec_s = _make_sec_section()
    rec = _make_rec_section()
    pcr = _make_pcr()

    meta = build_report_metadata(arch, sec_s, rec, pcr, _NOW - timedelta(seconds=10), _NOW)
    assert meta.primary_language == "Python"
