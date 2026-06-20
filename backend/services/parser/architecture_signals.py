"""Architecture pattern signal extraction.

Derives ArchitectureSignals from file structure, directory conventions,
import topology, and cross-file coupling data.
"""

from __future__ import annotations

from pathlib import Path

from shared.types.enums import ArchitecturePattern, PatternStrength, SignalLevel
from shared.types.pcr_types import (
    ArchitectureSignals,
    CrossFileSignals,
    FileAnalysis,
    PatternIndicator,
)

_ARCH_DIRECTORY_CONVENTIONS: frozenset[str] = frozenset({
    "controllers", "models", "repositories", "adapters", "services",
    "handlers", "middleware", "routers", "views", "templates",
    "domain", "infrastructure", "application", "presentation",
    "usecases", "entities", "interfaces", "gateways",
})


def extract_architecture_signals(
    file_analyses: list[FileAnalysis],
    cross_file: CrossFileSignals,
) -> ArchitectureSignals:
    """Derive architecture pattern indicators from file structure and imports."""
    all_paths = [fa.path for fa in file_analyses]
    dir_conventions = _detect_directory_conventions(all_paths)
    pattern_indicators = _classify_patterns(all_paths, dir_conventions, cross_file)
    cohesion = _assess_cohesion(cross_file, file_analyses)

    return ArchitectureSignals(
        pattern_indicators=pattern_indicators,
        layer_boundary_violations=cross_file.dependency_direction_violations,
        cohesion_assessment=cohesion,
        directory_convention_signals=sorted(dir_conventions),
    )


def _detect_directory_conventions(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    for path in paths:
        for part in Path(path).parts:
            if part.lower() in _ARCH_DIRECTORY_CONVENTIONS:
                seen.add(part.lower())
    return sorted(seen)


def _classify_patterns(
    paths: list[str],
    dir_conventions: list[str],
    cross_file: CrossFileSignals,
) -> dict[str, PatternIndicator]:
    indicators: dict[str, PatternIndicator] = {}
    conventions_set = set(dir_conventions)

    layered_evidence: list[str] = []
    if "controllers" in conventions_set or "views" in conventions_set:
        layered_evidence.append("Directory 'controllers' or 'views' found")
    if "models" in conventions_set:
        layered_evidence.append("Directory 'models' found")
    if "repositories" in conventions_set:
        layered_evidence.append("Directory 'repositories' found")
    if layered_evidence:
        strength = PatternStrength.STRONG if len(layered_evidence) >= 2 else PatternStrength.WEAK
        indicators[ArchitecturePattern.LAYERED.value] = PatternIndicator(
            pattern=ArchitecturePattern.LAYERED,
            evidence=layered_evidence,
            strength=strength,
        )

    domain_evidence: list[str] = []
    for part in ["domain", "entities", "usecases", "interfaces"]:
        if part in conventions_set:
            domain_evidence.append(f"Directory '{part}' found")
    if domain_evidence:
        strength = PatternStrength.STRONG if len(domain_evidence) >= 3 else PatternStrength.MODERATE
        indicators[ArchitecturePattern.DOMAIN_DRIVEN.value] = PatternIndicator(
            pattern=ArchitecturePattern.DOMAIN_DRIVEN,
            evidence=domain_evidence,
            strength=strength,
        )

    service_count = sum(1 for p in paths if "service" in p.lower())
    if service_count >= 3:
        indicators[ArchitecturePattern.SERVICE_ORIENTED.value] = PatternIndicator(
            pattern=ArchitecturePattern.SERVICE_ORIENTED,
            evidence=[f"{service_count} service-prefixed modules detected"],
            strength=PatternStrength.WEAK,
        )

    return indicators


def _assess_cohesion(
    cross_file: CrossFileSignals,
    file_analyses: list[FileAnalysis],
) -> SignalLevel:
    high_coupling_count = len(cross_file.high_coupling_files)
    cycle_count = len(cross_file.import_cycle_indicators)
    violation_count = len(cross_file.dependency_direction_violations)
    total_files = max(len(file_analyses), 1)

    penalty = (high_coupling_count + cycle_count * 2 + violation_count) / total_files
    if penalty < 0.05:
        return SignalLevel.HIGH
    if penalty < 0.20:
        return SignalLevel.MEDIUM
    return SignalLevel.LOW
