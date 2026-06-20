"""Unit tests for the Architecture Agent deterministic rule engine.

All tests are pure: no Gemini calls, no settings, no .env required.
Tests verify that classification, severity assignment, and structural
measurement produce correct deterministic outputs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.architecture_agent.rule_engine import (
    ArchitectureRuleOutput,
    WeaknessSpec,
    _classify_pattern,
    _compute_coupling_spec,
    _generate_weaknesses,
    run_architecture_rules,
)
from shared.types.enums import (
    ArchitecturePattern,
    Confidence,
    NamingConsistencySignal,
    PatternStrength,
    Severity,
    SignalLevel,
    TestCoverageSignal,
)
from shared.types.pcr_types import (
    ArchitectureSignals,
    CouplingSignal,
    CouplingType,
    CrossFileSignals,
    DirectionViolation,
    FileAnalysis,
    ParseMetadata,
    ParsedCodeRepresentation,
    PatternIndicator,
    QualitySignals,
    SecuritySignals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pattern_indicator(
    pattern: ArchitecturePattern,
    strength: PatternStrength,
    evidence: list[str] | None = None,
) -> PatternIndicator:
    return PatternIndicator(
        pattern=pattern,
        evidence=evidence or ["evidence_item"],
        strength=strength,
    )


def _make_coupling_signal(path: str = "src/hub.py") -> CouplingSignal:
    return CouplingSignal(
        file_path=path,
        fan_in=12,
        fan_out=5,
        coupling_type=CouplingType.HIGH_FAN_IN,
    )


def _make_direction_violation(importer: str = "ui/view.py", imported: str = "db/model.py") -> DirectionViolation:
    return DirectionViolation(
        importer_path=importer,
        imported_path=imported,
        violation_description="UI layer imports from DB layer directly",
    )


def _make_minimal_pcr(
    architecture_signals: ArchitectureSignals | None = None,
    cross_file_signals: CrossFileSignals | None = None,
    quality_signals: QualitySignals | None = None,
) -> ParsedCodeRepresentation:
    file_analysis = FileAnalysis(
        path="main.py",
        language="Python",
        max_nesting_depth=2,
        complexity_proxy=3,
        is_test_file=False,
        parse_succeeded=True,
    )
    return ParsedCodeRepresentation(
        pcr_id=uuid4(),
        job_id=uuid4(),
        source_manifest_id=uuid4(),
        file_analyses=[file_analysis],
        cross_file_signals=cross_file_signals or CrossFileSignals(),
        architecture_signals=architecture_signals or ArchitectureSignals(
            cohesion_assessment=SignalLevel.MEDIUM
        ),
        security_signals=SecuritySignals(),
        quality_signals=quality_signals or QualitySignals(
            test_presence_ratio=0.0,
            test_coverage_signal=TestCoverageSignal.ABSENT,
            naming_consistency_signal=NamingConsistencySignal.CONSISTENT,
        ),
        parse_metadata=ParseMetadata(
            files_attempted=1,
            files_parsed_successfully=1,
            files_skipped=0,
            files_with_parse_errors=0,
            languages_parsed=["Python"],
            parse_duration_ms=50,
        ),
        produced_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# _classify_pattern tests
# ---------------------------------------------------------------------------


def test_classify_pattern_single_strong_indicator():
    """Single STRONG indicator → that pattern, HIGH confidence."""
    indicators = {
        "LAYERED": _make_pattern_indicator(
            ArchitecturePattern.LAYERED, PatternStrength.STRONG
        )
    }
    pattern, confidence, secondary = _classify_pattern(indicators)
    assert pattern == ArchitecturePattern.LAYERED
    assert confidence == Confidence.HIGH
    assert secondary == []


def test_classify_pattern_strong_with_competing_moderate():
    """STRONG + MODERATE indicators → STRONG pattern wins, MEDIUM confidence."""
    indicators = {
        "LAYERED": _make_pattern_indicator(
            ArchitecturePattern.LAYERED, PatternStrength.STRONG
        ),
        "MVC": _make_pattern_indicator(
            ArchitecturePattern.MVC, PatternStrength.MODERATE
        ),
    }
    pattern, confidence, secondary = _classify_pattern(indicators)
    assert pattern == ArchitecturePattern.LAYERED
    assert confidence == Confidence.MEDIUM
    assert "MVC" in secondary


def test_classify_pattern_multiple_strong_picks_most_evidence():
    """Multiple STRONG indicators → most evidence wins, MEDIUM confidence."""
    indicators = {
        "LAYERED": _make_pattern_indicator(
            ArchitecturePattern.LAYERED, PatternStrength.STRONG, evidence=["a", "b", "c"]
        ),
        "MVC": _make_pattern_indicator(
            ArchitecturePattern.MVC, PatternStrength.STRONG, evidence=["x"]
        ),
    }
    pattern, confidence, _ = _classify_pattern(indicators)
    assert pattern == ArchitecturePattern.LAYERED
    assert confidence == Confidence.MEDIUM


def test_classify_pattern_moderate_only():
    """Only MODERATE indicators → best evidence wins, MEDIUM confidence."""
    indicators = {
        "SERVICE_BASED": _make_pattern_indicator(
            ArchitecturePattern.SERVICE_BASED,
            PatternStrength.MODERATE,
            evidence=["svc/", "api/"],
        )
    }
    pattern, confidence, _ = _classify_pattern(indicators)
    assert pattern == ArchitecturePattern.SERVICE_BASED
    assert confidence == Confidence.MEDIUM


def test_classify_pattern_weak_only():
    """Only WEAK indicators → best evidence wins, LOW confidence."""
    indicators = {
        "MVC": _make_pattern_indicator(
            ArchitecturePattern.MVC, PatternStrength.WEAK
        )
    }
    pattern, confidence, _ = _classify_pattern(indicators)
    assert pattern == ArchitecturePattern.MVC
    assert confidence == Confidence.LOW


def test_classify_pattern_empty_indicators():
    """No indicators → UNKNOWN pattern, LOW confidence."""
    pattern, confidence, secondary = _classify_pattern({})
    assert pattern == ArchitecturePattern.UNKNOWN
    assert confidence == Confidence.LOW
    assert secondary == []


def test_classify_pattern_secondary_keys_exclude_winner():
    """secondary_pattern_keys must not contain the winning pattern key."""
    indicators = {
        "LAYERED": _make_pattern_indicator(
            ArchitecturePattern.LAYERED, PatternStrength.STRONG
        ),
        "MVC": _make_pattern_indicator(
            ArchitecturePattern.MVC, PatternStrength.WEAK
        ),
    }
    _, _, secondary = _classify_pattern(indicators)
    assert "LAYERED" not in secondary
    assert "MVC" in secondary


# ---------------------------------------------------------------------------
# _generate_weaknesses tests
# ---------------------------------------------------------------------------


def test_generate_weaknesses_cycle_indicators_produces_high_severity():
    """Circular imports must generate a HIGH severity weakness."""
    cross = CrossFileSignals(import_cycle_indicators=["module_a.py", "module_b.py"])
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.MEDIUM)

    cycle_weaknesses = [w for w in weaknesses if "Circular" in w.title]
    assert len(cycle_weaknesses) == 1
    assert cycle_weaknesses[0].severity == Severity.HIGH
    assert cycle_weaknesses[0].weakness_id == "AW-001"


def test_generate_weaknesses_high_coupling_produces_medium_severity():
    """High-coupling files must generate a MEDIUM severity weakness."""
    cross = CrossFileSignals(high_coupling_files=[_make_coupling_signal()])
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.MEDIUM)

    coupling_weaknesses = [w for w in weaknesses if "Coupling" in w.title]
    assert len(coupling_weaknesses) == 1
    assert coupling_weaknesses[0].severity == Severity.MEDIUM


def test_generate_weaknesses_direction_violations_produce_medium_severity():
    """Dependency direction violations must generate a MEDIUM severity weakness."""
    cross = CrossFileSignals(
        dependency_direction_violations=[_make_direction_violation()]
    )
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.MEDIUM)

    dir_weaknesses = [w for w in weaknesses if "Direction" in w.title]
    assert len(dir_weaknesses) == 1
    assert dir_weaknesses[0].severity == Severity.MEDIUM


def test_generate_weaknesses_low_cohesion_produces_low_severity():
    """Low cohesion must generate a LOW severity weakness."""
    cross = CrossFileSignals()
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.LOW)

    cohesion_weaknesses = [w for w in weaknesses if "Cohesion" in w.title]
    assert len(cohesion_weaknesses) == 1
    assert cohesion_weaknesses[0].severity == Severity.LOW


def test_generate_weaknesses_no_signals_returns_empty():
    """No signals must produce no weaknesses."""
    cross = CrossFileSignals()
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.MEDIUM)
    assert weaknesses == []


def test_generate_weaknesses_ids_are_sequential():
    """Weakness IDs must be assigned sequentially from AW-001."""
    cross = CrossFileSignals(
        import_cycle_indicators=["a.py"],
        high_coupling_files=[_make_coupling_signal()],
        dependency_direction_violations=[_make_direction_violation()],
    )
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.LOW)
    ids = [w.weakness_id for w in weaknesses]
    assert ids == [f"AW-{i:03d}" for i in range(1, len(ids) + 1)]


def test_generate_weaknesses_evidence_refs_capped_at_five():
    """Evidence refs per weakness must be capped at 5 items."""
    paths = [f"file_{i}.py" for i in range(10)]
    cross = CrossFileSignals(import_cycle_indicators=paths)
    weaknesses = _generate_weaknesses(cross, [], SignalLevel.MEDIUM)
    assert len(weaknesses[0].evidence_refs) <= 5


# ---------------------------------------------------------------------------
# _compute_coupling_spec tests
# ---------------------------------------------------------------------------


def test_coupling_level_high_when_more_than_five_files():
    """More than 5 high-coupling files → HIGH coupling level."""
    cross = CrossFileSignals(
        high_coupling_files=[_make_coupling_signal(f"f{i}.py") for i in range(6)]
    )
    spec = _compute_coupling_spec(cross)
    assert spec.overall_coupling_level == SignalLevel.HIGH
    assert spec.high_coupling_file_count == 6


def test_coupling_level_high_when_more_than_three_violations():
    """More than 3 direction violations → HIGH coupling level."""
    cross = CrossFileSignals(
        dependency_direction_violations=[
            _make_direction_violation(f"a{i}.py", "db.py") for i in range(4)
        ]
    )
    spec = _compute_coupling_spec(cross)
    assert spec.overall_coupling_level == SignalLevel.HIGH
    assert spec.dependency_violation_count == 4


def test_coupling_level_medium_boundary():
    """2 high-coupling files → MEDIUM coupling level."""
    cross = CrossFileSignals(
        high_coupling_files=[_make_coupling_signal("a.py"), _make_coupling_signal("b.py")]
    )
    spec = _compute_coupling_spec(cross)
    assert spec.overall_coupling_level == SignalLevel.MEDIUM


def test_coupling_level_low_when_no_signals():
    """No coupling signals → LOW coupling level."""
    cross = CrossFileSignals()
    spec = _compute_coupling_spec(cross)
    assert spec.overall_coupling_level == SignalLevel.LOW
    assert spec.high_coupling_file_count == 0
    assert spec.dependency_violation_count == 0


# ---------------------------------------------------------------------------
# run_architecture_rules integration
# ---------------------------------------------------------------------------


def test_run_architecture_rules_returns_output_for_minimal_pcr():
    """run_architecture_rules must return a valid ArchitectureRuleOutput for any PCR."""
    pcr = _make_minimal_pcr()
    output = run_architecture_rules(pcr)

    assert isinstance(output, ArchitectureRuleOutput)
    assert output.detected_pattern in ArchitecturePattern
    assert output.confidence in Confidence
    assert isinstance(output.weakness_specs, list)
    assert isinstance(output.coupling_spec.high_coupling_file_count, int)


def test_run_architecture_rules_copies_test_coverage_signal():
    """run_architecture_rules must copy test_coverage_signal from PCR quality signals."""
    quality = QualitySignals(
        test_presence_ratio=0.35,
        test_coverage_signal=TestCoverageSignal.PRESENT,
        naming_consistency_signal=NamingConsistencySignal.CONSISTENT,
    )
    pcr = _make_minimal_pcr(quality_signals=quality)
    output = run_architecture_rules(pcr)
    assert output.test_coverage_signal == TestCoverageSignal.PRESENT


def test_run_architecture_rules_strong_pattern_detected():
    """run_architecture_rules must detect LAYERED when a STRONG indicator is present."""
    arch = ArchitectureSignals(
        cohesion_assessment=SignalLevel.HIGH,
        pattern_indicators={
            "LAYERED": PatternIndicator(
                pattern=ArchitecturePattern.LAYERED,
                evidence=["controllers/", "services/", "repositories/"],
                strength=PatternStrength.STRONG,
            )
        },
    )
    pcr = _make_minimal_pcr(architecture_signals=arch)
    output = run_architecture_rules(pcr)
    assert output.detected_pattern == ArchitecturePattern.LAYERED
    assert output.confidence == Confidence.HIGH
