"""Security Analysis Agent service.

Orchestrates the three-step process:
  1. Deterministic rule engine  → list[FindingSpec]
  2. Gemini LLM generation      → narrative + per-finding descriptions
  3. Section assembly           → validated SecuritySection

GeminiClient.generate() is the only external call. All severity, OWASP,
CWE, and confidence assignments are performed by the rule engine. The LLM
generates text only and never changes any deterministic field.

Disclaimer text and is_confirmed_vulnerability are structurally enforced by
the SecuritySection schema — they cannot be modified by this service or the LLM.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from config.constants import DISCLAIMER_TEXT
from infrastructure.gemini_client import GeminiClient
from services.security_agent.prompt_builder import (
    SYSTEM_PROMPT,
    build_security_prompt,
)
from services.security_agent.rule_engine import FindingSpec, generate_findings
from shared.exceptions.llm_exceptions import LLMResponseParseError
from shared.logging.logger import get_logger
from shared.types.analysis_types import (
    GenerationMetadata,
    SecurityFinding,
    SecuritySection,
)
from shared.types.enums import Severity
from shared.types.pcr_types import ParsedCodeRepresentation

logger = get_logger(__name__)


class SecurityService:
    """Runs the Security Analysis Agent for a single analysis job.

    Stateless — safe to instantiate once and call run() multiple times.
    Each run() call is independent.
    """

    def __init__(self, gemini_client: GeminiClient, model_id: str) -> None:
        self._gemini = gemini_client
        self._model_id = model_id

    def run(self, pcr: ParsedCodeRepresentation) -> SecuritySection:
        """Analyse security signals from a ParsedCodeRepresentation.

        Args:
            pcr: Fully populated PCR from ParseNode.

        Returns:
            Validated SecuritySection ready to write to AnalysisState.

        Raises:
            LLMResponseParseError: LLM returned unparseable or invalid JSON.
            Any LLMError subclass from GeminiClient on API failure.
            ValidationError: Assembled section fails Pydantic invariants
                             (indicates a programming bug, not LLM failure).
        """
        logger.debug("SecurityService: running rule engine", extra={"job_id": str(pcr.job_id)})
        finding_specs = generate_findings(pcr.security_signals)

        prompt = build_security_prompt(pcr, finding_specs)

        logger.debug("SecurityService: calling Gemini", extra={"job_id": str(pcr.job_id)})
        gen_timestamp = datetime.now(tz=timezone.utc)
        response_text = self._gemini.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)

        llm_data = self._parse_response(response_text, finding_specs)

        section = self._assemble_section(pcr, finding_specs, llm_data, gen_timestamp)

        logger.debug("SecurityService: section assembled", extra={
            "job_id": str(pcr.job_id),
            "findings": len(section.findings),
            "overall_risk": section.overall_risk_level.name,
        })
        return section

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, response_text: str, finding_specs: list[FindingSpec]) -> dict:
        """Parse and validate the LLM JSON response.

        Strips markdown code fences if present. Raises LLMResponseParseError
        on structural problems.
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

        finding_descriptions = data.get("finding_descriptions", {})
        if not isinstance(finding_descriptions, dict):
            finding_descriptions = {}

        return {
            "narrative": narrative,
            "finding_descriptions": finding_descriptions,
        }

    # ------------------------------------------------------------------
    # Section assembly
    # ------------------------------------------------------------------

    def _assemble_section(
        self,
        pcr: ParsedCodeRepresentation,
        finding_specs: list[FindingSpec],
        llm_data: dict,
        gen_timestamp: datetime,
    ) -> SecuritySection:
        findings = _build_findings(finding_specs, llm_data, self._model_id)
        overall_risk = _compute_overall_risk(findings)
        counts = _compute_severity_counts(findings)

        metadata = GenerationMetadata(
            model_id=self._model_id,
            input_token_count=0,
            output_token_count=0,
            generation_timestamp=gen_timestamp,
            retry_count=0,
        )

        return SecuritySection(
            section_id=uuid4(),
            job_id=pcr.job_id,
            findings=findings,
            overall_risk_level=overall_risk,
            finding_counts_by_severity=counts,
            narrative=llm_data["narrative"],
            disclaimer=DISCLAIMER_TEXT,
            generated_at=datetime.now(tz=timezone.utc),
            generation_metadata=metadata,
            dependency_risk_signals=None,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _build_findings(
    finding_specs: list[FindingSpec],
    llm_data: dict,
    model_id: str,
) -> list[SecurityFinding]:
    """Combine rule engine FindingSpec entries with LLM-generated descriptions."""
    descriptions = llm_data.get("finding_descriptions", {})
    findings: list[SecurityFinding] = []

    for spec in finding_specs:
        raw_desc = descriptions.get(spec.finding_id, "")
        description = str(raw_desc).strip()
        if len(description) < 20:
            description = (
                f"{spec.title}: static analysis signals may indicate a potential risk "
                "requiring manual security review."
            )

        findings.append(SecurityFinding(
            finding_id=spec.finding_id,
            title=spec.title,
            severity=spec.severity,
            confidence=spec.confidence,
            owasp_category=spec.owasp_category,
            cwe_id=spec.cwe_id,
            evidence_refs=spec.evidence_refs,
            description=description,
        ))

    return findings


def _compute_overall_risk(findings: list[SecurityFinding]) -> Severity:
    """Return the highest severity level among findings, or INFO if empty."""
    if not findings:
        return Severity.INFO
    return max(f.severity for f in findings)


def _compute_severity_counts(findings: list[SecurityFinding]) -> dict[str, int]:
    """Build a per-severity count dict consistent with the findings list."""
    counts: dict[str, int] = {level.name: 0 for level in Severity}
    for f in findings:
        counts[f.severity.name] += 1
    return counts


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap JSON output in."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
