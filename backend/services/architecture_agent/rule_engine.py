"""Architecture Agent deterministic rule engine.

All classification, severity assignment, and structural measurement logic
lives here. Nothing in this module calls the Gemini API or any external service.

Outputs are intermediate dataclasses (WeaknessSpec, CouplingSpec,
ArchitectureRuleOutput) that the service layer uses to:
  1. Build the LLM prompt
  2. Assemble the final ArchitectureSection after LLM enrichment
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    PatternStrength,
    Severity,
    SignalLevel,
    TestCoverageSignal,
)
from shared.types.pcr_types import (
    ArchitectureSignals,
    CrossFileSignals,
    DirectionViolation,
    ParsedCodeRepresentation,
    PatternIndicator,
    QualitySignals,
)


# ---------------------------------------------------------------------------
# Intermediate data contracts (internal to the architecture agent)
# ---------------------------------------------------------------------------


@dataclass
class WeaknessSpec:
    """A weakness identified by the rule engine before LLM enrichment.

    description and rag_query_hint are empty strings here — filled in by
    the service after the LLM call.
    """

    weakness_id: str
    title: str
    severity: Severity
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class CouplingSpec:
    """Coupling metrics computed deterministically from cross-file signals."""

    overall_coupling_level: SignalLevel
    high_coupling_file_count: int
    dependency_violation_count: int


@dataclass
class ArchitectureRuleOutput:
    """Complete output of the architecture rule engine for one analysis job."""

    detected_pattern: ArchitecturePattern
    confidence: Confidence
    weakness_specs: list[WeaknessSpec]
    coupling_spec: CouplingSpec
    test_coverage_signal: TestCoverageSignal
    cohesion_level: SignalLevel
    secondary_pattern_keys: list[str]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_architecture_rules(pcr: ParsedCodeRepresentation) -> ArchitectureRuleOutput:
    """Run all deterministic architecture rules against a ParsedCodeRepresentation.

    Args:
        pcr: Fully populated PCR from ParseNode.

    Returns:
        ArchitectureRuleOutput containing all deterministic analysis results.
        Passed to the prompt builder and used for final ArchitectureSection assembly.
    """
    arch = pcr.architecture_signals
    cross = pcr.cross_file_signals
    quality = pcr.quality_signals

    detected_pattern, confidence, secondary_keys = _classify_pattern(arch.pattern_indicators)
    weakness_specs = _generate_weaknesses(cross, arch.layer_boundary_violations, arch.cohesion_assessment)
    coupling_spec = _compute_coupling_spec(cross)

    return ArchitectureRuleOutput(
        detected_pattern=detected_pattern,
        confidence=confidence,
        weakness_specs=weakness_specs,
        coupling_spec=coupling_spec,
        test_coverage_signal=quality.test_coverage_signal,
        cohesion_level=arch.cohesion_assessment,
        secondary_pattern_keys=secondary_keys,
    )


# ---------------------------------------------------------------------------
# Pattern classification
# ---------------------------------------------------------------------------


def _classify_pattern(
    pattern_indicators: dict[str, PatternIndicator],
) -> tuple[ArchitecturePattern, Confidence, list[str]]:
    """Classify the dominant architecture pattern from PCR pattern indicators.

    Returns:
        (detected_pattern, confidence, secondary_pattern_keys)
        secondary_pattern_keys: all non-dominant pattern keys with any evidence
    """
    if not pattern_indicators:
        return ArchitecturePattern.UNKNOWN, Confidence.LOW, []

    strong = {k: v for k, v in pattern_indicators.items() if v.strength == PatternStrength.STRONG}
    moderate = {k: v for k, v in pattern_indicators.items() if v.strength == PatternStrength.MODERATE}
    weak = {k: v for k, v in pattern_indicators.items() if v.strength == PatternStrength.WEAK}

    winner_key: str | None = None
    confidence: Confidence

    if len(strong) == 1:
        winner_key = next(iter(strong))
        confidence = Confidence.HIGH if not moderate else Confidence.MEDIUM
    elif len(strong) > 1:
        winner_key = max(strong, key=lambda k: len(strong[k].evidence))
        confidence = Confidence.MEDIUM
    elif moderate:
        winner_key = max(moderate, key=lambda k: len(moderate[k].evidence))
        confidence = Confidence.MEDIUM
    elif weak:
        winner_key = max(weak, key=lambda k: len(weak[k].evidence))
        confidence = Confidence.LOW
    else:
        return ArchitecturePattern.UNKNOWN, Confidence.LOW, []

    try:
        detected_pattern = ArchitecturePattern(winner_key)
    except ValueError:
        detected_pattern = ArchitecturePattern.UNKNOWN
        confidence = Confidence.LOW

    secondary_keys = [k for k in pattern_indicators if k != winner_key]

    return detected_pattern, confidence, secondary_keys


# ---------------------------------------------------------------------------
# Weakness generation
# ---------------------------------------------------------------------------


def _generate_weaknesses(
    cross: CrossFileSignals,
    layer_boundary_violations: list[DirectionViolation],
    cohesion_assessment: SignalLevel,
) -> list[WeaknessSpec]:
    """Generate WeaknessSpec entries from structural signal data.

    Severity is always assigned here. LLM fills in description and rag_query_hint later.
    Evidence refs are capped at 5 items per weakness to keep prompts manageable.
    """
    weaknesses: list[WeaknessSpec] = []
    counter = 1

    def _next_id() -> str:
        nonlocal counter
        wid = f"AW-{counter:03d}"
        counter += 1
        return wid

    # Circular imports → HIGH (cycles break dependency management)
    if cross.import_cycle_indicators:
        weaknesses.append(WeaknessSpec(
            weakness_id=_next_id(),
            title="Circular Import Dependencies",
            severity=Severity.HIGH,
            evidence_refs=list(cross.import_cycle_indicators[:5]),
        ))

    # High-coupling files → MEDIUM
    if cross.high_coupling_files:
        evidence = [s.file_path for s in cross.high_coupling_files[:5]]
        weaknesses.append(WeaknessSpec(
            weakness_id=_next_id(),
            title="High Module Coupling",
            severity=Severity.MEDIUM,
            evidence_refs=evidence,
        ))

    # Dependency direction violations (cross-file) → MEDIUM
    if cross.dependency_direction_violations:
        evidence = [v.importer_path for v in cross.dependency_direction_violations[:5]]
        weaknesses.append(WeaknessSpec(
            weakness_id=_next_id(),
            title="Dependency Direction Violation",
            severity=Severity.MEDIUM,
            evidence_refs=evidence,
        ))

    # Layer boundary violations (from architecture signals) → MEDIUM
    if layer_boundary_violations:
        evidence = [v.importer_path for v in layer_boundary_violations[:5]]
        weaknesses.append(WeaknessSpec(
            weakness_id=_next_id(),
            title="Architectural Layer Boundary Breach",
            severity=Severity.MEDIUM,
            evidence_refs=evidence,
        ))

    # Low cohesion → LOW
    if cohesion_assessment == SignalLevel.LOW:
        weaknesses.append(WeaknessSpec(
            weakness_id=_next_id(),
            title="Low Module Cohesion",
            severity=Severity.LOW,
            evidence_refs=[],
        ))

    return weaknesses


# ---------------------------------------------------------------------------
# Coupling level computation
# ---------------------------------------------------------------------------


def _compute_coupling_spec(cross: CrossFileSignals) -> CouplingSpec:
    """Derive CouplingSpec from cross-file signal counts."""
    coupling_count = len(cross.high_coupling_files)
    violation_count = len(cross.dependency_direction_violations)

    if coupling_count > 5 or violation_count > 3:
        level = SignalLevel.HIGH
    elif coupling_count >= 2 or violation_count >= 1:
        level = SignalLevel.MEDIUM
    else:
        level = SignalLevel.LOW

    return CouplingSpec(
        overall_coupling_level=level,
        high_coupling_file_count=coupling_count,
        dependency_violation_count=violation_count,
    )
