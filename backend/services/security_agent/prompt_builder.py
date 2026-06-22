"""Security Agent prompt construction.

Builds the structured Gemini prompt from PCR metadata and rule engine outputs.
No LLM calls here — pure string construction only.

Security constraint: no raw source code, no secret literal values, no
actual credential content ever enters the prompt. Evidence references
contain file paths and context descriptions only.
"""

from __future__ import annotations

from services.security_agent.rule_engine import FindingSpec
from shared.types.pcr_types import ParsedCodeRepresentation

SYSTEM_PROMPT = (
    "You are an expert security analyst reviewing static analysis signals from a software codebase. "
    "These signals are NOT confirmed vulnerabilities — they are structural risk indicators only. "
    "You MUST use qualified language throughout your response: "
    "'may indicate', 'could suggest', 'signals a potential risk', 'warrants review'. "
    "Never state findings as confirmed. Never claim a vulnerability is definitely present. "
    "Respond with valid JSON only. "
    "Do not include markdown code fences, explanatory text, or any content outside the JSON object."
)


def build_security_prompt(
    pcr: ParsedCodeRepresentation,
    finding_specs: list[FindingSpec],
) -> str:
    """Build the user-facing Gemini prompt for security analysis.

    Args:
        pcr: Parsed code representation for contextual metadata.
        finding_specs: Rule-engine-generated findings with all deterministic fields set.

    Returns:
        Prompt string to pass to GeminiClient.generate().
    """
    primary_language = (
        pcr.parse_metadata.languages_parsed[0]
        if pcr.parse_metadata.languages_parsed
        else "unknown"
    )
    files_analyzed = pcr.parse_metadata.files_parsed_successfully

    findings_block = _build_findings_block(finding_specs)
    descriptions_schema = _build_descriptions_schema(finding_specs)

    no_findings_note = (
        "\nNo security risk signals were detected by the static analysis rule engine.\n"
        if not finding_specs
        else ""
    )

    rag_hints_schema = _build_rag_hints_schema(finding_specs)

    return f"""Repository static analysis security signals:

METADATA:
  Primary language: {primary_language}
  Files analyzed: {files_analyzed}

FINDINGS IDENTIFIED BY RULE ENGINE (severity, OWASP, and CWE are final — do not reassign):
{findings_block}{no_findings_note}
REQUIRED JSON OUTPUT — respond with this object and no other text:
{{
  "narrative": "<security assessment narrative using qualified language, minimum 100 characters>",
  "finding_descriptions": {descriptions_schema},
  "rag_query_hints": {rag_hints_schema}
}}

Rules:
- narrative: minimum 100 characters; summarise overall security posture using qualified language
- narrative must NOT claim any finding is a confirmed vulnerability
- finding_descriptions: provide one description per finding ID shown above
- Each description: minimum 20 characters; must use qualified language
- rag_query_hints: concise semantic search query per finding for retrieving remediation guidance
- Each rag_query_hint: describe the vulnerability class and remediation approach (10-80 chars)
- Do not invent finding IDs not listed above
- Do not reassign or modify severity, OWASP, or CWE values
"""


def _build_findings_block(finding_specs: list[FindingSpec]) -> str:
    if not finding_specs:
        return "  None detected.\n"

    lines: list[str] = []
    for fs in finding_specs:
        owasp = fs.owasp_category.value if fs.owasp_category else "N/A"
        cwe = fs.cwe_id or "N/A"
        lines.append(
            f"  {fs.finding_id}: \"{fs.title}\" "
            f"[Severity: {fs.severity.name} | Confidence: {fs.confidence.value} | "
            f"OWASP: {owasp} | CWE: {cwe}]"
        )
        for ref in fs.evidence_refs[:3]:
            lines.append(f"    - {ref.file_path}: {ref.context_description}")
    return "\n".join(lines) + "\n"


def _build_rag_hints_schema(finding_specs: list[FindingSpec]) -> str:
    if not finding_specs:
        return "{}"

    lines = ["{"]
    for i, fs in enumerate(finding_specs):
        comma = "," if i < len(finding_specs) - 1 else ""
        owasp = fs.owasp_category.value if fs.owasp_category else "security vulnerability"
        lines.append(
            f'    "{fs.finding_id}": '
            f'"<semantic query for {owasp} remediation guidance>"{comma}'
        )
    lines.append("  }")
    return "\n  ".join(lines)


def _build_descriptions_schema(finding_specs: list[FindingSpec]) -> str:
    if not finding_specs:
        return "{}"

    lines = ["{"]
    for i, fs in enumerate(finding_specs):
        comma = "," if i < len(finding_specs) - 1 else ""
        lines.append(
            f'    "{fs.finding_id}": '
            f'"<description of {fs.title} using qualified language, min 20 chars>"{comma}'
        )
    lines.append("  }")
    return "\n  ".join(lines)
