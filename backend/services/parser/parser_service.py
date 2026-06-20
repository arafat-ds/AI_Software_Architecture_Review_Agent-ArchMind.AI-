"""Orchestrates Tree-sitter parsing and PCR assembly for a full repository.

Responsibility: iterate over analyzable files from a RepositoryManifest,
call file_parser for each, collect source text for security signal extraction,
then delegate to the signal modules and pcr_builder to produce a PCR.

ParseNode calls parser_service.run(manifest) and receives a ParsedCodeRepresentation.
"""

from __future__ import annotations

import time
from pathlib import Path

from shared.exceptions.parse_exceptions import ZeroParseableFilesError
from shared.logging.logger import get_logger
from shared.types.manifest_types import RepositoryManifest
from shared.types.pcr_types import FileAnalysis, ParsedCodeRepresentation
from services.parser.file_parser import parse_file_bytes
from services.parser.pcr_builder import build_pcr
from services.parser.architecture_signals import extract_architecture_signals
from services.parser.coupling_signals import extract_cross_file_signals
from services.parser.quality_signals import extract_quality_signals
from services.parser.security_signals import extract_security_signals

logger = get_logger(__name__)


class ParserService:
    """Parses all analyzable files in a repository manifest and returns a PCR.

    Stateless — safe to instantiate once and reuse.
    """

    def run(self, manifest: RepositoryManifest) -> ParsedCodeRepresentation:
        """Parse the repository described by manifest and return a PCR.

        Args:
            manifest: Fully populated RepositoryManifest from IngestionService.

        Returns:
            ParsedCodeRepresentation ready to be written to AnalysisState.

        Raises:
            ZeroParseableFilesError: All parseable files failed to parse.
            PCRAssemblyError: PCR validation failed during assembly.
        """
        clone_path = manifest.temp_clone_path
        analyzable = [f for f in manifest.file_list if not f.is_skipped]
        skipped_count = sum(1 for f in manifest.file_list if f.is_skipped)

        logger.info("Starting parse phase", extra={
            "job_id": str(manifest.job_id),
            "analyzable_files": len(analyzable),
            "skipped_files": skipped_count,
        })

        start_ms = int(time.monotonic() * 1000)
        file_analyses: list[FileAnalysis] = []
        source_map: dict[str, str] = {}

        for entry in analyzable:
            abs_path = (
                Path(clone_path) / entry.path
                if clone_path
                else Path(entry.path)
            )
            source_bytes = _read_file_bytes(abs_path)
            analysis = parse_file_bytes(
                path=entry.path,
                language=entry.language,
                is_test_file=entry.is_test_file,
                source=source_bytes,
            )
            file_analyses.append(analysis)
            if source_bytes:
                source_map[entry.path] = source_bytes.decode("utf-8", errors="replace")

        elapsed_ms = int(time.monotonic() * 1000) - start_ms

        successful_count = sum(1 for fa in file_analyses if fa.parse_succeeded)
        if successful_count == 0:
            raise ZeroParseableFilesError(
                files_attempted=len(analyzable),
                files_skipped=skipped_count,
            )

        logger.info("Parse phase complete", extra={
            "job_id": str(manifest.job_id),
            "parsed_ok": successful_count,
            "parse_errors": len(file_analyses) - successful_count,
            "elapsed_ms": elapsed_ms,
        })

        cross_file = extract_cross_file_signals(file_analyses)
        arch_signals = extract_architecture_signals(file_analyses, cross_file)
        security_signals = extract_security_signals(file_analyses, source_map)
        quality_signals = extract_quality_signals(file_analyses)

        return build_pcr(
            job_id=manifest.job_id,
            source_manifest_id=manifest.manifest_id,
            file_analyses=file_analyses,
            cross_file_signals=cross_file,
            architecture_signals=arch_signals,
            security_signals=security_signals,
            quality_signals=quality_signals,
            files_attempted=len(analyzable),
            files_skipped=skipped_count,
            parse_duration_ms=elapsed_ms,
        )


def _read_file_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""
