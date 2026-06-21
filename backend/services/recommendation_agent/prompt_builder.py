"""Recommendation Agent prompt construction.

Builds the Gemini prompt from RecommendationRuleOutput. No LLM calls here.

When rag_excerpts are present on a spec, includes a knowledge base context
block in the prompt. Omits the block when absent.

Two prompt variants:
  - has_findings=True:  full recommendation generation prompt.
  - has_findings=False: brief prompt requesting executive summary and
    actionable_next_steps only, with empty recommendations object.
"""

from __future__ import annotations

from services.recommendation_agent.rule_engine import RecommendationRuleOutput, RecommendationSpec

SYSTEM_PROMPT = (
    "You are a senior software engineering consultant synthesising a codebase analysis. "
    "You will receive structured signals from static analysis tools. "
    "Respond with valid JSON only. "
    "Do not include markdown code fences, explanatory text, "
    "or any content outside the JSON object."
)


def build_recommendation_prompt(rule_output: RecommendationRuleOutput) -> str:
    """Build the Gemini prompt for recommendation synthesis.

    Args:
        rule_output: Deterministic rule engine output with all specs.

    Returns:
        Prompt string to pass to GeminiClient.generate().
    """
    if not rule_output.has_findings:
        return _build_no_findings_prompt()

    specs_block = _build_specs_block(rule_output.specs)
    json_schema = _build_json_schema(rule_output.specs)
    truncation_note = (
        f"  (Note: {rule_output.truncated_count} lower-priority items were omitted "
        "due to the 15-recommendation cap.)"
        if rule_output.truncated_count > 0
        else ""
    )

    return f"""Static analysis findings requiring recommendation synthesis:

FINDING SUMMARY:
  Total source findings (weaknesses + security): {rule_output.source_finding_count}
  Recommendations to generate: {len(rule_output.specs)}
  RAG knowledge base chunks incorporated: {rule_output.rag_chunks_used_count}
{truncation_note}

FINDINGS (IDs, priorities, categories, and severities are final — do not change):
{specs_block}
REQUIRED JSON OUTPUT — respond with this object and no other text:
{{
  "executive_summary": "<overall codebase health assessment, min 150 chars>",
  "actionable_next_steps": ["<most urgent step>", "<step 2>", "<min 3, max 10 items>"],
  "recommendations": {json_schema}
}}

Rules:
- executive_summary: synthesise overall risk and health across all findings. Min 150 chars.
- actionable_next_steps: 3 to 10 concrete steps ordered most-urgent-first.
- For each recommendation ID listed:
    - title: short action-oriented title, max 80 chars.
    - recommendation_text: specific, actionable guidance. Min 30 chars. No prescribing exact code.
    - rationale: why the issue matters and risk if ignored. Min 20 chars.
    - estimated_effort: one of "LOW", "MEDIUM", "HIGH". Append " (estimate)" qualifier.
    - context: if knowledge base excerpts are provided, synthesise them. If none, draw on
      general engineering best practices for that finding type. Min 10 chars.
- Use precise, technical language throughout.
- Do not alter recommendation IDs, priorities, or categories.
"""


def _build_no_findings_prompt() -> str:
    return (
        "Static analysis found no significant architecture weaknesses or security findings.\n\n"
        "REQUIRED JSON OUTPUT — respond with this object and no other text:\n"
        "{\n"
        '  "executive_summary": "<positive assessment with general maintenance advice, min 150 chars>",\n'
        '  "actionable_next_steps": ["<step 1>", "<step 2>", "<min 3, max 10 items>"],\n'
        '  "recommendations": {}\n'
        "}\n\n"
        "Rules:\n"
        "- executive_summary: affirm good practices and suggest proactive improvements. Min 150 chars.\n"
        "- actionable_next_steps: 3 to 10 general quality improvement steps.\n"
        "- recommendations: must be an empty JSON object {}.\n"
    )


def _build_specs_block(specs: list[RecommendationSpec]) -> str:
    lines: list[str] = []
    for spec in specs:
        lines.append(
            f"  {spec.recommendation_id}: [{spec.priority.value}] "
            f"[{spec.category.value}] \"{spec.source_title}\" "
            f"(Severity: {spec.source_severity.name})"
        )
        lines.append(f"    Source: {', '.join(spec.source_finding_ids)}")
        if spec.rag_excerpts:
            lines.append("    Knowledge base context:")
            for i, excerpt in enumerate(spec.rag_excerpts, start=1):
                lines.append(f"      [{i}] {excerpt[:300]}")
        else:
            lines.append("    Knowledge base context: none retrieved")
        lines.append("")
    return "\n".join(lines)


def _build_json_schema(specs: list[RecommendationSpec]) -> str:
    if not specs:
        return "{}"

    lines = ["{"]
    for i, spec in enumerate(specs):
        comma = "," if i < len(specs) - 1 else ""
        lines.append(f'    "{spec.recommendation_id}": {{')
        lines.append(f'      "title": "<action-oriented title for {spec.source_title}>",')
        lines.append(
            f'      "recommendation_text": "<specific guidance to address {spec.source_title}>",')
        lines.append(f'      "rationale": "<why this matters and risk if not addressed>",')
        lines.append(f'      "estimated_effort": "LOW|MEDIUM|HIGH (estimate)",')
        lines.append(
            f'      "context": "<synthesised knowledge base context or general best practices>"')
        lines.append(f"    }}{comma}")
    lines.append("  }")
    return "\n  ".join(lines)
