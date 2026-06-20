"""Configuration package.

Exposes application settings and constants as the single source of truth
for all configuration values. No other module reads environment variables directly.
"""

from config.constants import (
    DISCLAIMER_TEXT,
    HIGH_COUPLING_FAN_IN_THRESHOLD,
    HIGH_COUPLING_FAN_OUT_THRESHOLD,
    KB_CATEGORY_DOMAIN_MAP,
    KB_CHUNK_MIN_LENGTH,
    LLM_MAX_RETRIES,
    LLM_TEMPERATURE,
    MAX_ANALYZABLE_FILES,
    MAX_FILE_SIZE_BYTES,
    MAX_REPO_SIZE_MB,
    RAG_RELEVANCE_THRESHOLD,
    RAG_TOP_K,
    REPORT_SCHEMA_VERSION,
    SECTION_ORDER,
    SUPPORTED_EXTENSIONS,
    TEST_FILE_PRESENCE_THRESHOLD_PARTIAL,
    TEST_FILE_PRESENCE_THRESHOLD_PRESENT,
)
from config.settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
    "DISCLAIMER_TEXT",
    "HIGH_COUPLING_FAN_IN_THRESHOLD",
    "HIGH_COUPLING_FAN_OUT_THRESHOLD",
    "KB_CATEGORY_DOMAIN_MAP",
    "KB_CHUNK_MIN_LENGTH",
    "LLM_MAX_RETRIES",
    "LLM_TEMPERATURE",
    "MAX_ANALYZABLE_FILES",
    "MAX_FILE_SIZE_BYTES",
    "MAX_REPO_SIZE_MB",
    "RAG_RELEVANCE_THRESHOLD",
    "RAG_TOP_K",
    "REPORT_SCHEMA_VERSION",
    "SECTION_ORDER",
    "SUPPORTED_EXTENSIONS",
    "TEST_FILE_PRESENCE_THRESHOLD_PARTIAL",
    "TEST_FILE_PRESENCE_THRESHOLD_PRESENT",
]
