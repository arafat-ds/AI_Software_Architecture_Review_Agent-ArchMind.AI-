"""Application settings loaded from environment variables.

All runtime configuration is defined here. No other module calls os.environ
or reads .env files directly. Consume settings via get_settings().

Usage:
    from config.settings import get_settings

    settings = get_settings()
    api_key = settings.gemini_api_key
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for ArchMind AI.

    Values are loaded in priority order:
    1. Environment variables (highest priority)
    2. .env file
    3. Field defaults (lowest priority)

    Required fields (no default) will raise ValidationError at startup
    if not present in the environment. This is intentional: the application
    must not start with missing critical configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Gemini API
    # ------------------------------------------------------------------

    gemini_api_key: str = Field(
        ...,
        description="Gemini API key. Required. Never logged or exposed in responses.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model ID used for all generation tasks.",
    )
    gemini_embedding_model: str = Field(
        default="models/gemini-embedding-001",
        description="Gemini embedding model ID used by the RAG embedder. Must match EMBEDDING_VECTOR_SIZE in constants.py.",
    )

    # ------------------------------------------------------------------
    # Qdrant
    # ------------------------------------------------------------------

    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant server hostname or IP address.",
    )
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant server gRPC/REST port.",
    )
    qdrant_collection_name: str = Field(
        default="archmind_kb",
        description="Qdrant collection name for the knowledge base vector store.",
    )

    # ------------------------------------------------------------------
    # Supabase
    # ------------------------------------------------------------------

    supabase_url: str = Field(
        ...,
        description="Supabase project URL (e.g. https://<project-ref>.supabase.co).",
    )
    supabase_key: str = Field(
        ...,
        description="Supabase service role key. Never logged or exposed in responses.",
    )

    # ------------------------------------------------------------------
    # API authentication
    # ------------------------------------------------------------------

    api_key: str = Field(
        ...,
        description=(
            "Static API key for authenticating all protected API endpoints. "
            "Required. Never logged or exposed in responses. "
            "Must be at least 32 characters. "
            'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        ),
    )

    # ------------------------------------------------------------------
    # API / CORS
    # ------------------------------------------------------------------

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="List of allowed CORS origins. Include the OpenWebUI origin.",
    )

    # ------------------------------------------------------------------
    # API / Concurrency
    # ------------------------------------------------------------------

    max_concurrent_jobs: int = Field(
        default=4,
        ge=1,
        le=32,
        description=(
            "Maximum number of analysis jobs that can run concurrently. "
            "Controls the ThreadPoolExecutor worker count in the API process. "
            "Each job holds a git clone, LLM connections, and Qdrant connections "
            "for its full duration (~5-15 min). Size conservatively. "
            "Env var: MAX_CONCURRENT_JOBS."
        ),
    )

    # ------------------------------------------------------------------
    # Repository ingestion
    # ------------------------------------------------------------------

    max_clone_timeout_seconds: int = Field(
        default=120,
        description="Hard timeout for git clone operations in seconds.",
    )

    # ------------------------------------------------------------------
    # LLM call limits
    # ------------------------------------------------------------------

    llm_max_tokens: int = Field(
        default=8192,
        description="Maximum output tokens per Gemini API generation call.",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    log_level: str = Field(
        default="INFO",
        description="Application log level. One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        """Ensure the API key meets minimum length for adequate entropy."""
        key = str(value).strip()
        if len(key) < 32:
            raise ValueError(
                "api_key must be at least 32 characters. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return key

    @field_validator("log_level", mode="before")
    @classmethod
    def normalise_log_level(cls, value: str) -> str:
        """Normalise and validate the log level string."""
        normalised = str(value).upper().strip()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalised not in valid_levels:
            raise ValueError(
                f"log_level '{value}' is not valid. Must be one of: {sorted(valid_levels)}"
            )
        return normalised

    @field_validator("qdrant_port", mode="before")
    @classmethod
    def validate_qdrant_port(cls, value: int) -> int:
        """Ensure the Qdrant port is within the valid TCP port range."""
        port = int(value)
        if not (1 <= port <= 65535):
            raise ValueError(f"qdrant_port {port} is outside the valid range 1–65535.")
        return port

    @field_validator("llm_max_tokens", mode="before")
    @classmethod
    def validate_llm_max_tokens(cls, value: int) -> int:
        """Ensure token limit is a positive integer."""
        tokens = int(value)
        if tokens < 1:
            raise ValueError("llm_max_tokens must be a positive integer.")
        return tokens

    @field_validator("max_clone_timeout_seconds", mode="before")
    @classmethod
    def validate_clone_timeout(cls, value: int) -> int:
        """Ensure clone timeout is a positive integer."""
        timeout = int(value)
        if timeout < 1:
            raise ValueError("max_clone_timeout_seconds must be a positive integer.")
        return timeout

    @field_validator("supabase_url", mode="before")
    @classmethod
    def validate_supabase_url(cls, value: str) -> str:
        """Ensure Supabase URL uses HTTPS."""
        url = str(value).strip()
        if not url.startswith("https://"):
            raise ValueError("supabase_url must use HTTPS.")
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application Settings singleton.

    The instance is created once and cached for the process lifetime.
    In tests, call get_settings.cache_clear() before patching environment
    variables to ensure a fresh instance is created.

    Returns:
        Settings: The validated application configuration.

    Raises:
        ValidationError: If any required environment variable is missing or invalid.
    """
    return Settings()
