"""Recommendation Agent service.

Orchestrates:
  1. Deterministic rule engine  → RecommendationRuleOutput
  2. Gemini LLM generation      → executive summary, per-recommendation text
  3. Section assembly           → validated RecommendationSection

Rule engine assigns all structural fields (priority, category, source IDs).
LLM generates text fields only (title, recommendation_text, rationale,
estimated_effort, context, executive_summary, actionable_next_steps).

RAGContext is optional. Pass None to skip knowledge-base grounding.
Phase 5 injects rag_context without any changes to this service.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from infrastructure.gemini_client import GeminiClient, GenerationResult
from services.recommendation_agent.prompt_builder import (
    SYSTEM_PROMPT,
    build_recommendation_prompt,
)
from services.recommendation_agent.rule_engine import (
    RecommendationRuleOutput,
    RecommendationSpec,
    run_recommendation_rules,
)
from shared.exceptions.llm_exceptions import LLMResponseParseError
from shared.logging.logger import get_logger
from shared.types.analysis_types import ArchitectureSection, GenerationMetadata, SecuritySection
from shared.types.enums import EffortEstimate
from shared.types.rag_types import RAGContext
from shared.types.report_types import Recommendation, RecommendationSection

logger = get_logger(__name__)

_NO_FINDINGS_NOTE = (
    "No significant architecture weaknesses or security findings were detected. "
    "The following recommendations are general quality improvements."
)


class RecommendationService:
    """Runs the Recommendation Agent for a single analysis job.

    Stateless — safe to instantiate once and call run() multiple times.
    Each run() call is independent.
    """

    def __init__(self, gemini_client: GeminiClient, model_id: str) -> None:
        self._gemini = gemini_client
        self._model_id = model_id

    def run(
        self,
        architecture_section: ArchitectureSection,
        security_section: SecuritySection,
        rag_context: RAGContext | None = None,
    ) -> RecommendationSection:
        """Synthesise findings into a prioritised RecommendationSection.

        Args:
            architecture_section: Output of ArchitectureAnalysisNode.
            security_section: Output of SecurityAnalysisNode.
            rag_context: Optional RAG output. None in Phase 4; injected in Phase 5.

        Returns:
            Validated RecommendationSection ready to write to AnalysisState.

        Raises:
            LLMResponseParseError: LLM returned unparseable or invalid JSON.
            Any LLMError subclass from GeminiClient on API failure.
        """
        logger.debug("RecommendationService: running rule engine", extra={
            "job_id": str(architecture_section.job_id),
        })
        rule_output = run_recommendation_rules(architecture_section, security_section, rag_context)

        if rule_output.truncated_count > 0:
            logger.warning("RecommendationService: recommendations truncated", extra={
                "truncated": rule_output.truncated_count,
                "kept": len(rule_output.specs),
            })

        prompt = build_recommendation_prompt(rule_output)

        logger.debug("RecommendationService: calling Gemini", extra={
            "job_id": str(architecture_section.job_id),
        })
        gen_timestamp = datetime.now(tz=timezone.utc)
        result = self._gemini.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)

        llm_data = self._parse_response(result.text, rule_output)
        section = self._assemble_section(
            rule_output, llm_data, gen_timestamp, architecture_section.job_id, result
        )

        logger.debug("RecommendationService: section assembled", extra={
            "job_id": str(architecture_section.job_id),
            "recommendations": len(section.recommendations),
        })
        return section

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self, response_text: str, rule_output: RecommendationRuleOutput
    ) -> dict:
        cleaned = _strip_code_fences(response_text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason=f"JSON decode failed: {exc}",
            ) from exc

        if not isinstance(data, dict):
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason=f"Expected JSON object, got {type(data).__name__}",
            )

        executive_summary = str(data.get("executive_summary", "")).strip()
        if len(executive_summary) < 100:
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason=f"executive_summary too short: {len(executive_summary)} chars (min 100)",
            )

        next_steps = data.get("actionable_next_steps", [])
        if not isinstance(next_steps, list):
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason="actionable_next_steps must be a JSON array",
            )
        next_steps = [str(s).strip() for s in next_steps if str(s).strip()]
        if len(next_steps) < 3:
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason=f"actionable_next_steps has {len(next_steps)} items (min 3)",
            )
        if len(next_steps) > 10:
            next_steps = next_steps[:10]

        recs_raw = data.get("recommendations", {})
        if not isinstance(recs_raw, dict):
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason="recommendations must be a JSON object",
            )

        return {
            "executive_summary": executive_summary,
            "actionable_next_steps": next_steps,
            "recommendations": recs_raw,
        }

    # ------------------------------------------------------------------
    # Section assembly
    # ------------------------------------------------------------------

    def _assemble_section(
        self,
        rule_output: RecommendationRuleOutput,
        llm_data: dict,
        gen_timestamp: datetime,
        job_id: UUID,
        result: GenerationResult,
    ) -> RecommendationSection:
        recommendations = self._build_recommendations(
            rule_output.specs, llm_data["recommendations"]
        )

        metadata = GenerationMetadata(
            model_id=self._model_id,
            input_token_count=result.input_tokens,
            output_token_count=result.output_tokens,
            generation_timestamp=gen_timestamp,
            retry_count=0,
        )

        no_findings_note = _NO_FINDINGS_NOTE if not rule_output.has_findings else None

        return RecommendationSection(
            section_id=uuid4(),
            job_id=job_id,
            executive_summary=llm_data["executive_summary"],
            recommendations=recommendations,
            actionable_next_steps=llm_data["actionable_next_steps"],
            recommendation_counts_by_priority=rule_output.counts_by_priority,
            generated_at=datetime.now(tz=timezone.utc),
            generation_metadata=metadata,
            source_finding_count=rule_output.source_finding_count,
            rag_chunks_used_count=rule_output.rag_chunks_used_count,
            no_significant_findings_note=no_findings_note,
        )

    def _build_recommendations(
        self,
        specs: list[RecommendationSpec],
        recs_raw: dict,
    ) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for spec in specs:
            raw = recs_raw.get(spec.recommendation_id, {})
            if not isinstance(raw, dict):
                raw = {}

            title = str(raw.get("title", "")).strip() or spec.source_title

            rec_text = str(raw.get("recommendation_text", "")).strip()
            if len(rec_text) < 30:
                rec_text = (
                    f"Address the identified {spec.source_title} issue to reduce "
                    "technical debt and associated risk."
                )

            rationale = str(raw.get("rationale", "")).strip()
            if len(rationale) < 20:
                rationale = (
                    f"Unresolved {spec.source_title} may compound over time "
                    "and increase maintenance burden."
                )

            context = str(raw.get("context", "")).strip()
            if len(context) < 10:
                context = "No specific knowledge base context was retrieved for this finding."

            effort = _parse_effort(raw.get("estimated_effort", ""))

            recommendations.append(Recommendation(
                recommendation_id=spec.recommendation_id,
                priority=spec.priority,
                title=title,
                category=spec.category,
                source_finding_ids=spec.source_finding_ids,
                rag_chunk_ids_used=spec.rag_chunk_ids,
                context=context,
                recommendation_text=rec_text,
                rationale=rationale,
                estimated_effort=effort,
            ))

        return recommendations


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_effort(value: object) -> EffortEstimate:
    raw = re.sub(r"\s*\(.*?\)", "", str(value).strip().upper()).strip()
    try:
        return EffortEstimate(raw)
    except ValueError:
        return EffortEstimate.MEDIUM
