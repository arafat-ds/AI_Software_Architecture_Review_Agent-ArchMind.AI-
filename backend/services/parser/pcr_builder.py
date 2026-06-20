"""Assembles a ParsedCodeRepresentation from per-file analyses and signals.

Responsibility: combine FileAnalysis list, cross-file signals, architecture
signals, security signals, quality signals, and parse metadata into one PCR.

This module has no Tree-sitter dependency — it only combines already-computed
data structures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared.exceptions.parse_exceptions import PCRAssemblyError
from shared.types.pcr_types import (
    ArchitectureSignals,
    CrossFileSignals,
    ParseMetadata,
    ParsedCodeRepresentation,
    QualitySignals,
    SecuritySignals,
    FileAnalysis,
)


def build_pcr(
    job_id: UUID,
    source_manifest_id: UUID,
    file_analyses: list[FileAnalysis],
    cross_file_signals: CrossFileSignals,
    architecture_signals: ArchitectureSignals,
    security_signals: SecuritySignals,
    quality_signals: QualitySignals,
    files_attempted: int,
    files_skipped: int,
    parse_duration_ms: int,
) -> ParsedCodeRepresentation:
    """Assemble a ParsedCodeRepresentation from pre-computed components.

    Args:
        job_id: Parent job UUID.
        source_manifest_id: UUID of the RepositoryManifest used as input.
        file_analyses: Per-file structural analyses from file_parser.
        cross_file_signals: Derived from signal_extractor.
        architecture_signals: Derived from signal_extractor.
        security_signals: Derived from signal_extractor.
        quality_signals: Derived from signal_extractor.
        files_attempted: Total files sent for parsing (including failed).
        files_skipped: Files excluded before parsing.
        parse_duration_ms: Wall-clock time for the full parse phase.

    Returns:
        Fully validated ParsedCodeRepresentation.

    Raises:
        PCRAssemblyError: If validation fails (e.g. zero successful parses).
    """
    successful = [f for f in file_analyses if f.parse_succeeded]
    failed = [f for f in file_analyses if not f.parse_succeeded]

    languages_parsed = sorted({f.language for f in successful})
    if not languages_parsed:
        raise PCRAssemblyError(
            reason="Zero files parsed successfully. Cannot assemble PCR."
        )

    metadata = ParseMetadata(
        files_attempted=files_attempted,
        files_parsed_successfully=len(successful),
        files_skipped=files_skipped,
        files_with_parse_errors=len(failed),
        languages_parsed=languages_parsed,
        parse_duration_ms=parse_duration_ms,
    )

    try:
        return ParsedCodeRepresentation(
            pcr_id=uuid4(),
            job_id=job_id,
            source_manifest_id=source_manifest_id,
            file_analyses=file_analyses,
            cross_file_signals=cross_file_signals,
            architecture_signals=architecture_signals,
            security_signals=security_signals,
            quality_signals=quality_signals,
            parse_metadata=metadata,
            produced_at=datetime.now(tz=timezone.utc),
        )
    except Exception as exc:
        raise PCRAssemblyError(reason=str(exc)) from exc
