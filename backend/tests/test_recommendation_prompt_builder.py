"""Unit tests for services/recommendation_agent/prompt_builder.py.

All tests are pure: no Gemini calls, no settings, no .env required.
Tests verify prompt structure, RAG excerpt injection, excerpt length,
KB grounding instructions, and the no-findings fallback path.
"""

from __future__ import annotations

from dataclasses import field
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.recommendation_agent.prompt_builder import (
    SYSTEM_PROMPT,
    _build_no_findings_prompt,
    _build_specs_block,
    build_recommendation_prompt,
)
from services.recommendation_agent.rule_engine import (
    RecommendationRuleOutput,
    RecommendationSpec,
)
from shared.types.enums import Priority, RecommendationCategory, Severity


# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------


def _make_spec(
    rec_id: str,
    priority: Priority,
    category: RecommendationCategory,
    source_title: str,
    source_severity: Severity,
    source_finding_ids: list[str] | None = None,
    rag_chunk_ids: list[str] | None = None,
    rag_excerpts: list[str] | None = None,
) -> RecommendationSpec:
    return RecommendationSpec(
        recommendation_id=rec_id,
        priority=priority,
        category=category,
        source_finding_ids=source_finding_ids or ["AW-001"],
        source_title=source_title,
        source_severity=source_severity,
        rag_chunk_ids=rag_chunk_ids or [],
        rag_excerpts=rag_excerpts or [],
    )


def _make_rule_output(
    specs: list[RecommendationSpec],
    rag_chunks_used_count: int = 0,
    source_finding_count: int = 1,
    truncated_count: int = 0,
    has_findings: bool = True,
) -> RecommendationRuleOutput:
    counts = {p.value: 0 for p in Priority}
    for s in specs:
        counts[s.priority.value] += 1
    return RecommendationRuleOutput(
        specs=specs,
        counts_by_priority=counts,
        source_finding_count=source_finding_count,
        rag_chunks_used_count=rag_chunks_used_count,
        has_findings=has_findings,
        truncated_count=truncated_count,
    )


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT — KB grounding instruction
# ---------------------------------------------------------------------------


def test_system_prompt_contains_kb_grounding_priority():
    assert "knowledge base" in SYSTEM_PROMPT.lower()
    assert "takes precedence" in SYSTEM_PROMPT


def test_system_prompt_requires_kb_grounding_when_excerpts_present():
    assert "MUST ground" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# _build_specs_block — no RAG excerpts
# ---------------------------------------------------------------------------


def test_specs_block_without_excerpts_shows_none_retrieved():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "SQL Injection Risk", Severity.HIGH,
    )
    block = _build_specs_block([spec])
    assert "Knowledge base context: none retrieved" in block


def test_specs_block_contains_recommendation_id():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "SQL Injection Risk", Severity.HIGH,
    )
    block = _build_specs_block([spec])
    assert "REC-001" in block


def test_specs_block_contains_priority_and_category():
    spec = _make_spec(
        "REC-001", Priority.P2, RecommendationCategory.ARCHITECTURE,
        "Layered coupling", Severity.MEDIUM,
    )
    block = _build_specs_block([spec])
    assert "[P2]" in block
    assert "[ARCHITECTURE]" in block


# ---------------------------------------------------------------------------
# _build_specs_block — with RAG excerpts
# ---------------------------------------------------------------------------


def test_specs_block_with_excerpts_shows_knowledge_base_context_header():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Injection Risk", Severity.HIGH,
        rag_excerpts=["Use parameterized queries to prevent SQL injection attacks."],
    )
    block = _build_specs_block([spec])
    assert "Knowledge base context:" in block
    assert "Knowledge base context: none retrieved" not in block


def test_specs_block_excerpt_text_appears_in_block():
    excerpt = "Always validate and sanitize user input at the boundary layer."
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Input Validation Gap", Severity.HIGH,
        rag_excerpts=[excerpt],
    )
    block = _build_specs_block([spec])
    assert excerpt in block


def test_specs_block_multiple_excerpts_all_appear():
    excerpts = [
        "First guidance: use parameterized queries.",
        "Second guidance: apply input validation at controller layer.",
        "Third guidance: encode output to prevent XSS.",
    ]
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Multi-excerpt finding", Severity.HIGH,
        rag_excerpts=excerpts,
    )
    block = _build_specs_block([spec])
    for excerpt in excerpts:
        assert excerpt in block


def test_specs_block_excerpt_numbered_with_bracket_index():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
        rag_excerpts=["First excerpt text.", "Second excerpt text."],
    )
    block = _build_specs_block([spec])
    assert "[1]" in block
    assert "[2]" in block


# ---------------------------------------------------------------------------
# Excerpt length — 500-char cap (not 300)
# ---------------------------------------------------------------------------


def test_specs_block_excerpt_not_truncated_below_500_chars():
    excerpt_490 = "B" * 490
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
        rag_excerpts=[excerpt_490],
    )
    block = _build_specs_block([spec])
    assert excerpt_490 in block


def test_specs_block_excerpt_truncated_at_500_chars():
    excerpt_600 = "C" * 600
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
        rag_excerpts=[excerpt_600],
    )
    block = _build_specs_block([spec])
    assert "C" * 500 in block
    assert "C" * 501 not in block


def test_specs_block_excerpt_at_exactly_500_chars_included_fully():
    excerpt_500 = "D" * 500
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
        rag_excerpts=[excerpt_500],
    )
    block = _build_specs_block([spec])
    assert excerpt_500 in block


# ---------------------------------------------------------------------------
# build_recommendation_prompt — full prompt structure
# ---------------------------------------------------------------------------


def test_full_prompt_contains_finding_summary_header():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Injection", Severity.HIGH,
    )
    output = _make_rule_output([spec], source_finding_count=1)
    prompt = build_recommendation_prompt(output)
    assert "FINDING SUMMARY" in prompt


def test_full_prompt_contains_rag_chunk_count_in_summary():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Injection", Severity.HIGH,
        rag_excerpts=["Some KB context text for injection."],
    )
    output = _make_rule_output([spec], rag_chunks_used_count=2, source_finding_count=1)
    prompt = build_recommendation_prompt(output)
    assert "RAG knowledge base chunks incorporated: 2" in prompt


def test_full_prompt_contains_kb_grounding_rule_for_recommendation_text():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
    )
    output = _make_rule_output([spec])
    prompt = build_recommendation_prompt(output)
    assert "knowledge base excerpts" in prompt.lower()
    assert "recommendation_text" in prompt


def test_full_prompt_contains_kb_grounding_rule_for_rationale():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
    )
    output = _make_rule_output([spec])
    prompt = build_recommendation_prompt(output)
    assert "rationale" in prompt
    assert "knowledge base excerpts" in prompt.lower()


def test_full_prompt_truncation_note_absent_when_zero_truncated():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
    )
    output = _make_rule_output([spec], truncated_count=0)
    prompt = build_recommendation_prompt(output)
    assert "lower-priority items were omitted" not in prompt


def test_full_prompt_truncation_note_present_when_truncated():
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "Test finding", Severity.HIGH,
    )
    output = _make_rule_output([spec], truncated_count=3)
    prompt = build_recommendation_prompt(output)
    assert "3 lower-priority items were omitted" in prompt


def test_full_prompt_with_rag_excerpts_contains_excerpt_text():
    excerpt = "Critical: never concatenate user input into SQL queries."
    spec = _make_spec(
        "REC-001", Priority.P1, RecommendationCategory.SECURITY,
        "SQL Injection", Severity.HIGH,
        rag_excerpts=[excerpt],
    )
    output = _make_rule_output([spec], rag_chunks_used_count=1)
    prompt = build_recommendation_prompt(output)
    assert excerpt in prompt


def test_full_prompt_routes_to_no_findings_when_no_findings():
    output = _make_rule_output([], has_findings=False, source_finding_count=0)
    prompt = build_recommendation_prompt(output)
    assert "no significant" in prompt.lower()
    assert "FINDING SUMMARY" not in prompt


# ---------------------------------------------------------------------------
# _build_no_findings_prompt
# ---------------------------------------------------------------------------


def test_no_findings_prompt_requests_empty_recommendations_object():
    prompt = _build_no_findings_prompt()
    assert '"recommendations": {}' in prompt


def test_no_findings_prompt_still_requests_executive_summary():
    prompt = _build_no_findings_prompt()
    assert "executive_summary" in prompt


def test_no_findings_prompt_still_requests_actionable_next_steps():
    prompt = _build_no_findings_prompt()
    assert "actionable_next_steps" in prompt
