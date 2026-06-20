"""Shared type definitions package.

All internal data contracts for ArchMind AI are defined in sub-modules and
re-exported from this package for convenient import. Prefer explicit sub-module
imports in production code for clarity; use this package-level import in tests.

Dependency rule: shared/types imports only from config/ and stdlib/pydantic.
"""

from shared.types.analysis_types import (
    ArchitectureSection,
    ArchitectureWeakness,
    CouplingAnalysis,
    DependencyRiskSignal,
    EvidenceRef,
    GenerationMetadata,
    SecurityFinding,
    SecuritySection,
)
from shared.types.enums import (
    ArchitecturePattern,
    AuthSignalType,
    Confidence,
    CouplingType,
    DefinitionKind,
    EffortEstimate,
    JobStatus,
    ManifestType,
    NamingConsistencySignal,
    NodeExecutionStatus,
    OWASPCategory,
    PatternStrength,
    Priority,
    RAGDomain,
    RecommendationCategory,
    SQLSignalType,
    SectionKey,
    SecretSignalType,
    Severity,
    SignalLevel,
    TestCoverageSignal,
    ValidationGapType,
    WorkflowStatus,
)
from shared.types.job_types import JobRecord, NodeExecution, WorkflowError
from shared.types.manifest_types import (
    DependencyEntry,
    DependencyManifest,
    DirectoryEntry,
    FileEntry,
    LanguageStats,
    RepositoryManifest,
)
from shared.types.pcr_types import (
    ArchitectureSignals,
    AuthSignal,
    CrossFileSignals,
    CouplingSignal,
    DefinitionSummary,
    DirectionViolation,
    FileAnalysis,
    ParseMetadata,
    ParsedCodeRepresentation,
    PatternIndicator,
    QualitySignals,
    SQLSignal,
    SecretSignal,
    SecuritySignals,
    ValidationGapSignal,
)
from shared.types.rag_types import RAGChunk, RAGContext, RAGQuery
from shared.types.report_types import (
    FinalReport,
    Recommendation,
    RecommendationSection,
    ReportMetadata,
    ReportSection,
)

__all__ = [
    # Enums
    "ArchitecturePattern",
    "AuthSignalType",
    "Confidence",
    "CouplingType",
    "DefinitionKind",
    "EffortEstimate",
    "JobStatus",
    "ManifestType",
    "NamingConsistencySignal",
    "NodeExecutionStatus",
    "OWASPCategory",
    "PatternStrength",
    "Priority",
    "RAGDomain",
    "RecommendationCategory",
    "SQLSignalType",
    "SectionKey",
    "SecretSignalType",
    "Severity",
    "SignalLevel",
    "TestCoverageSignal",
    "ValidationGapType",
    "WorkflowStatus",
    # Manifest types
    "DependencyEntry",
    "DependencyManifest",
    "DirectoryEntry",
    "FileEntry",
    "LanguageStats",
    "RepositoryManifest",
    # PCR types
    "ArchitectureSignals",
    "AuthSignal",
    "CrossFileSignals",
    "CouplingSignal",
    "DefinitionSummary",
    "DirectionViolation",
    "FileAnalysis",
    "ParseMetadata",
    "ParsedCodeRepresentation",
    "PatternIndicator",
    "QualitySignals",
    "SQLSignal",
    "SecretSignal",
    "SecuritySignals",
    "ValidationGapSignal",
    # Analysis section types
    "ArchitectureSection",
    "ArchitectureWeakness",
    "CouplingAnalysis",
    "DependencyRiskSignal",
    "EvidenceRef",
    "GenerationMetadata",
    "SecurityFinding",
    "SecuritySection",
    # RAG types
    "RAGChunk",
    "RAGContext",
    "RAGQuery",
    # Report types
    "FinalReport",
    "Recommendation",
    "RecommendationSection",
    "ReportMetadata",
    "ReportSection",
    # Job types
    "JobRecord",
    "NodeExecution",
    "WorkflowError",
]
