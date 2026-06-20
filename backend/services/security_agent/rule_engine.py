"""Security Agent deterministic rule engine.

Maps raw PCR security signals to typed SecurityFindings with all
deterministic fields assigned: severity, confidence, OWASP category,
CWE ID, and evidence references.

Nothing here calls the Gemini API. The LLM fills in description text
for each finding after this module runs.

INVARIANTS enforced by this module (not by the LLM):
- Severity is always assigned from the signal-type table below.
- OWASPCategory is always assigned from the signal-type table.
- CWE is always assigned from the static map or None.
- is_confirmed_vulnerability is always False (Literal[False] in the type).
- One finding per signal category (MVP grouping strategy).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.types.analysis_types import EvidenceRef
from shared.types.enums import (
    Confidence,
    OWASPCategory,
    Severity,
)
from shared.types.pcr_types import SecuritySignals


# ---------------------------------------------------------------------------
# Intermediate data contract (internal to the security agent)
# ---------------------------------------------------------------------------


@dataclass
class FindingSpec:
    """A security finding identified by the rule engine before LLM enrichment.

    description is an empty string here — filled in by the service
    after the LLM call. All other fields are final.
    """

    finding_id: str
    title: str
    severity: Severity
    confidence: Confidence
    owasp_category: OWASPCategory | None
    cwe_id: str | None
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_findings(security_signals: SecuritySignals) -> list[FindingSpec]:
    """Generate FindingSpec entries from PCR security signals.

    One FindingSpec is produced per non-empty signal category (MVP strategy).
    Returns an empty list when all signal categories are empty.

    Severity, OWASP category, CWE, and confidence are assigned deterministically
    from the tables in this module. The LLM never changes these values.

    Args:
        security_signals: SecuritySignals from the ParsedCodeRepresentation.

    Returns:
        List of FindingSpec entries ordered by descending severity.
    """
    specs: list[FindingSpec] = []
    counter = 1

    def _next_id() -> str:
        nonlocal counter
        fid = f"SF-{counter:03d}"
        counter += 1
        return fid

    # Hardcoded secrets → A02 / CWE-798 / HIGH
    if security_signals.hardcoded_secret_indicators:
        count = len(security_signals.hardcoded_secret_indicators)
        evidence = [
            EvidenceRef(
                file_path=s.file_path,
                signal_type=s.signal_type.value,
                context_description=s.context_description,
            )
            for s in security_signals.hardcoded_secret_indicators[:10]
        ]
        specs.append(FindingSpec(
            finding_id=_next_id(),
            title="Hardcoded Secret or Credential",
            severity=Severity.HIGH,
            confidence=_confidence_from_count(count, min_medium=True),
            owasp_category=OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES,
            cwe_id="CWE-798",
            evidence_refs=evidence,
        ))

    # SQL construction patterns → A03 / CWE-89 / HIGH
    if security_signals.sql_construction_indicators:
        count = len(security_signals.sql_construction_indicators)
        evidence = [
            EvidenceRef(
                file_path=s.file_path,
                signal_type=s.signal_type.value,
                context_description=f"SQL string construction pattern detected: {s.signal_type.value}",
            )
            for s in security_signals.sql_construction_indicators[:10]
        ]
        specs.append(FindingSpec(
            finding_id=_next_id(),
            title="Potential SQL Injection Risk",
            severity=Severity.HIGH,
            confidence=_confidence_from_count(count, min_medium=True),
            owasp_category=OWASPCategory.A03_INJECTION,
            cwe_id="CWE-89",
            evidence_refs=evidence,
        ))

    # Authentication control gaps → A07 / CWE-306 / HIGH
    if security_signals.auth_bypass_indicators:
        count = len(security_signals.auth_bypass_indicators)
        evidence = [
            EvidenceRef(
                file_path=s.file_path,
                signal_type=s.signal_type.value,
                context_description=(
                    f"Auth signal in '{s.function_name}': {s.signal_type.value}"
                ),
            )
            for s in security_signals.auth_bypass_indicators[:10]
        ]
        specs.append(FindingSpec(
            finding_id=_next_id(),
            title="Authentication Control Gap",
            severity=Severity.HIGH,
            confidence=_confidence_from_count(count),
            owasp_category=OWASPCategory.A07_AUTH_FAILURES,
            cwe_id="CWE-306",
            evidence_refs=evidence,
        ))

    # Missing input validation → A03 / CWE-20 / MEDIUM
    if security_signals.missing_input_validation_indicators:
        count = len(security_signals.missing_input_validation_indicators)
        evidence = [
            EvidenceRef(
                file_path=s.file_path,
                signal_type=s.gap_type.value,
                context_description=f"Validation gap in '{s.function_name}': {s.gap_type.value}",
            )
            for s in security_signals.missing_input_validation_indicators[:10]
        ]
        specs.append(FindingSpec(
            finding_id=_next_id(),
            title="Missing Input Validation",
            severity=Severity.MEDIUM,
            confidence=_confidence_from_count(count),
            owasp_category=OWASPCategory.A03_INJECTION,
            cwe_id="CWE-20",
            evidence_refs=evidence,
        ))

    # Insecure default configurations → A05 / CWE-1188 / MEDIUM
    if security_signals.insecure_default_indicators:
        count = len(security_signals.insecure_default_indicators)
        evidence = [
            EvidenceRef(
                file_path=path,
                signal_type="insecure_default_indicator",
                context_description="Insecure default configuration pattern detected in this file",
            )
            for path in security_signals.insecure_default_indicators[:10]
        ]
        specs.append(FindingSpec(
            finding_id=_next_id(),
            title="Insecure Default Configuration",
            severity=Severity.MEDIUM,
            confidence=_confidence_from_count(count),
            owasp_category=OWASPCategory.A05_SECURITY_MISCONFIGURATION,
            cwe_id="CWE-1188",
            evidence_refs=evidence,
        ))

    # Missing error handling in security-sensitive paths → A09 / LOW
    if security_signals.missing_error_handling_indicators:
        count = len(security_signals.missing_error_handling_indicators)
        evidence = [
            EvidenceRef(
                file_path=path,
                signal_type="missing_error_handling_indicator",
                context_description="Missing error handling detected in security-relevant code path",
            )
            for path in security_signals.missing_error_handling_indicators[:10]
        ]
        specs.append(FindingSpec(
            finding_id=_next_id(),
            title="Insufficient Error Handling in Security Code",
            severity=Severity.LOW,
            confidence=_confidence_from_count(count),
            owasp_category=OWASPCategory.A09_LOGGING_MONITORING_FAILURES,
            cwe_id=None,
            evidence_refs=evidence,
        ))

    return specs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _confidence_from_count(count: int, min_medium: bool = False) -> Confidence:
    """Derive confidence from the number of signal occurrences.

    Args:
        count: Number of files or signal instances in this category.
        min_medium: When True, count=1 yields MEDIUM instead of LOW.
                    Used for high-specificity signals (API keys, SQL patterns).
    """
    if count >= 3:
        return Confidence.HIGH
    if count >= 2 or min_medium:
        return Confidence.MEDIUM
    return Confidence.LOW
