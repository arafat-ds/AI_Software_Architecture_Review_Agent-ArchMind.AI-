"""Unit tests for the Security Agent deterministic rule engine.

All tests are pure: no Gemini calls, no settings, no .env required.
Tests verify severity, OWASP, CWE, and confidence assignments.
"""

from __future__ import annotations

import pytest

from services.security_agent.rule_engine import FindingSpec, _confidence_from_count, generate_findings
from shared.types.enums import (
    AuthSignalType,
    Confidence,
    OWASPCategory,
    SQLSignalType,
    SecretSignalType,
    Severity,
    ValidationGapType,
)
from shared.types.pcr_types import (
    AuthSignal,
    SQLSignal,
    SecretSignal,
    SecuritySignals,
    ValidationGapSignal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _secret(path: str = "config.py", stype: SecretSignalType = SecretSignalType.API_KEY_LITERAL) -> SecretSignal:
    return SecretSignal(
        file_path=path,
        signal_type=stype,
        context_description="API key pattern detected in variable assignment",
    )


def _sql(path: str = "db.py") -> SQLSignal:
    return SQLSignal(
        file_path=path,
        signal_type=SQLSignalType.STRING_CONCATENATION_NEAR_DB_CALL,
    )


def _auth(path: str = "auth.py", fname: str = "login") -> AuthSignal:
    return AuthSignal(
        file_path=path,
        function_name=fname,
        signal_type=AuthSignalType.NO_GUARD_PRESENT,
    )


def _validation_gap(path: str = "api.py", fname: str = "handle_request") -> ValidationGapSignal:
    return ValidationGapSignal(
        file_path=path,
        function_name=fname,
        gap_type=ValidationGapType.MISSING_INPUT_VALIDATION,
    )


# ---------------------------------------------------------------------------
# generate_findings — basic presence tests
# ---------------------------------------------------------------------------


def test_generate_findings_empty_signals_returns_empty():
    """No signals → no findings."""
    findings = generate_findings(SecuritySignals())
    assert findings == []


def test_generate_findings_secret_indicator_produces_one_finding():
    """One secret indicator → exactly one SF finding."""
    signals = SecuritySignals(hardcoded_secret_indicators=[_secret()])
    findings = generate_findings(signals)
    assert len(findings) == 1
    assert findings[0].finding_id == "SF-001"


def test_generate_findings_all_categories_produce_six_findings():
    """One signal per category → six findings."""
    signals = SecuritySignals(
        hardcoded_secret_indicators=[_secret()],
        sql_construction_indicators=[_sql()],
        auth_bypass_indicators=[_auth()],
        missing_input_validation_indicators=[_validation_gap()],
        insecure_default_indicators=["settings.py"],
        missing_error_handling_indicators=["handler.py"],
    )
    findings = generate_findings(signals)
    assert len(findings) == 6
    ids = [f.finding_id for f in findings]
    assert ids == [f"SF-{i:03d}" for i in range(1, 7)]


def test_generate_findings_ids_are_sequential():
    """Finding IDs are assigned sequentially from SF-001."""
    signals = SecuritySignals(
        hardcoded_secret_indicators=[_secret()],
        sql_construction_indicators=[_sql()],
    )
    findings = generate_findings(signals)
    assert findings[0].finding_id == "SF-001"
    assert findings[1].finding_id == "SF-002"


# ---------------------------------------------------------------------------
# Severity assignments
# ---------------------------------------------------------------------------


def test_secret_finding_has_high_severity():
    signals = SecuritySignals(hardcoded_secret_indicators=[_secret()])
    finding = generate_findings(signals)[0]
    assert finding.severity == Severity.HIGH


def test_sql_finding_has_high_severity():
    signals = SecuritySignals(sql_construction_indicators=[_sql()])
    finding = generate_findings(signals)[0]
    assert finding.severity == Severity.HIGH


def test_auth_finding_has_high_severity():
    signals = SecuritySignals(auth_bypass_indicators=[_auth()])
    finding = generate_findings(signals)[0]
    assert finding.severity == Severity.HIGH


def test_validation_gap_finding_has_medium_severity():
    signals = SecuritySignals(missing_input_validation_indicators=[_validation_gap()])
    finding = generate_findings(signals)[0]
    assert finding.severity == Severity.MEDIUM


def test_insecure_default_finding_has_medium_severity():
    signals = SecuritySignals(insecure_default_indicators=["app.py"])
    finding = generate_findings(signals)[0]
    assert finding.severity == Severity.MEDIUM


def test_error_handling_finding_has_low_severity():
    signals = SecuritySignals(missing_error_handling_indicators=["handler.py"])
    finding = generate_findings(signals)[0]
    assert finding.severity == Severity.LOW


# ---------------------------------------------------------------------------
# OWASP category assignments
# ---------------------------------------------------------------------------


def test_secret_owasp_is_a02():
    signals = SecuritySignals(hardcoded_secret_indicators=[_secret()])
    finding = generate_findings(signals)[0]
    assert finding.owasp_category == OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES


def test_sql_owasp_is_a03():
    signals = SecuritySignals(sql_construction_indicators=[_sql()])
    finding = generate_findings(signals)[0]
    assert finding.owasp_category == OWASPCategory.A03_INJECTION


def test_auth_owasp_is_a07():
    signals = SecuritySignals(auth_bypass_indicators=[_auth()])
    finding = generate_findings(signals)[0]
    assert finding.owasp_category == OWASPCategory.A07_AUTH_FAILURES


def test_validation_gap_owasp_is_a03():
    signals = SecuritySignals(missing_input_validation_indicators=[_validation_gap()])
    finding = generate_findings(signals)[0]
    assert finding.owasp_category == OWASPCategory.A03_INJECTION


def test_insecure_default_owasp_is_a05():
    signals = SecuritySignals(insecure_default_indicators=["app.py"])
    finding = generate_findings(signals)[0]
    assert finding.owasp_category == OWASPCategory.A05_SECURITY_MISCONFIGURATION


def test_error_handling_owasp_is_a09():
    signals = SecuritySignals(missing_error_handling_indicators=["handler.py"])
    finding = generate_findings(signals)[0]
    assert finding.owasp_category == OWASPCategory.A09_LOGGING_MONITORING_FAILURES


# ---------------------------------------------------------------------------
# CWE assignments
# ---------------------------------------------------------------------------


def test_secret_cwe_is_798():
    signals = SecuritySignals(hardcoded_secret_indicators=[_secret()])
    assert generate_findings(signals)[0].cwe_id == "CWE-798"


def test_sql_cwe_is_89():
    signals = SecuritySignals(sql_construction_indicators=[_sql()])
    assert generate_findings(signals)[0].cwe_id == "CWE-89"


def test_auth_cwe_is_306():
    signals = SecuritySignals(auth_bypass_indicators=[_auth()])
    assert generate_findings(signals)[0].cwe_id == "CWE-306"


def test_validation_gap_cwe_is_20():
    signals = SecuritySignals(missing_input_validation_indicators=[_validation_gap()])
    assert generate_findings(signals)[0].cwe_id == "CWE-20"


def test_insecure_default_cwe_is_1188():
    signals = SecuritySignals(insecure_default_indicators=["app.py"])
    assert generate_findings(signals)[0].cwe_id == "CWE-1188"


def test_error_handling_cwe_is_none():
    signals = SecuritySignals(missing_error_handling_indicators=["handler.py"])
    assert generate_findings(signals)[0].cwe_id is None


# ---------------------------------------------------------------------------
# Confidence from count
# ---------------------------------------------------------------------------


def test_confidence_high_when_count_gte_3():
    assert _confidence_from_count(3) == Confidence.HIGH
    assert _confidence_from_count(10) == Confidence.HIGH


def test_confidence_medium_when_count_2():
    assert _confidence_from_count(2) == Confidence.MEDIUM


def test_confidence_low_when_count_1():
    assert _confidence_from_count(1) == Confidence.LOW


def test_confidence_medium_when_min_medium_and_count_1():
    """min_medium=True must yield MEDIUM even for count=1."""
    assert _confidence_from_count(1, min_medium=True) == Confidence.MEDIUM


def test_secret_single_occurrence_has_medium_confidence():
    """Single secret signal must yield at least MEDIUM confidence (min_medium=True)."""
    signals = SecuritySignals(hardcoded_secret_indicators=[_secret()])
    finding = generate_findings(signals)[0]
    assert finding.confidence in {Confidence.MEDIUM, Confidence.HIGH}


def test_secret_three_occurrences_have_high_confidence():
    """Three secret signals must yield HIGH confidence."""
    signals = SecuritySignals(
        hardcoded_secret_indicators=[_secret(f"f{i}.py") for i in range(3)]
    )
    finding = generate_findings(signals)[0]
    assert finding.confidence == Confidence.HIGH


# ---------------------------------------------------------------------------
# Evidence refs
# ---------------------------------------------------------------------------


def test_evidence_refs_capped_at_ten():
    """Evidence refs per finding must not exceed 10."""
    signals = SecuritySignals(
        hardcoded_secret_indicators=[_secret(f"file_{i}.py") for i in range(15)]
    )
    finding = generate_findings(signals)[0]
    assert len(finding.evidence_refs) <= 10


def test_evidence_refs_contain_file_paths():
    """Evidence refs must include the correct file path."""
    signals = SecuritySignals(hardcoded_secret_indicators=[_secret("secrets/config.py")])
    finding = generate_findings(signals)[0]
    assert any(ref.file_path == "secrets/config.py" for ref in finding.evidence_refs)


def test_evidence_refs_never_contain_secret_values():
    """Context descriptions must not expose actual secret literal values."""
    signals = SecuritySignals(
        hardcoded_secret_indicators=[
            SecretSignal(
                file_path="config.py",
                signal_type=SecretSignalType.PASSWORD_LITERAL,
                context_description="Password pattern detected in variable assignment",
            )
        ]
    )
    finding = generate_findings(signals)[0]
    for ref in finding.evidence_refs:
        assert "password123" not in ref.context_description.lower()
        assert "secret_value" not in ref.context_description.lower()
