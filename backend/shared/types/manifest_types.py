"""Data contracts for repository ingestion output.

RepositoryManifest is produced exclusively by the Repository Ingestion Service
and consumed by the Code Parser. It must never contain raw source code content.
The temp_clone_path field is nulled by ParseNode immediately after parsing
completes and the cloned repository is deleted from disk.

Dependency rule: imports only from shared/types/enums and stdlib/pydantic.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.types.enums import ManifestType


class DependencyEntry(BaseModel):
    """A single dependency declared in a package manifest file."""

    name: str = Field(..., description="Package or module name as declared in the manifest.")
    version: str | None = Field(
        default=None,
        description="Version specifier as written in the manifest. None if unspecified.",
    )


class DependencyManifest(BaseModel):
    """Parsed contents of a single dependency manifest file (e.g. requirements.txt)."""

    manifest_type: ManifestType = Field(
        ..., description="Which manifest file type this record represents."
    )
    dependencies: list[DependencyEntry] = Field(
        default_factory=list,
        description="Runtime dependencies declared in this manifest.",
    )
    dev_dependencies: list[DependencyEntry] = Field(
        default_factory=list,
        description=(
            "Development or test dependencies, if the manifest format distinguishes them "
            "(e.g. devDependencies in package.json). Empty list if not applicable."
        ),
    )


class LanguageStats(BaseModel):
    """Per-language file count and size statistics derived from the repository."""

    language: str = Field(..., description="Language name (e.g. 'Python', 'TypeScript').")
    file_count: int = Field(..., ge=0, description="Number of source files in this language.")
    estimated_line_count: int = Field(
        ..., ge=0, description="Rough aggregate line count estimate for this language."
    )
    percentage_of_codebase: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Proportion of analyzable files in this language. "
            "All language percentages sum to ≤ 1.0."
        ),
    )


class FileEntry(BaseModel):
    """Metadata record for a single file discovered during repository ingestion."""

    path: str = Field(..., description="Relative path from the repository root.")
    language: str = Field(..., description="Detected programming language.")
    size_bytes: int = Field(..., ge=0, description="File size in bytes.")
    is_test_file: bool = Field(
        ...,
        description=(
            "True when the path matches known test file naming conventions "
            "(e.g. test_*.py, *.spec.ts, *_test.go)."
        ),
    )
    is_skipped: bool = Field(
        ...,
        description="True when this file is excluded from analysis.",
    )
    skip_reason: str | None = Field(
        default=None,
        description="Human-readable reason for skipping. Must be non-null when is_skipped is True.",
    )

    @model_validator(mode="after")
    def validate_skip_reason_present_when_skipped(self) -> "FileEntry":
        """Enforce that skipped files always carry an explanation."""
        if self.is_skipped and not self.skip_reason:
            raise ValueError(
                f"File '{self.path}' is marked as skipped but provides no skip_reason."
            )
        return self


class DirectoryEntry(BaseModel):
    """Metadata record for a single directory in the repository tree."""

    path: str = Field(..., description="Relative directory path from the repository root.")
    depth: int = Field(
        ..., ge=0, description="Nesting depth from the root directory (root = 0)."
    )
    file_count: int = Field(
        ..., ge=0, description="Count of direct file children in this directory."
    )
    subdirectory_count: int = Field(
        ..., ge=0, description="Count of direct subdirectory children."
    )


class RepositoryManifest(BaseModel):
    """Structured description of a cloned repository.

    Produced by the Repository Ingestion Service after a successful shallow
    clone. Contains structural metadata, language statistics, and dependency
    information. Never contains raw source code.

    Ownership rules:
    - Created and fully populated by the Repository Ingestion Service.
    - temp_clone_path is valid only during IngestNode and ParseNode execution.
    - ParseNode nulls temp_clone_path after the clone is deleted from disk.
    - All downstream components (agents, RAG) treat this as read-only.
    - Not persisted to Supabase; exists only in AnalysisState during workflow.
    """

    manifest_id: UUID = Field(..., description="Unique identifier for this manifest instance.")
    job_id: UUID = Field(..., description="Parent analysis job this manifest belongs to.")
    repo_url: str = Field(..., description="Validated GitHub URL exactly as submitted.")
    repo_name: str = Field(..., description="Repository name extracted from the URL.")
    default_branch: str = Field(
        ..., description="Branch name checked out during the shallow clone."
    )
    primary_language: str = Field(
        ...,
        description=(
            "Language with the highest analyzable file count. "
            "Must be a key present in the languages map."
        ),
    )
    languages: dict[str, LanguageStats] = Field(
        ...,
        description="Per-language breakdown keyed by language name.",
    )
    file_list: list[FileEntry] = Field(
        ...,
        description="All files discovered in the repository, including skipped ones.",
    )
    directory_tree: list[DirectoryEntry] = Field(
        ...,
        description="Directory structure summary. Does not include file contents.",
    )
    total_file_count: int = Field(
        ..., ge=1, description="Total file count across all languages and types."
    )
    analyzable_file_count: int = Field(
        ...,
        ge=0,
        description="Files in supported languages eligible for Tree-sitter parsing.",
    )
    skipped_file_count: int = Field(
        ..., ge=0, description="Files excluded from analysis for any reason."
    )
    clone_timestamp: datetime = Field(
        ..., description="UTC timestamp when the git clone operation was initiated."
    )
    temp_clone_path: str | None = Field(
        default=None,
        description=(
            "Absolute path to the cloned repository on disk. "
            "Valid only during IngestNode and ParseNode execution. "
            "Set to None by ParseNode after the clone is deleted."
        ),
    )

    # --- Optional fields ---

    dependency_manifests: dict[str, DependencyManifest] | None = Field(
        default=None,
        description=(
            "Parsed contents of detected dependency manifests, keyed by ManifestType value. "
            "None when no supported manifest files are present."
        ),
    )
    repo_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Total repository size in bytes. None if undetectable.",
    )
    detected_frameworks: list[str] | None = Field(
        default=None,
        description=(
            "Best-effort framework signals derived from file patterns "
            "(e.g. 'Django', 'Express'). None when no signals detected."
        ),
    )

    # --- Validators ---

    @field_validator("repo_url", mode="before")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        """Enforce GitHub HTTPS URL format."""
        url = str(value).strip()
        if not url.startswith("https://github.com/"):
            raise ValueError(
                f"repo_url must be a GitHub HTTPS URL starting with "
                f"'https://github.com/'. Got: '{url}'"
            )
        return url

    @model_validator(mode="after")
    def validate_file_counts_consistent(self) -> "RepositoryManifest":
        """Enforce that analyzable_file_count does not exceed total_file_count."""
        if self.analyzable_file_count > self.total_file_count:
            raise ValueError(
                f"analyzable_file_count ({self.analyzable_file_count}) cannot exceed "
                f"total_file_count ({self.total_file_count})."
            )
        return self

    @model_validator(mode="after")
    def validate_primary_language_in_languages_map(self) -> "RepositoryManifest":
        """Enforce that primary_language is present in the languages map."""
        if self.primary_language not in self.languages:
            raise ValueError(
                f"primary_language '{self.primary_language}' must be a key in the "
                f"languages map. Available: {list(self.languages.keys())}"
            )
        return self

    @model_validator(mode="after")
    def validate_clone_timestamp_not_future(self) -> "RepositoryManifest":
        """Enforce that clone_timestamp is not in the future."""
        from datetime import timezone

        now = datetime.now(tz=timezone.utc)
        ts = self.clone_timestamp
        aware_ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if aware_ts > now:
            raise ValueError(
                f"clone_timestamp {self.clone_timestamp.isoformat()} is in the future."
            )
        return self
