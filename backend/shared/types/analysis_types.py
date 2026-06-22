"""Data contracts for agent analysis output sections.

Contains the output contracts for the Architecture Agent and Security Agent,
plus the shared GenerationMetadata type used by both.

Security contract invariants enforced at the schema level:
- SecurityFinding.is_confirmed_vulnerability is always False (Literal type).
- SecuritySection.disclaimer always equals the approved fixed text.
- Severity is always assigned by the rule engine, never by LLM.

Dependency rule: imports only from shared/types/enums, config/constants,
and stdlib/pydantic.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from config.constants import DISCLAIMER_TEXT
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    OWASPCategory,
    Severity,
    SignalLevel,
    TestCoverageSignal,
)


# ---------------------------------------------------------------------------
# Shared generation metadata
# ---------------------------------------------------------------------------


class GenerationMetadata(BaseModel):
    """Metadata recorded for each Gemini API generation call.

    Attached to every agent output section to support cost monitoring,
    audit logging, and prompt regression analysis.
    """

    model_id: str = Field(
        ..., description="Gemini model identifier used for this generation call."
    )
    input_token_count: int = Field(
        ..., ge=0, description="Number of tokens in the prompt sent to the model."
    )
    output_token_count: int = Field(
        ..., ge=0, description="Number of tokens in the model's response."
    )
    generation_timestamp: datetime = Field(
        ..., description="UTC timestamp when the LLM call completed."
    )
    retry_count: int = Field(
        ...,
        ge=0,
        description="Number of retries required before a successful response. 0 = first attempt succeeded.",
    )


# ---------------------------------------------------------------------------
# Architecture Agent output
# ---------------------------------------------------------------------------


class ArchitectureWeakness(BaseModel):
    """A single identified architectural weakness or structural problem.

    Severity is assigned by the Architecture Agent rule engine. The LLM
    generates the description and rag_query_hint fields only.
    """

    weakness_id: str = Field(
        ...,
        description=(
            "Scoped unique identifier within the ArchitectureSection. "
            "Format: 'AW-NNN' where NNN is zero-padded to three digits (e.g. 'AW-001')."
        ),
    )
    title: str = Field(..., description="Short descriptive title for the weakness.")
    severity: Severity = Field(
        ..., description="Severity assigned by the rule engine. Not assigned by LLM."
    )
    description: str = Field(
        ..., description="LLM-generated explanation of the weakness and its implications."
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Relative file paths from the PCR that provide structural evidence "
            "for this weakness."
        ),
    )
    rag_query_hint: str = Field(
        ...,
        description=(
            "Suggested semantic query for RAG retrieval targeting this weakness. "
            "Used by RAGRetrievalNode to find relevant knowledge base context."
        ),
    )

    @field_validator("weakness_id", mode="before")
    @classmethod
    def validate_weakness_id_format(cls, value: str) -> str:
        """Enforce the AW-NNN scoped identifier format."""
        pattern = r"^AW-\d{3}$"
        if not re.match(pattern, str(value)):
            raise ValueError(
                f"weakness_id '{value}' does not match required format 'AW-NNN' "
                "(e.g. 'AW-001')."
            )
        return value

    @field_validator("description", "rag_query_hint", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        """Prevent empty string values for LLM-generated text fields."""
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("Text field must not be empty or whitespace only.")
        return value


class CouplingAnalysis(BaseModel):
    """Coupling assessment produced by the Architecture Agent coupling analyzer."""

    overall_coupling_level: SignalLevel = Field(
        ...,
        description=(
            "Aggregate coupling assessment. HIGH coupling is undesirable. "
            "Derived from high_coupling_file_count and dependency_violation_count."
        ),
    )
    high_coupling_file_count: int = Field(
        ..., ge=0, description="Number of files exceeding either the fan-in or fan-out threshold."
    )
    dependency_violation_count: int = Field(
        ..., ge=0, description="Number of import direction violations detected."
    )
    coupling_narrative: str = Field(
        ...,
        min_length=10,
        description="LLM-generated coupling assessment narrative.",
    )


class ArchitectureSection(BaseModel):
    """Complete output of the Architecture Agent for a single analysis job.

    Produced by the Architecture Agent and consumed by:
    - Recommendation Agent (for synthesis)
    - RAGRetrievalNode (queries built from weaknesses)
    - Report Assembly Service (for the Architecture Assessment section)

    Ownership rules:
    - Architecture Agent creates and fully populates this contract.
    - No downstream component modifies ArchitectureSection fields.
    - Not persisted to Supabase independently; embedded in FinalReport.
    """

    section_id: UUID = Field(..., description="Unique identifier for this section instance.")
    job_id: UUID = Field(..., description="Parent analysis job.")
    detected_pattern: ArchitecturePattern = Field(
        ..., description="Primary architecture pattern classification."
    )
    confidence: Confidence = Field(
        ..., description="Confidence level in the pattern classification."
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Identified positive architectural attributes.",
    )
    weaknesses: list[ArchitectureWeakness] = Field(
        default_factory=list,
        description="Identified architectural problems or structural risks.",
    )
    coupling_analysis: CouplingAnalysis = Field(
        ..., description="Cross-file coupling assessment."
    )
    test_coverage_signal: TestCoverageSignal = Field(
        ..., description="Test file presence signal derived from the PCR QualitySignals."
    )
    narrative: str = Field(
        ...,
        min_length=50,
        description=(
            "LLM-generated narrative explaining the architecture assessment. "
            "Must be at least 50 characters."
        ),
    )
    generated_at: datetime = Field(
        ..., description="UTC timestamp when the Architecture Agent completed generation."
    )
    generation_metadata: GenerationMetadata = Field(
        ..., description="Gemini API call metadata for this generation."
    )

    # --- Optional fields ---

    secondary_pattern_indicators: list[str] | None = Field(
        default=None,
        description=(
            "Other architecture pattern signals present in the codebase but not dominant. "
            "None when no secondary patterns detected."
        ),
    )
    cohesion_narrative: str | None = Field(
        default=None,
        description=(
            "LLM-generated cohesion assessment. Present only when significant "
            "cohesion signals (positive or negative) are detected."
        ),
    )
    layer_boundary_narrative: str | None = Field(
        default=None,
        description=(
            "LLM-generated assessment of layer boundary violations. "
            "Present only when violations are detected."
        ),
    )

    @model_validator(mode="after")
    def validate_at_least_one_finding(self) -> "ArchitectureSection":
        """Enforce that at least strengths or weaknesses is non-empty."""
        if not self.strengths and not self.weaknesses:
            raise ValueError(
                "ArchitectureSection must contain at least one strength or one weakness."
            )
        return self

    @model_validator(mode="after")
    def validate_weakness_ids_unique(self) -> "ArchitectureSection":
        """Enforce uniqueness of weakness_id values within this section."""
        ids = [w.weakness_id for w in self.weaknesses]
        if len(ids) != len(set(ids)):
            duplicates = [wid for wid in ids if ids.count(wid) > 1]
            raise ValueError(
                f"Duplicate weakness_id values detected in ArchitectureSection: {duplicates}"
            )
        return self


# ---------------------------------------------------------------------------
# Security Agent output
# ---------------------------------------------------------------------------


class EvidenceRef(BaseModel):
    """A reference to a structural signal location supporting a security finding.

    Never contains raw source code values. context_description describes
    the signal context without revealing sensitive literal values.
    """

    file_path: str = Field(
        ..., description="Relative file path containing the structural signal."
    )
    signal_type: str = Field(
        ...,
        description=(
            "Signal type identifier from the PCR security signals "
            "(e.g. 'hardcoded_secret_indicator', 'sql_construction_indicator')."
        ),
    )
    context_description: str = Field(
        ...,
        description=(
            "Human-readable context description. Must never include actual "
            "secret values, passwords, tokens, or other sensitive literal content."
        ),
    )


class DependencyRiskSignal(BaseModel):
    """A risk signal derived from a dependency manifest entry."""

    package_name: str = Field(..., description="Name of the dependency package.")
    risk_description: str = Field(
        ..., description="Explanation of why this dependency was flagged."
    )
    manifest_source: str = Field(
        ..., description="Manifest file from which this dependency was read."
    )


class SecurityFinding(BaseModel):
    """A single security risk signal identified by the Security Agent.

    CRITICAL CONTRACT INVARIANTS:
    1. is_confirmed_vulnerability is structurally locked to False via Literal[False].
       The type system prevents any other value from being assigned.
    2. severity is assigned by the Security Agent rule engine.
       The LLM generates description text only; it never assigns severity.
    3. All findings are advisory signals from static analysis, not confirmed vulnerabilities.
       The SecuritySection.disclaimer communicates this to end users.
    """

    finding_id: str = Field(
        ...,
        description=(
            "Scoped unique identifier within the SecuritySection. "
            "Format: 'SF-NNN' where NNN is zero-padded to three digits (e.g. 'SF-001')."
        ),
    )
    title: str = Field(..., description="Short descriptive title for the security finding.")
    severity: Severity = Field(
        ...,
        description=(
            "Severity assigned by the Security Agent rule engine. "
            "Never assigned by LLM output."
        ),
    )
    confidence: Confidence = Field(
        ...,
        description=(
            "Confidence in this finding assigned by the rule engine "
            "based on signal strength."
        ),
    )
    owasp_category: OWASPCategory | None = Field(
        default=None,
        description=(
            "Applicable OWASP Top 10 2021 category. "
            "None when no mapping is applicable."
        ),
    )
    cwe_id: str | None = Field(
        default=None,
        description=(
            "CWE identifier if mappable (e.g. 'CWE-89'). "
            "None when CWE mapping is not applicable."
        ),
    )
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description=(
            "Structural signal locations supporting this finding. "
            "File path references only — never raw code content."
        ),
    )
    description: str = Field(
        ...,
        min_length=20,
        description=(
            "LLM-generated explanation of the finding. Must use qualified language "
            "consistent with the signal-based (non-confirmed) nature of the finding."
        ),
    )
    rag_query_hint: str = Field(
        ...,
        description=(
            "Suggested semantic query for RAG retrieval targeting this finding. "
            "Used by RAGRetrievalNode to find relevant security knowledge base context."
        ),
    )
    is_confirmed_vulnerability: Literal[False] = Field(
        default=False,
        description=(
            "Always False. This field is structurally locked to False via Literal[False]. "
            "All findings are static analysis signals, not confirmed vulnerabilities."
        ),
    )

    @field_validator("finding_id", mode="before")
    @classmethod
    def validate_finding_id_format(cls, value: str) -> str:
        """Enforce the SF-NNN scoped identifier format."""
        pattern = r"^SF-\d{3}$"
        if not re.match(pattern, str(value)):
            raise ValueError(
                f"finding_id '{value}' does not match required format 'SF-NNN' "
                "(e.g. 'SF-001')."
            )
        return value

    @field_validator("rag_query_hint", mode="before")
    @classmethod
    def validate_rag_query_hint_non_empty(cls, value: str) -> str:
        """Prevent empty rag_query_hint."""
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("rag_query_hint must not be empty or whitespace only.")
        return value

    @field_validator("cwe_id", mode="before")
    @classmethod
    def validate_cwe_id_format(cls, value: str | None) -> str | None:
        """Enforce CWE-NNN format when a CWE ID is provided."""
        if value is None:
            return None
        pattern = r"^CWE-\d+$"
        if not re.match(pattern, str(value)):
            raise ValueError(
                f"cwe_id '{value}' does not match required format 'CWE-NNN' "
                "(e.g. 'CWE-89')."
            )
        return value


class SecuritySection(BaseModel):
    """Complete output of the Security Agent for a single analysis job.

    CONTRACT INVARIANTS ENFORCED AT SCHEMA LEVEL:
    1. disclaimer equals the DISCLAIMER_TEXT constant from config/constants.py.
       The model validator rejects any other value.
    2. All findings have is_confirmed_vulnerability = False (Literal[False]).
    3. overall_risk_level equals the highest Severity among findings,
       or Severity.INFO when no findings are present.
    4. finding_counts_by_severity is consistent with the actual findings list.

    Consumed by:
    - Recommendation Agent (for synthesis)
    - RAGRetrievalNode (queries built from findings)
    - Report Assembly Service (for the Security Findings section)
    """

    section_id: UUID = Field(..., description="Unique identifier for this section instance.")
    job_id: UUID = Field(..., description="Parent analysis job.")
    findings: list[SecurityFinding] = Field(
        default_factory=list,
        description=(
            "All detected security risk signals. An empty list is valid when "
            "no signals are detected — this does not imply the codebase is secure."
        ),
    )
    overall_risk_level: Severity = Field(
        ...,
        description=(
            "Aggregate risk classification. Must equal the highest Severity present "
            "in findings. Must be Severity.INFO when findings is empty."
        ),
    )
    finding_counts_by_severity: dict[str, int] = Field(
        ...,
        description=(
            "Count of findings per severity level, keyed by Severity enum name "
            "(e.g. {'CRITICAL': 1, 'HIGH': 2, 'MEDIUM': 0, 'LOW': 3, 'INFO': 0})."
        ),
    )
    narrative: str = Field(
        ...,
        min_length=50,
        description="LLM-generated security assessment narrative.",
    )
    disclaimer: str = Field(
        default=DISCLAIMER_TEXT,
        description=(
            "Fixed advisory disclaimer. Must always equal the DISCLAIMER_TEXT "
            "constant. The model validator enforces this invariant."
        ),
    )
    generated_at: datetime = Field(
        ..., description="UTC timestamp when the Security Agent completed generation."
    )
    generation_metadata: GenerationMetadata = Field(
        ..., description="Gemini API call metadata for this generation."
    )
    dependency_risk_signals: list[DependencyRiskSignal] | None = Field(
        default=None,
        description=(
            "Risk signals derived from dependency manifests. "
            "None when no dependency manifests were present in the repository."
        ),
    )

    # --- Validators ---

    @field_validator("disclaimer", mode="before")
    @classmethod
    def validate_disclaimer_is_fixed_text(cls, value: str) -> str:
        """Reject any disclaimer text that deviates from the approved constant."""
        if str(value) != DISCLAIMER_TEXT:
            raise ValueError(
                "SecuritySection.disclaimer must equal the DISCLAIMER_TEXT constant "
                "from config/constants.py. The disclaimer text is contractually fixed "
                "and must not be modified by any agent or LLM call."
            )
        return value

    @model_validator(mode="after")
    def validate_overall_risk_level_matches_findings(self) -> "SecuritySection":
        """Enforce that overall_risk_level equals the highest finding severity."""
        if self.findings:
            expected = max(f.severity for f in self.findings)
            if self.overall_risk_level != expected:
                raise ValueError(
                    f"overall_risk_level must be {expected.name} (the highest severity "
                    f"among {len(self.findings)} findings), "
                    f"but got {self.overall_risk_level.name}."
                )
        else:
            if self.overall_risk_level != Severity.INFO:
                raise ValueError(
                    f"overall_risk_level must be Severity.INFO when findings is empty, "
                    f"but got {self.overall_risk_level.name}."
                )
        return self

    @model_validator(mode="after")
    def validate_finding_counts_consistent(self) -> "SecuritySection":
        """Enforce that finding_counts_by_severity matches the actual findings list."""
        actual_counts: dict[str, int] = {level.name: 0 for level in Severity}
        for finding in self.findings:
            actual_counts[finding.severity.name] += 1

        for severity_name, expected_count in actual_counts.items():
            declared_count = self.finding_counts_by_severity.get(severity_name, 0)
            if declared_count != expected_count:
                raise ValueError(
                    f"finding_counts_by_severity['{severity_name}'] is {declared_count} "
                    f"but the findings list contains {expected_count} {severity_name} findings."
                )
        return self

    @model_validator(mode="after")
    def validate_finding_ids_unique(self) -> "SecuritySection":
        """Enforce uniqueness of finding_id values within this section."""
        ids = [f.finding_id for f in self.findings]
        if len(ids) != len(set(ids)):
            duplicates = [fid for fid in ids if ids.count(fid) > 1]
            raise ValueError(
                f"Duplicate finding_id values detected in SecuritySection: {duplicates}"
            )
        return self
