"""Architecture Agent prompt construction.

Builds the structured Gemini prompt from PCR data and rule engine outputs.
No LLM calls here — pure string construction only.
"""

from __future__ import annotations

from services.architecture_agent.rule_engine import ArchitectureRuleOutput
from shared.types.pcr_types import ParsedCodeRepresentation

SYSTEM_PROMPT = (
    "You are an expert software architect performing a structural codebase analysis. "
    "You will receive structured signals from static analysis only — no raw source code is provided. "
    "Respond with valid JSON only. "
    "Do not include markdown code fences, explanatory text, or any content outside the JSON object."
)


def build_architecture_prompt(
    pcr: ParsedCodeRepresentation,
    rule_output: ArchitectureRuleOutput,
) -> str:
    """Build the user-facing Gemini prompt for architecture analysis.

    Args:
        pcr: Parsed code representation (structural signals only).
        rule_output: Deterministic rule engine results.

    Returns:
        Prompt string to pass to GeminiClient.generate().
    """
    primary_language = (
        pcr.parse_metadata.languages_parsed[0]
        if pcr.parse_metadata.languages_parsed
        else "unknown"
    )
    languages_str = ", ".join(pcr.parse_metadata.languages_parsed) or "unknown"
    files_analyzed = pcr.parse_metadata.files_parsed_successfully

    dir_conventions = ", ".join(pcr.architecture_signals.directory_convention_signals) or "none detected"
    hub_files = ", ".join(pcr.cross_file_signals.hub_files[:5]) or "none"
    has_cycles = bool(pcr.cross_file_signals.import_cycle_indicators)
    has_layer_violations = bool(pcr.architecture_signals.layer_boundary_violations)
    large_files = len(pcr.quality_signals.large_file_indicators)

    weakness_block = _build_weakness_block(rule_output)
    weakness_schema = _build_weakness_schema(rule_output)

    return f"""Repository static analysis results:

METADATA:
  Primary language: {primary_language}
  All languages: {languages_str}
  Files analyzed: {files_analyzed}

ARCHITECTURE PATTERN (determined by rule engine — do not reassign):
  Pattern: {rule_output.detected_pattern.value}
  Confidence: {rule_output.confidence.value}
  Directory conventions observed: {dir_conventions}

COUPLING ANALYSIS:
  Overall level: {rule_output.coupling_spec.overall_coupling_level.value}
  High-coupling file count: {rule_output.coupling_spec.high_coupling_file_count}
  Dependency direction violations: {rule_output.coupling_spec.dependency_violation_count}
  Hub files (high fan-in): {hub_files}
  Circular import indicators present: {"yes" if has_cycles else "no"}
  Layer boundary violations present: {"yes" if has_layer_violations else "no"}

COHESION:
  Assessment: {rule_output.cohesion_level.value}

QUALITY SIGNALS:
  Test coverage: {rule_output.test_coverage_signal.value}
  Naming consistency: {pcr.quality_signals.naming_consistency_signal.value}
  Large files detected: {large_files}

WEAKNESSES IDENTIFIED BY RULE ENGINE (IDs, titles, and severities are final — do not change):
{weakness_block}
REQUIRED JSON OUTPUT — respond with this object and no other text:
{{
  "narrative": "<comprehensive architecture assessment, minimum 100 characters>",
  "strengths": ["<strength 1>", "<at least one more strength>"],
  "coupling_narrative": "<coupling assessment, minimum 20 characters>",
  "cohesion_narrative": <null, or a string if cohesion is notable>,
  "layer_boundary_narrative": <null, or a string describing violations if present>,
  "weakness_descriptions": {weakness_schema}
}}

Rules:
- narrative: minimum 100 characters, cover pattern confidence and overall health
- strengths: minimum 1 item; describe genuine positive structural attributes
- coupling_narrative: minimum 20 characters
- cohesion_narrative: provide text only when cohesion is LOW or HIGH; null otherwise
- layer_boundary_narrative: provide text when layer violations exist; null otherwise
- weakness_descriptions: provide description (min 20 chars) and rag_query_hint for each listed ID
- rag_query_hint: a specific semantic search phrase (e.g. "circular dependency resolution strategies")
- Use precise, technical language throughout
"""


def _build_weakness_block(rule_output: ArchitectureRuleOutput) -> str:
    if not rule_output.weakness_specs:
        return "  None detected.\n"

    lines: list[str] = []
    for ws in rule_output.weakness_specs:
        evidence_str = ", ".join(ws.evidence_refs) if ws.evidence_refs else "none"
        lines.append(f"  {ws.weakness_id}: \"{ws.title}\" [Severity: {ws.severity.name}]")
        lines.append(f"    Evidence: {evidence_str}")
    return "\n".join(lines) + "\n"


def _build_weakness_schema(rule_output: ArchitectureRuleOutput) -> str:
    if not rule_output.weakness_specs:
        return "{}"

    lines = ["{"]
    for i, ws in enumerate(rule_output.weakness_specs):
        comma = "," if i < len(rule_output.weakness_specs) - 1 else ""
        lines.append(f'    "{ws.weakness_id}": {{')
        lines.append(f'      "description": "<explanation of {ws.title}, min 20 chars>",')
        lines.append(f'      "rag_query_hint": "<semantic search query for {ws.title.lower()}>"')
        lines.append(f"    }}{comma}")
    lines.append("  }")
    return "\n  ".join(lines)
