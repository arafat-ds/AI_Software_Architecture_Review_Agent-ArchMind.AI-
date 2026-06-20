"""Engineering quality signal extraction.

Derives QualitySignals from structural file analysis: test presence ratio,
naming consistency, large file/function indicators, and dead code indicators.
"""

from __future__ import annotations

from pathlib import Path

from config.constants import (
    TEST_FILE_PRESENCE_THRESHOLD_PARTIAL,
    TEST_FILE_PRESENCE_THRESHOLD_PRESENT,
)
from shared.types.enums import NamingConsistencySignal, TestCoverageSignal
from shared.types.pcr_types import FileAnalysis, QualitySignals

_LARGE_FILE_LINE_THRESHOLD: int = 300
_LARGE_FUNCTION_LINE_THRESHOLD: int = 60
_LARGE_FUNCTION_PARAM_THRESHOLD: int = 8


def extract_quality_signals(file_analyses: list[FileAnalysis]) -> QualitySignals:
    """Derive engineering quality signals from structural file analysis."""
    total = len(file_analyses)
    if total == 0:
        ratio = 0.0
    else:
        test_count = sum(1 for f in file_analyses if f.is_test_file)
        ratio = test_count / total

    if ratio >= TEST_FILE_PRESENCE_THRESHOLD_PRESENT:
        coverage_signal = TestCoverageSignal.PRESENT
    elif ratio >= TEST_FILE_PRESENCE_THRESHOLD_PARTIAL:
        coverage_signal = TestCoverageSignal.PARTIAL
    else:
        coverage_signal = TestCoverageSignal.ABSENT

    large_files = [
        fa.path for fa in file_analyses
        if _estimate_line_count(fa) > _LARGE_FILE_LINE_THRESHOLD
    ]

    large_functions = []
    for fa in file_analyses:
        for defn in fa.definition_summaries:
            if (defn.line_count > _LARGE_FUNCTION_LINE_THRESHOLD
                    or defn.parameter_count > _LARGE_FUNCTION_PARAM_THRESHOLD):
                large_functions.append(f"{fa.path}::{defn.name}")

    naming_signal = _assess_naming_consistency(file_analyses)
    dead_code = _detect_dead_code_indicators(file_analyses)

    return QualitySignals(
        test_presence_ratio=ratio,
        test_coverage_signal=coverage_signal,
        naming_consistency_signal=naming_signal,
        large_file_indicators=large_files,
        large_function_indicators=large_functions,
        dead_code_indicators=dead_code,
    )


def _estimate_line_count(fa: FileAnalysis) -> int:
    if fa.definition_summaries:
        return sum(d.line_count for d in fa.definition_summaries)
    return 0


def _assess_naming_consistency(file_analyses: list[FileAnalysis]) -> NamingConsistencySignal:
    snake_count = 0
    camel_count = 0
    for fa in file_analyses:
        name = Path(fa.path).stem
        if "_" in name:
            snake_count += 1
        elif any(c.isupper() for c in name[1:]):
            camel_count += 1

    total = snake_count + camel_count
    if total == 0:
        return NamingConsistencySignal.CONSISTENT
    dominant = max(snake_count, camel_count)
    ratio = dominant / total
    if ratio >= 0.85:
        return NamingConsistencySignal.CONSISTENT
    if ratio >= 0.60:
        return NamingConsistencySignal.MIXED
    return NamingConsistencySignal.INCONSISTENT


def _detect_dead_code_indicators(file_analyses: list[FileAnalysis]) -> list[str]:
    all_imports: set[str] = set()
    for fa in file_analyses:
        all_imports.update(fa.import_list)

    dead: list[str] = []
    for fa in file_analyses:
        if fa.is_test_file:
            continue
        if not any(fa.path in imp or Path(fa.path).stem in imp for imp in all_imports):
            if fa.export_list:
                dead.append(fa.path)
    return dead
