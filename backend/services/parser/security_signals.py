"""Security risk signal extraction.

Detects hardcoded secrets, missing input validation, auth bypass patterns,
SQL construction risks, and insecure defaults via regex heuristics on source text.

All detection is signal-based only. No findings are confirmed vulnerabilities.
"""

from __future__ import annotations

import re

from shared.types.enums import (
    AuthSignalType,
    SQLSignalType,
    SecretSignalType,
    ValidationGapType,
)
from shared.types.pcr_types import (
    AuthSignal,
    FileAnalysis,
    SQLSignal,
    SecretSignal,
    SecuritySignals,
    ValidationGapSignal,
)

_SECRET_PATTERNS: list[tuple[SecretSignalType, re.Pattern[str]]] = [
    (SecretSignalType.API_KEY_LITERAL, re.compile(r'(?i)(api_key|apikey)\s*=\s*["\'][^"\']{8,}["\']')),
    (SecretSignalType.PASSWORD_LITERAL, re.compile(r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']')),
    (SecretSignalType.TOKEN_LITERAL, re.compile(r'(?i)(token|secret|access_token)\s*=\s*["\'][^"\']{8,}["\']')),
    (SecretSignalType.SECRET_LITERAL, re.compile(r'(?i)(connection_string|database_url|db_url)\s*=\s*["\'][^"\']{10,}["\']')),
]

_AUTH_BYPASS_PATTERNS: list[tuple[AuthSignalType, re.Pattern[str]]] = [
    (AuthSignalType.BYPASSED_CHECK_INDICATOR, re.compile(r'(?i)(admin|root|password)\s*==\s*["\'][^"\']+["\']')),
    (AuthSignalType.NO_GUARD_PRESENT, re.compile(r'(?i)def\s+(login|authenticate|verify)\s*\([^)]*\)\s*:\s*\n\s*(return True|pass)')),
]

_SQL_CONSTRUCTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?i)(SELECT|INSERT|UPDATE|DELETE).*\+\s*[a-zA-Z_]'),
    re.compile(r'(?i)f["\'].*SELECT.*\{'),
    re.compile(r'(?i)%s.*WHERE|WHERE.*%s'),
]

_INSECURE_DEFAULT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?i)DEBUG\s*=\s*True'),
    re.compile(r'(?i)CORS_ALLOW_ALL_ORIGINS\s*=\s*True'),
    re.compile(r'(?i)CORS_ORIGIN_ALLOW_ALL\s*=\s*True'),
    re.compile(r'(?i)verify\s*=\s*False'),
]


def extract_security_signals(
    file_analyses: list[FileAnalysis],
    source_map: dict[str, str],
) -> SecuritySignals:
    """Detect security risk patterns from file content strings.

    Args:
        file_analyses: Per-file structural analyses.
        source_map: Map of file path to raw source text for pattern matching.
    """
    secrets: list[SecretSignal] = []
    validation_gaps: list[ValidationGapSignal] = []
    auth_signals: list[AuthSignal] = []
    sql_signals: list[SQLSignal] = []
    insecure_defaults: list[str] = []
    missing_error_handling: list[str] = []

    for fa in file_analyses:
        source = source_map.get(fa.path, "")
        if not source:
            continue

        for signal_type, pattern in _SECRET_PATTERNS:
            if pattern.search(source):
                secrets.append(SecretSignal(
                    file_path=fa.path,
                    signal_type=signal_type,
                    context_description=f"Possible hardcoded {signal_type.value} detected",
                ))

        for auth_type, pattern in _AUTH_BYPASS_PATTERNS:
            if pattern.search(source):
                auth_signals.append(AuthSignal(
                    file_path=fa.path,
                    function_name="<unknown>",
                    signal_type=auth_type,
                ))

        for pattern in _SQL_CONSTRUCTION_PATTERNS:
            if pattern.search(source):
                sql_signals.append(SQLSignal(
                    file_path=fa.path,
                    signal_type=SQLSignalType.STRING_CONCATENATION_NEAR_DB_CALL,
                ))
                break

        for pattern in _INSECURE_DEFAULT_PATTERNS:
            if pattern.search(source):
                insecure_defaults.append(fa.path)
                break

        for defn in fa.definition_summaries:
            if _is_entry_point(defn.name) and defn.parameter_count > 0:
                if not _has_validation_import(fa.import_list):
                    validation_gaps.append(ValidationGapSignal(
                        file_path=fa.path,
                        function_name=defn.name,
                        gap_type=ValidationGapType.MISSING_INPUT_VALIDATION,
                    ))

    return SecuritySignals(
        hardcoded_secret_indicators=secrets,
        missing_input_validation_indicators=validation_gaps,
        auth_bypass_indicators=auth_signals,
        sql_construction_indicators=sql_signals,
        insecure_default_indicators=insecure_defaults,
        missing_error_handling_indicators=missing_error_handling,
    )


def _is_entry_point(func_name: str) -> bool:
    lower = func_name.lower()
    return any(kw in lower for kw in ("route", "endpoint", "handler", "view",
                                      "controller", "api", "webhook"))


def _has_validation_import(import_list: list[str]) -> bool:
    text = " ".join(import_list).lower()
    return any(kw in text for kw in ("pydantic", "marshmallow", "cerberus",
                                     "voluptuous", "schema", "validator",
                                     "validate", "jsonschema"))
