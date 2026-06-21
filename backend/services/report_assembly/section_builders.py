"""Report Assembly section builders.

One pure function per SectionKey. Each function takes exactly the data it
needs and returns a validated ReportSection. No side effects, no LLM calls,
no external I/O.

Section order follows SECTION_ORDER from config/constants.py:
  1. EXECUTIVE_SUMMARY
  2. REPOSITORY_OVERVIEW
  3. ARCHITECTURE_ASSESSMENT
  4. SECURITY_FINDINGS
  5. RECOMMENDATIONS
  6. ACTIONABLE_NEXT_STEPS
"""

from __future__ import annotations

from config.constants import DISCLAIMER_TEXT
from shared.types.analysis_types import ArchitectureSection, SecuritySection
from shared.types.enums import SectionKey
from shared.types.manifest_types import RepositoryManifest
from shared.types.pcr_types import ParsedCodeRepresentation
from shared.types.report_types import Recommendation, RecommendationSection, ReportSection


def build_executive_summary_section(
    recommendations_section: RecommendationSection,
    security_section: SecuritySection,
) -> ReportSection:
    """Build the Executive Summary section (order 1)."""
    p1_count = recommendations_section.recommendation_counts_by_priority.get("P1", 0)
    total_recs = len(recommendations_section.recommendations)
    risk = security_section.overall_risk_level.name

    content = (
        f"## Executive Summary\n\n"
        f"{recommendations_section.executive_summary}\n\n"
        f"**Overall Security Risk Level:** {risk}  \n"
        f"**P1 (Immediate Action) Recommendations:** {p1_count}  \n"
        f"**Total Recommendations:** {total_recs}  \n"
        f"**RAG Knowledge Base Chunks Used:** {recommendations_section.rag_chunks_used_count}\n"
    )

    if recommendations_section.no_significant_findings_note:
        content += f"\n> {recommendations_section.no_significant_findings_note}\n"

    return ReportSection(
        section_order=1,
        section_key=SectionKey.EXECUTIVE_SUMMARY,
        section_title="Executive Summary",
        content_markdown=content,
    )


def build_repository_overview_section(
    repository_manifest: RepositoryManifest,
    pcr: ParsedCodeRepresentation,
) -> ReportSection:
    """Build the Repository Overview section (order 2)."""
    meta = pcr.parse_metadata
    lang_rows = "\n".join(
        f"| {name} | {stats.file_count} | {stats.estimated_line_count:,} "
        f"| {stats.percentage_of_codebase:.0%} |"
        for name, stats in repository_manifest.languages.items()
    )

    dep_count = 0
    if repository_manifest.dependency_manifests:
        dep_count = sum(
            len(m.dependencies) + len(m.dev_dependencies)
            for m in repository_manifest.dependency_manifests.values()
        )

    frameworks = (
        ", ".join(repository_manifest.detected_frameworks)
        if repository_manifest.detected_frameworks
        else "None detected"
    )

    content = (
        f"## Repository Overview\n\n"
        f"**Repository:** {repository_manifest.repo_name}  \n"
        f"**Branch:** {repository_manifest.default_branch}  \n"
        f"**Primary Language:** {repository_manifest.primary_language}  \n"
        f"**Detected Frameworks:** {frameworks}\n\n"
        f"### File Statistics\n\n"
        f"| Metric | Count |\n"
        f"|---|---|\n"
        f"| Total Files | {repository_manifest.total_file_count} |\n"
        f"| Analyzable Files | {repository_manifest.analyzable_file_count} |\n"
        f"| Successfully Parsed | {meta.files_parsed_successfully} |\n"
        f"| Skipped | {meta.files_skipped} |\n"
        f"| Parse Errors | {meta.files_with_parse_errors} |\n\n"
        f"### Language Breakdown\n\n"
        f"| Language | Files | Lines (est.) | Share |\n"
        f"|---|---|---|---|\n"
        f"{lang_rows}\n\n"
        f"### Dependencies\n\n"
        f"**Total declared dependencies:** {dep_count}  \n"
    )

    if repository_manifest.dependency_manifests:
        for mtype, manifest in repository_manifest.dependency_manifests.items():
            rt = len(manifest.dependencies)
            dev = len(manifest.dev_dependencies)
            content += f"- `{mtype}`: {rt} runtime, {dev} dev\n"

    return ReportSection(
        section_order=2,
        section_key=SectionKey.REPOSITORY_OVERVIEW,
        section_title="Repository Overview",
        content_markdown=content,
    )


def build_architecture_assessment_section(
    architecture_section: ArchitectureSection,
) -> ReportSection:
    """Build the Architecture Assessment section (order 3)."""
    strengths = "\n".join(f"- {s}" for s in architecture_section.strengths) or "- None noted."

    weakness_rows = "\n".join(
        f"| {w.weakness_id} | {w.title} | {w.severity.name} |"
        for w in architecture_section.weaknesses
    ) or "| — | No weaknesses detected | — |"

    coupling = architecture_section.coupling_analysis
    cohesion = (
        f"\n**Cohesion Assessment:**\n\n{architecture_section.cohesion_narrative}\n"
        if architecture_section.cohesion_narrative
        else ""
    )
    layer = (
        f"\n**Layer Boundary Assessment:**\n\n{architecture_section.layer_boundary_narrative}\n"
        if architecture_section.layer_boundary_narrative
        else ""
    )

    content = (
        f"## Architecture Assessment\n\n"
        f"**Detected Pattern:** {architecture_section.detected_pattern.value}  \n"
        f"**Confidence:** {architecture_section.confidence.value}  \n"
        f"**Test Coverage Signal:** {architecture_section.test_coverage_signal.value}\n\n"
        f"### Narrative\n\n"
        f"{architecture_section.narrative}\n\n"
        f"### Strengths\n\n"
        f"{strengths}\n\n"
        f"### Weaknesses\n\n"
        f"| ID | Title | Severity |\n"
        f"|---|---|---|\n"
        f"{weakness_rows}\n\n"
        f"### Coupling Analysis\n\n"
        f"**Overall Coupling Level:** {coupling.overall_coupling_level.value}  \n"
        f"**High-Coupling Files:** {coupling.high_coupling_file_count}  \n"
        f"**Dependency Violations:** {coupling.dependency_violation_count}\n\n"
        f"{coupling.coupling_narrative}"
        f"{cohesion}"
        f"{layer}"
    )

    return ReportSection(
        section_order=3,
        section_key=SectionKey.ARCHITECTURE_ASSESSMENT,
        section_title="Architecture Assessment",
        content_markdown=content,
    )


def build_security_findings_section(security_section: SecuritySection) -> ReportSection:
    """Build the Security Findings section (order 4)."""
    finding_rows = "\n".join(
        f"| {f.finding_id} | {f.title} | {f.severity.name} "
        f"| {f.owasp_category.value if f.owasp_category else '—'} "
        f"| {f.cwe_id or '—'} |"
        for f in security_section.findings
    ) or "| — | No findings detected | — | — | — |"

    counts = security_section.finding_counts_by_severity
    severity_summary = "  ".join(
        f"**{k}:** {v}" for k, v in counts.items() if v > 0
    ) or "No findings."

    content = (
        f"## Security Findings\n\n"
        f"> **Advisory Disclaimer:** {DISCLAIMER_TEXT}\n\n"
        f"**Overall Risk Level:** {security_section.overall_risk_level.name}  \n"
        f"{severity_summary}\n\n"
        f"### Narrative\n\n"
        f"{security_section.narrative}\n\n"
        f"### Findings\n\n"
        f"| ID | Title | Severity | OWASP | CWE |\n"
        f"|---|---|---|---|---|\n"
        f"{finding_rows}\n"
    )

    return ReportSection(
        section_order=4,
        section_key=SectionKey.SECURITY_FINDINGS,
        section_title="Security Findings",
        content_markdown=content,
    )


def build_recommendations_section(
    recommendations_section: RecommendationSection,
) -> ReportSection:
    """Build the Recommendations section (order 5)."""
    summary_rows = "\n".join(
        f"| {r.recommendation_id} | {r.priority.value} | {r.category.value} "
        f"| {r.title} | {r.estimated_effort.value} |"
        for r in recommendations_section.recommendations
    ) or "| — | — | — | No recommendations | — |"

    detail_blocks = "\n\n".join(
        _build_recommendation_block(r)
        for r in recommendations_section.recommendations
    )

    content = (
        f"## Recommendations\n\n"
        f"| ID | Priority | Category | Title | Effort |\n"
        f"|---|---|---|---|---|\n"
        f"{summary_rows}\n\n"
    )

    if detail_blocks:
        content += f"### Details\n\n{detail_blocks}\n"

    return ReportSection(
        section_order=5,
        section_key=SectionKey.RECOMMENDATIONS,
        section_title="Recommendations",
        content_markdown=content,
    )


def build_actionable_next_steps_section(
    recommendations_section: RecommendationSection,
) -> ReportSection:
    """Build the Actionable Next Steps section (order 6)."""
    steps = "\n".join(
        f"{i}. {step}"
        for i, step in enumerate(recommendations_section.actionable_next_steps, start=1)
    )

    content = f"## Actionable Next Steps\n\n{steps}\n"

    return ReportSection(
        section_order=6,
        section_key=SectionKey.ACTIONABLE_NEXT_STEPS,
        section_title="Actionable Next Steps",
        content_markdown=content,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_recommendation_block(rec: Recommendation) -> str:
    sources = ", ".join(rec.source_finding_ids)
    return (
        f"#### {rec.recommendation_id}: {rec.title}\n\n"
        f"**Priority:** {rec.priority.value} | "
        f"**Category:** {rec.category.value} | "
        f"**Effort:** {rec.estimated_effort.value} (estimate)  \n"
        f"**Source Findings:** {sources}\n\n"
        f"{rec.recommendation_text}\n\n"
        f"**Rationale:** {rec.rationale}\n"
    )
