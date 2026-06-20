"""Exceptions raised by the Repository Ingestion Service.

All exceptions inherit from IngestionError so callers can catch the entire
family with a single except clause while still handling specific sub-cases
when finer-grained logic is required.

Dependency rule: no imports from other application modules.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base exception for all repository ingestion failures.

    Raised by services/ingestion/ components. The LangGraph IngestNode
    treats all IngestionError subclasses as fatal workflow errors.
    """

    def __init__(self, message: str, repo_url: str | None = None) -> None:
        self.repo_url = repo_url
        super().__init__(message)


class InvalidGitHubURLError(IngestionError):
    """Raised when the submitted URL is not a valid public GitHub repository URL.

    This is a validation failure that occurs before any network request is made.
    The API layer catches this and returns HTTP 400 to the client.
    """

    def __init__(self, url: str) -> None:
        super().__init__(
            f"'{url}' is not a valid public GitHub repository URL. "
            "Expected format: https://github.com/<owner>/<repo>",
            repo_url=url,
        )
        self.url = url


class PrivateRepoError(IngestionError):
    """Raised when the target repository is private or requires authentication.

    Public repository access is an MVP requirement. Private repository support
    is deferred to Phase 2.
    """

    def __init__(self, repo_url: str) -> None:
        super().__init__(
            f"Repository '{repo_url}' is private or requires authentication. "
            "ArchMind AI supports public repositories only in this version.",
            repo_url=repo_url,
        )


class CloneTimeoutError(IngestionError):
    """Raised when the git clone operation exceeds the configured timeout.

    The timeout threshold is configured via MAX_CLONE_TIMEOUT_SECONDS in
    config/settings.py. Large repositories or slow network conditions trigger
    this exception.
    """

    def __init__(self, repo_url: str, timeout_seconds: int) -> None:
        super().__init__(
            f"Clone of '{repo_url}' exceeded the {timeout_seconds}s timeout. "
            "Consider analysing a smaller repository or increasing MAX_CLONE_TIMEOUT_SECONDS.",
            repo_url=repo_url,
        )
        self.timeout_seconds = timeout_seconds


class RepositoryTooLargeError(IngestionError):
    """Raised when the repository size exceeds the configured maximum.

    The size limit is configured via MAX_REPO_SIZE_MB in config/constants.py.
    Prevents runaway disk usage during ingestion.
    """

    def __init__(self, repo_url: str, size_mb: float, limit_mb: int) -> None:
        super().__init__(
            f"Repository '{repo_url}' is {size_mb:.1f} MB which exceeds the "
            f"{limit_mb} MB analysis limit.",
            repo_url=repo_url,
        )
        self.size_mb = size_mb
        self.limit_mb = limit_mb


class EmptyRepositoryError(IngestionError):
    """Raised when a repository contains no files eligible for analysis.

    Triggered when analyzable_file_count is zero after scanning the cloned
    repository. The workflow cannot proceed without at least one parseable file.
    """

    def __init__(self, repo_url: str) -> None:
        super().__init__(
            f"Repository '{repo_url}' contains no files in supported languages. "
            "At least one analyzable source file is required.",
            repo_url=repo_url,
        )


class CloneFailedError(IngestionError):
    """Raised when the git clone operation fails for a reason other than timeout.

    Wraps GitPython exceptions to decouple the rest of the application from
    the GitPython API surface.
    """

    def __init__(self, repo_url: str, reason: str) -> None:
        super().__init__(
            f"Failed to clone repository '{repo_url}': {reason}",
            repo_url=repo_url,
        )
        self.reason = reason
