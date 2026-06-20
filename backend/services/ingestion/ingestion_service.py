"""Orchestrates repository cloning and manifest construction.

Responsibility: clone the repository with timeout enforcement, validate
preconditions (URL format, repo accessibility, size), then delegate to
manifest_builder for filesystem traversal.

Cleans up the clone directory on failure. On success, the clone remains
on disk at temp_clone_path for ParseNode to use; ParseNode is responsible
for cleanup after parsing completes.
"""

from __future__ import annotations

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from uuid import UUID

import git
from git import GitCommandError, InvalidGitRepositoryError

from config.constants import MAX_REPO_SIZE_MB
from services.ingestion.manifest_builder import build_manifest
from shared.exceptions.ingestion_exceptions import (
    CloneFailedError,
    CloneTimeoutError,
    EmptyRepositoryError,
    InvalidGitHubURLError,
    PrivateRepoError,
    RepositoryTooLargeError,
)
from shared.logging.logger import get_logger
from shared.types.manifest_types import RepositoryManifest

logger = get_logger(__name__)

_CLONE_TIMEOUT_SECONDS: int = 120


class IngestionService:
    """Clones a GitHub repository and builds a RepositoryManifest.

    Stateless — safe to instantiate once and call run() multiple times.
    Each run() call is independent and uses a fresh temp directory.
    """

    def run(self, job_id: UUID, repo_url: str) -> RepositoryManifest:
        """Clone the repository and return a RepositoryManifest.

        Args:
            job_id: Parent job UUID.
            repo_url: Validated GitHub HTTPS URL.

        Returns:
            RepositoryManifest with temp_clone_path set to the cloned directory.

        Raises:
            InvalidGitHubURLError: URL is not a valid GitHub HTTPS URL.
            PrivateRepoError: Repository is private or requires authentication.
            CloneTimeoutError: Clone exceeded the timeout limit.
            RepositoryTooLargeError: Repository exceeds MAX_REPO_SIZE_MB.
            EmptyRepositoryError: Repository has no commits.
            CloneFailedError: Clone failed for any other reason.
        """
        _validate_github_url(repo_url)
        repo_name = _extract_repo_name(repo_url)

        logger.info("Starting repository clone", extra={
            "job_id": str(job_id),
            "repo_url": repo_url,
        })

        clone_dir = tempfile.mkdtemp(prefix="archmind_clone_")
        try:
            _clone_with_timeout(repo_url, clone_dir)
            _validate_repo_size(clone_dir, repo_url)
            _validate_not_empty(clone_dir, repo_url)

            manifest = build_manifest(
                job_id=job_id,
                repo_url=repo_url,
                repo_name=repo_name,
                clone_path=clone_dir,
            )

            logger.info("Repository ingestion complete", extra={
                "job_id": str(job_id),
                "total_files": manifest.total_file_count,
                "analyzable_files": manifest.analyzable_file_count,
                "primary_language": manifest.primary_language,
            })
            return manifest

        except (
            InvalidGitHubURLError,
            PrivateRepoError,
            CloneTimeoutError,
            RepositoryTooLargeError,
            EmptyRepositoryError,
            CloneFailedError,
        ):
            shutil.rmtree(clone_dir, ignore_errors=True)
            raise

        except Exception as exc:
            shutil.rmtree(clone_dir, ignore_errors=True)
            raise CloneFailedError(repo_url=repo_url, reason=str(exc)) from exc


def _validate_github_url(repo_url: str) -> None:
    if not repo_url.startswith("https://github.com/"):
        raise InvalidGitHubURLError(
            f"URL must be a GitHub HTTPS URL. Got: '{repo_url}'"
        )


def _extract_repo_name(repo_url: str) -> str:
    parts = repo_url.rstrip("/").split("/")
    name = parts[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def _clone_with_timeout(repo_url: str, target_dir: str) -> None:
    """Clone repo into target_dir with a hard timeout."""
    def _do_clone() -> None:
        try:
            git.Repo.clone_from(repo_url, target_dir, depth=1)
        except GitCommandError as exc:
            error_str = str(exc).lower()
            if "authentication" in error_str or "repository not found" in error_str:
                raise PrivateRepoError(
                    f"Repository not accessible (private or not found): {repo_url}"
                ) from exc
            raise CloneFailedError(repo_url=repo_url, reason=str(exc)) from exc

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_clone)
        try:
            future.result(timeout=_CLONE_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            raise CloneTimeoutError(
                repo_url=repo_url,
                timeout_seconds=_CLONE_TIMEOUT_SECONDS,
            )
        except (PrivateRepoError, CloneFailedError):
            raise
        except Exception as exc:
            raise CloneFailedError(repo_url=repo_url, reason=str(exc)) from exc


def _validate_repo_size(clone_dir: str, repo_url: str) -> None:
    total_bytes = sum(
        f.stat().st_size
        for f in Path(clone_dir).rglob("*")
        if f.is_file()
    )
    size_mb = total_bytes / (1024 * 1024)
    if size_mb > MAX_REPO_SIZE_MB:
        raise RepositoryTooLargeError(
            repo_url=repo_url,
            size_mb=size_mb,
            limit_mb=MAX_REPO_SIZE_MB,
        )


def _validate_not_empty(clone_dir: str, repo_url: str) -> None:
    try:
        repo = git.Repo(clone_dir)
        if not repo.head.is_valid():
            raise EmptyRepositoryError(f"Repository has no commits: {repo_url}")
    except (InvalidGitRepositoryError, ValueError) as exc:
        raise EmptyRepositoryError(f"Repository has no commits: {repo_url}") from exc
