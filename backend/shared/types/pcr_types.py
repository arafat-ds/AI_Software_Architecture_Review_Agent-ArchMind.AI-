"""Data contracts for the Parsed Code Representation (PCR).

The PCR is the central internal data contract produced by the Code Parser
(Tree-sitter) and consumed by both the Architecture Agent and the Security Agent.
It contains structural signals derived from AST analysis — never raw source code.

All signal detection is performed at file level for MVP. Function-level depth
is a Phase 2 enhancement.

Dependency rule: imports only from shared/types/enums and stdlib/pydantic.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from shared.types.enums import (
    AuthSignalType,
    CouplingType,
    DefinitionKind,
    NamingConsistencySignal,
    PatternStrength,
    SQLSignalType,
    SecretSignalType,
    SignalLevel,
    TestCoverageSignal,
    ValidationGapType,
    ArchitecturePattern,
)


# ---------------------------------------------------------------------------
# File-level analysis types
# ---------------------------------------------------------------------------


class DefinitionSummary(BaseModel):
    """Summary of a single function, class, or method definition in a source file."""

    name: str = Field(..., description="Identifier name as it appears in the source.")
    kind: DefinitionKind = Field(..., description="Whether this is a function, class, or method.")
    line_count: int = Field(..., ge=0, description="Number of lines in the definition body.")
    parameter_count: int = Field(
        ..., ge=0, description="Number of parameters (for functions and methods)."
    )
    has_docstring: bool = Field(
        ..., description="True when a documentation string is present."
    )


class FileAnalysis(BaseModel):
    """Structural analysis of a single source file produced by Tree-sitter parsing."""

    path: str = Field(..., description="Relative file path from the repository root.")
    language: str = Field(..., description="Programming language this file was parsed as.")
    import_list: list[str] = Field(
        default_factory=list,
        description="All import or dependency references (module paths, not resolved).",
    )
    export_list: list[str] = Field(
        default_factory=list,
        description="Exported symbols for module boundary analysis.",
    )
    definition_summaries: list[DefinitionSummary] = Field(
        default_factory=list,
        description="Summaries of all function and class definitions in this file.",
    )
    max_nesting_depth: int = Field(
        ...,
        ge=0,
        description="Maximum statement nesting depth observed in this file.",
    )
    complexity_proxy: int = Field(
        ...,
        ge=0,
        description=(
            "Proxy complexity metric: sum of branch count and loop count. "
            "Not McCabe cyclomatic complexity. Used as a relative signal only."
        ),
    )
    is_test_file: bool = Field(
        ...,
        description="Mirrors the is_test_file value from the corresponding FileEntry.",
    )
    parse_succeeded: bool = Field(
        ...,
        description="True when Tree-sitter parsed this file without structural errors.",
    )
    parse_error_summary: str | None = Field(
        default=None,
        description=(
            "Brief description of any Tree-sitter parse errors. "
            "Must be non-None when parse_succeeded is False."
        ),
    )

    @model_validator(mode="after")
    def validate_parse_error_summary_when_failed(self) -> "FileAnalysis":
        """Enforce that a parse error explanation is always provided on failure."""
        if not self.parse_succeeded and not self.parse_error_summary:
            raise ValueError(
                f"File '{self.path}': parse_error_summary must be provided "
                "when parse_succeeded is False."
            )
        return self


# ---------------------------------------------------------------------------
# Cross-file signal types
# ---------------------------------------------------------------------------


class DirectionViolation(BaseModel):
    """A detected import direction violation between two modules.

    Represents an import that crosses an expected architectural boundary in the
    wrong direction (e.g. a data layer importing from a presentation layer).
    """

    importer_path: str = Field(..., description="Relative path of the file containing the import.")
    imported_path: str = Field(..., description="Relative path of the file being imported.")
    violation_description: str = Field(
        ...,
        description="Human-readable explanation of why this direction is a violation.",
    )


class CouplingSignal(BaseModel):
    """Coupling metrics for a single file that exceeds fan-in or fan-out thresholds."""

    file_path: str = Field(..., description="Relative path of the high-coupling file.")
    fan_in: int = Field(
        ..., ge=0, description="Number of other files that import this file."
    )
    fan_out: int = Field(
        ..., ge=0, description="Number of modules this file imports."
    )
    coupling_type: CouplingType = Field(
        ..., description="Whether the issue is high fan-in, high fan-out, or both."
    )


class CrossFileSignals(BaseModel):
    """Signals derived from relationships between files across the repository."""

    high_coupling_files: list[CouplingSignal] = Field(
        default_factory=list,
        description="Files exceeding fan-in or fan-out coupling thresholds.",
    )
    dependency_direction_violations: list[DirectionViolation] = Field(
        default_factory=list,
        description="Imports that cross architectural boundaries in the wrong direction.",
    )
    import_cycle_indicators: list[str] = Field(
        default_factory=list,
        description="File paths involved in likely circular import patterns.",
    )
    hub_files: list[str] = Field(
        default_factory=list,
        description="Files imported by more than the fan-in threshold (potential god objects).",
    )


# ---------------------------------------------------------------------------
# Architecture signal types
# ---------------------------------------------------------------------------


class PatternIndicator(BaseModel):
    """Evidence supporting a specific architecture pattern classification."""

    pattern: ArchitecturePattern = Field(
        ..., description="Which architecture pattern this indicator supports."
    )
    evidence: list[str] = Field(
        ...,
        min_length=1,
        description="Specific signals that support this pattern classification.",
    )
    strength: PatternStrength = Field(
        ..., description="How strongly the collected evidence supports this pattern."
    )


class ArchitectureSignals(BaseModel):
    """Aggregated architecture indicator signals derived from cross-file analysis."""

    pattern_indicators: dict[str, PatternIndicator] = Field(
        default_factory=dict,
        description=(
            "Pattern evidence keyed by ArchitecturePattern enum value string. "
            "Only patterns with detectable evidence are included."
        ),
    )
    layer_boundary_violations: list[DirectionViolation] = Field(
        default_factory=list,
        description="Import direction violations that cross logical architectural layers.",
    )
    cohesion_assessment: SignalLevel = Field(
        ...,
        description=(
            "Overall cohesion signal. HIGH cohesion is desirable. "
            "Derived from module boundary clarity and coupling density."
        ),
    )
    directory_convention_signals: list[str] = Field(
        default_factory=list,
        description=(
            "Directory names that match known architecture conventions "
            "(e.g. 'controllers', 'models', 'repositories', 'adapters')."
        ),
    )


# ---------------------------------------------------------------------------
# Security signal types
# ---------------------------------------------------------------------------


class SecretSignal(BaseModel):
    """A detected hardcoded secret signal in a source file.

    Records the location and signal type only. Never records the actual
    literal value of the suspected secret.
    """

    file_path: str = Field(..., description="Relative path of the file containing the signal.")
    signal_type: SecretSignalType = Field(
        ..., description="Classification of the detected secret pattern."
    )
    context_description: str = Field(
        ...,
        description=(
            "Human-readable description of the context in which the signal was found. "
            "Must never include the actual secret value."
        ),
    )


class ValidationGapSignal(BaseModel):
    """A detected input or output validation gap at a function entry point."""

    file_path: str = Field(..., description="Relative path of the file containing the gap.")
    function_name: str = Field(..., description="Name of the function where the gap was detected.")
    gap_type: ValidationGapType = Field(..., description="Classification of the validation gap.")


class AuthSignal(BaseModel):
    """A detected authentication-related risk pattern in a source file."""

    file_path: str = Field(..., description="Relative path of the file containing the signal.")
    function_name: str = Field(
        ..., description="Name of the function exhibiting the auth risk pattern."
    )
    signal_type: AuthSignalType = Field(..., description="Classification of the auth signal.")


class SQLSignal(BaseModel):
    """A detected SQL injection risk signal in a source file."""

    file_path: str = Field(..., description="Relative path of the file containing the signal.")
    signal_type: SQLSignalType = Field(..., description="Classification of the SQL risk pattern.")


class SecuritySignals(BaseModel):
    """Aggregated security risk indicator signals derived from file-level analysis."""

    hardcoded_secret_indicators: list[SecretSignal] = Field(
        default_factory=list,
        description="Files containing string literals in security-sensitive naming contexts.",
    )
    missing_input_validation_indicators: list[ValidationGapSignal] = Field(
        default_factory=list,
        description="Entry-point functions without detectable validation patterns.",
    )
    auth_bypass_indicators: list[AuthSignal] = Field(
        default_factory=list,
        description="Auth-related functions exhibiting bypass or missing guard patterns.",
    )
    sql_construction_indicators: list[SQLSignal] = Field(
        default_factory=list,
        description="String construction patterns detected near database call contexts.",
    )
    insecure_default_indicators: list[str] = Field(
        default_factory=list,
        description=(
            "File paths containing debug flags, permissive CORS-like patterns, "
            "or other insecure default configurations."
        ),
    )
    missing_error_handling_indicators: list[str] = Field(
        default_factory=list,
        description="File paths where error handling is absent in security-critical code paths.",
    )


# ---------------------------------------------------------------------------
# Quality signal types
# ---------------------------------------------------------------------------


class QualitySignals(BaseModel):
    """Engineering quality indicator signals derived from file-level structural analysis."""

    test_presence_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Ratio of test files to total files (test_files / total_files). "
            "Range [0.0, 1.0]."
        ),
    )
    test_coverage_signal: TestCoverageSignal = Field(
        ...,
        description=(
            "Derived from test_presence_ratio using thresholds in config/constants.py."
        ),
    )
    naming_consistency_signal: NamingConsistencySignal = Field(
        ...,
        description="Convention consistency signal across file and function names.",
    )
    large_file_indicators: list[str] = Field(
        default_factory=list,
        description="Relative paths of files exceeding the large-file line count threshold.",
    )
    large_function_indicators: list[str] = Field(
        default_factory=list,
        description=(
            "Qualified function names (file_path::function_name) exceeding "
            "the large-function parameter or line count threshold."
        ),
    )
    dead_code_indicators: list[str] = Field(
        default_factory=list,
        description=(
            "Relative paths or qualified names of files/functions with no "
            "detected import or call references."
        ),
    )

    @model_validator(mode="after")
    def validate_test_coverage_signal_consistent_with_ratio(self) -> "QualitySignals":
        """Verify test_coverage_signal is consistent with test_presence_ratio.

        Uses thresholds defined in config/constants.py to validate the signal
        was derived correctly.
        """
        from config.constants import (
            TEST_FILE_PRESENCE_THRESHOLD_PARTIAL,
            TEST_FILE_PRESENCE_THRESHOLD_PRESENT,
        )

        ratio = self.test_presence_ratio
        expected: TestCoverageSignal

        if ratio >= TEST_FILE_PRESENCE_THRESHOLD_PRESENT:
            expected = TestCoverageSignal.PRESENT
        elif ratio >= TEST_FILE_PRESENCE_THRESHOLD_PARTIAL:
            expected = TestCoverageSignal.PARTIAL
        else:
            expected = TestCoverageSignal.ABSENT

        if self.test_coverage_signal != expected:
            raise ValueError(
                f"test_coverage_signal '{self.test_coverage_signal.value}' is inconsistent "
                f"with test_presence_ratio {ratio:.3f}. Expected '{expected.value}'."
            )
        return self


# ---------------------------------------------------------------------------
# Parse process metadata
# ---------------------------------------------------------------------------


class ParseMetadata(BaseModel):
    """Statistics describing the Tree-sitter parsing process for this analysis job."""

    files_attempted: int = Field(
        ..., ge=0, description="Total files for which parsing was attempted."
    )
    files_parsed_successfully: int = Field(
        ..., ge=0, description="Files that Tree-sitter parsed without structural errors."
    )
    files_skipped: int = Field(
        ...,
        ge=0,
        description=(
            "Files excluded before parsing (binary, excluded directories, "
            "unsupported language, exceeds size limit)."
        ),
    )
    files_with_parse_errors: int = Field(
        ..., ge=0, description="Files where Tree-sitter returned parse errors."
    )
    languages_parsed: list[str] = Field(
        ...,
        min_length=1,
        description="Languages for which at least one file was successfully parsed.",
    )
    parse_duration_ms: int = Field(
        ..., ge=0, description="Total wall-clock time for the parsing phase in milliseconds."
    )

    @model_validator(mode="after")
    def validate_counts_consistent(self) -> "ParseMetadata":
        """Verify that parsed + skipped + errors accounts for all attempted files."""
        accounted = (
            self.files_parsed_successfully
            + self.files_skipped
            + self.files_with_parse_errors
        )
        if accounted != self.files_attempted:
            raise ValueError(
                f"File counts inconsistent: files_attempted={self.files_attempted} but "
                f"parsed_successfully({self.files_parsed_successfully}) + "
                f"skipped({self.files_skipped}) + "
                f"parse_errors({self.files_with_parse_errors}) = {accounted}."
            )
        return self


# ---------------------------------------------------------------------------
# Top-level PCR contract
# ---------------------------------------------------------------------------


class ParsedCodeRepresentation(BaseModel):
    """Language-agnostic structural representation of the analysed source code.

    Produced by the Code Parser (Tree-sitter) after processing all eligible
    source files. Contains structural signals only — never raw source code.

    This is the most-imported internal contract in the system. Both the
    Architecture Agent and the Security Agent receive it as their primary input.

    Ownership rules:
    - Created and fully populated by the Code Parser.
    - Immutable after ParseNode writes it to AnalysisState.
    - Architecture Agent reads it. Does not modify it.
    - Security Agent reads it. Does not modify it.
    - Not persisted to Supabase; exists only in AnalysisState.
    """

    pcr_id: UUID = Field(..., description="Unique identifier for this PCR instance.")
    job_id: UUID = Field(..., description="Parent analysis job.")
    source_manifest_id: UUID = Field(
        ...,
        description="UUID of the RepositoryManifest from which this PCR was produced.",
    )
    file_analyses: list[FileAnalysis] = Field(
        ...,
        min_length=1,
        description=(
            "Per-file structural summaries. At least one file must have been "
            "successfully parsed; zero analyses is a fatal parse failure."
        ),
    )
    cross_file_signals: CrossFileSignals = Field(
        ..., description="Signals derived from import relationships between files."
    )
    architecture_signals: ArchitectureSignals = Field(
        ..., description="Aggregated architecture pattern indicator signals."
    )
    security_signals: SecuritySignals = Field(
        ..., description="Aggregated security risk indicator signals."
    )
    quality_signals: QualitySignals = Field(
        ..., description="Engineering quality indicator signals."
    )
    parse_metadata: ParseMetadata = Field(
        ..., description="Statistics about the parsing process."
    )
    produced_at: datetime = Field(
        ..., description="UTC timestamp when PCR generation was completed."
    )

    @model_validator(mode="after")
    def validate_at_least_one_successful_parse(self) -> "ParsedCodeRepresentation":
        """Enforce that at least one file was successfully parsed."""
        successful = [f for f in self.file_analyses if f.parse_succeeded]
        if not successful:
            raise ValueError(
                "ParsedCodeRepresentation requires at least one successfully parsed file. "
                "Zero successful parses is a fatal error condition."
            )
        return self
