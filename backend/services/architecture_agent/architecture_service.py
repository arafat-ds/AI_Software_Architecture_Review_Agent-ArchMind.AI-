"""Architecture Analysis Agent service.

Orchestrates the three-step process:
  1. Deterministic rule engine  → ArchitectureRuleOutput
  2. Gemini LLM generation      → narrative text + weakness descriptions
  3. Section assembly           → validated ArchitectureSection

GeminiClient.generate() is the only external call. All classification,
severity assignment, and structural measurement is performed by the rule engine.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from infrastructure.gemini_client import GeminiClient, GenerationResult
from services.architecture_agent.prompt_builder import (
    SYSTEM_PROMPT,
    build_architecture_prompt,
)
from services.architecture_agent.rule_engine import (
    ArchitectureRuleOutput,
    WeaknessSpec,
    run_architecture_rules,
)
from shared.exceptions.llm_exceptions import LLMResponseParseError
from shared.logging.logger import get_logger
from shared.types.analysis_types import (
    ArchitectureSection,
    ArchitectureWeakness,
    CouplingAnalysis,
    GenerationMetadata,
)
from shared.types.pcr_types import ParsedCodeRepresentation

logger = get_logger(__name__)


class ArchitectureService:
    """Runs the Architecture Analysis Agent for a single analysis job.

    Stateless — safe to instantiate once and call run() multiple times.
    Each run() call is independent.
    """

    def __init__(self, gemini_client: GeminiClient, model_id: str) -> None:
        self._gemini = gemini_client
        self._model_id = model_id

    def run(self, pcr: ParsedCodeRepresentation) -> ArchitectureSection:
        """Analyse the architecture from a ParsedCodeRepresentation.

        Args:
            pcr: Fully populated PCR from ParseNode.

        Returns:
            Validated ArchitectureSection ready to write to AnalysisState.

        Raises:
            LLMResponseParseError: LLM returned unparseable or invalid JSON.
            Any LLMError subclass from GeminiClient on API failure.
            ValidationError: Assembled section fails Pydantic invariants
                             (indicates a programming bug, not LLM failure).
        """
        logger.debug("ArchitectureService: running rule engine", extra={"job_id": str(pcr.job_id)})
        rule_output = run_architecture_rules(pcr)

        prompt = build_architecture_prompt(pcr, rule_output)

        logger.debug("ArchitectureService: calling Gemini", extra={"job_id": str(pcr.job_id)})
        gen_timestamp = datetime.now(tz=timezone.utc)
        result = self._gemini.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)

        llm_data = self._parse_response(result.text)

        section = self._assemble_section(pcr, rule_output, llm_data, gen_timestamp, result)

        logger.debug("ArchitectureService: section assembled", extra={
            "job_id": str(pcr.job_id),
            "pattern": section.detected_pattern.value,
            "weaknesses": len(section.weaknesses),
            "strengths": len(section.strengths),
        })
        return section

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, response_text: str) -> dict:
        """Parse and validate the LLM JSON response.

        Strips markdown code fences if present before parsing.
        Raises LLMResponseParseError on any structural problem.
        """
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

        narrative = str(data.get("narrative", "")).strip()
        if len(narrative) < 50:
            raise LLMResponseParseError(
                model_id=self._model_id,
                reason=f"narrative too short: {len(narrative)} chars (min 50)",
            )

        strengths = data.get("strengths", [])
        if not isinstance(strengths, list) or not strengths:
            strengths = ["No critical structural issues detected in this codebase."]
        strengths = [str(s).strip() for s in strengths if str(s).strip()]
        if not strengths:
            strengths = ["No critical structural issues detected in this codebase."]

        coupling_narrative = str(data.get("coupling_narrative", "")).strip()
        if len(coupling_narrative) < 10:
            coupling_narrative = "Coupling assessment could not be determined from available signals."

        weakness_descriptions = data.get("weakness_descriptions", {})
        if not isinstance(weakness_descriptions, dict):
            weakness_descriptions = {}

        return {
            "narrative": narrative,
            "strengths": strengths,
            "coupling_narrative": coupling_narrative,
            "cohesion_narrative": _optional_str(data.get("cohesion_narrative")),
            "layer_boundary_narrative": _optional_str(data.get("layer_boundary_narrative")),
            "weakness_descriptions": weakness_descriptions,
        }

    # ------------------------------------------------------------------
    # Section assembly
    # ------------------------------------------------------------------

    def _assemble_section(
        self,
        pcr: ParsedCodeRepresentation,
        rule_output: ArchitectureRuleOutput,
        llm_data: dict,
        gen_timestamp: datetime,
        result: GenerationResult,
    ) -> ArchitectureSection:
        weaknesses = _build_weaknesses(rule_output.weakness_specs, llm_data)

        coupling = CouplingAnalysis(
            overall_coupling_level=rule_output.coupling_spec.overall_coupling_level,
            high_coupling_file_count=rule_output.coupling_spec.high_coupling_file_count,
            dependency_violation_count=rule_output.coupling_spec.dependency_violation_count,
            coupling_narrative=llm_data["coupling_narrative"],
        )

        metadata = GenerationMetadata(
            model_id=self._model_id,
            input_token_count=result.input_tokens,
            output_token_count=result.output_tokens,
            generation_timestamp=gen_timestamp,
            retry_count=0,
        )

        secondary = rule_output.secondary_pattern_keys if rule_output.secondary_pattern_keys else None

        return ArchitectureSection(
            section_id=uuid4(),
            job_id=pcr.job_id,
            detected_pattern=rule_output.detected_pattern,
            confidence=rule_output.confidence,
            strengths=llm_data["strengths"],
            weaknesses=weaknesses,
            coupling_analysis=coupling,
            test_coverage_signal=rule_output.test_coverage_signal,
            narrative=llm_data["narrative"],
            generated_at=datetime.now(tz=timezone.utc),
            generation_metadata=metadata,
            secondary_pattern_indicators=secondary,
            cohesion_narrative=llm_data["cohesion_narrative"],
            layer_boundary_narrative=llm_data["layer_boundary_narrative"],
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _build_weaknesses(
    weakness_specs: list[WeaknessSpec],
    llm_data: dict,
) -> list[ArchitectureWeakness]:
    """Combine rule engine WeaknessSpec entries with LLM-generated descriptions."""
    descriptions = llm_data.get("weakness_descriptions", {})
    weaknesses: list[ArchitectureWeakness] = []

    for spec in weakness_specs:
        raw = descriptions.get(spec.weakness_id, {})
        if isinstance(raw, dict):
            description = str(raw.get("description", "")).strip()
            rag_query_hint = str(raw.get("rag_query_hint", "")).strip()
        else:
            description = ""
            rag_query_hint = ""

        if len(description) < 10:
            description = f"{spec.title}: structural signal detected requiring architectural attention."
        if len(rag_query_hint) < 10:
            rag_query_hint = f"best practices for resolving {spec.title.lower()}"

        weaknesses.append(ArchitectureWeakness(
            weakness_id=spec.weakness_id,
            title=spec.title,
            severity=spec.severity,
            description=description,
            evidence_refs=spec.evidence_refs,
            rag_query_hint=rag_query_hint,
        ))

    return weaknesses


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap JSON output in."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _optional_str(value: object) -> str | None:
    """Convert a value to a non-empty string or None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
