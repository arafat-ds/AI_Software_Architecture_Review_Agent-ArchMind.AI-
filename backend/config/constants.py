"""Non-sensitive hardcoded application constants.

All tuneable thresholds, limits, and default values that are not secrets
and do not vary between environments. Environment-specific overrides belong
in settings.py, not here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Repository ingestion
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".rb",
    ".rs",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".kt",
    ".swift",
    ".scala",
    ".php",
})

MAX_ANALYZABLE_FILES: int = 500
"""Maximum number of source files processed per analysis job."""

MAX_FILE_SIZE_BYTES: int = 1_000_000
"""Files larger than 1 MB are skipped during parsing."""

MAX_REPO_SIZE_MB: int = 200
"""Repositories exceeding this size in MB are rejected before cloning."""

# ---------------------------------------------------------------------------
# Code parser / Tree-sitter
# ---------------------------------------------------------------------------

HIGH_COUPLING_FAN_IN_THRESHOLD: int = 10
"""Files imported by more than this many other files are flagged as hub files."""

HIGH_COUPLING_FAN_OUT_THRESHOLD: int = 15
"""Files importing more than this many other modules are flagged as high fan-out."""

TEST_FILE_PRESENCE_THRESHOLD_PARTIAL: float = 0.10
"""Below this ratio of test files to total files, coverage is PARTIAL."""

TEST_FILE_PRESENCE_THRESHOLD_PRESENT: float = 0.30
"""At or above this ratio, test coverage is considered PRESENT."""

# ---------------------------------------------------------------------------
# RAG / Qdrant
# ---------------------------------------------------------------------------

RAG_RELEVANCE_THRESHOLD: float = 0.72
"""Minimum cosine similarity score for a chunk to be included in retrieval results."""

RAG_TOP_K: int = 5
"""Maximum number of chunks returned per semantic query."""

KB_CHUNK_MIN_LENGTH: int = 100
"""Minimum character count for a knowledge base chunk to be indexed."""

KB_CATEGORY_DOMAIN_MAP: dict[str, str] = {
    "architecture": "ARCHITECTURE",
    "security": "SECURITY",
    "quality": "QUALITY",
}
"""Maps knowledge base subdirectory names to RAGDomain enum string values.
Add new categories here; the loader requires no other changes."""

# ---------------------------------------------------------------------------
# LLM / Gemini
# ---------------------------------------------------------------------------

LLM_TEMPERATURE: float = 0.3
"""Generation temperature applied to all Gemini API calls."""

LLM_MAX_RETRIES: int = 3
"""Maximum retry attempts for transient Gemini API failures before raising."""

# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

REPORT_SCHEMA_VERSION: str = "1.0"
"""Schema version embedded in persisted FinalReport and JobRecord documents."""

SECTION_ORDER: list[str] = [
    "EXECUTIVE_SUMMARY",
    "REPOSITORY_OVERVIEW",
    "ARCHITECTURE_ASSESSMENT",
    "SECURITY_FINDINGS",
    "RECOMMENDATIONS",
    "ACTIONABLE_NEXT_STEPS",
]
"""Canonical section ordering enforced by the Report Assembly Service.
Consumer rendering depends on this sequence. Do not reorder without a schema
version bump and a coordinated UI update."""

DISCLAIMER_TEXT: str = (
    "Findings represent risk signals from static analysis only. "
    "These are not confirmed vulnerabilities. "
    "Manual security review is required to validate all findings."
)
"""Fixed disclaimer appended to every SecuritySection. This text is a
contractual requirement; it must not be modified by any agent or LLM call."""

# ---------------------------------------------------------------------------
# Recommendation agent
# ---------------------------------------------------------------------------

RECOMMENDATION_MIN_NEXT_STEPS: int = 3
"""Minimum number of actionable next steps the Recommendation Agent must produce."""

RECOMMENDATION_MAX_NEXT_STEPS: int = 10
"""Maximum number of actionable next steps allowed in a single report."""
