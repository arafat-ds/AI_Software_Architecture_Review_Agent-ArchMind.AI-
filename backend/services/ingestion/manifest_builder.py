"""Builds a RepositoryManifest from a cloned repository on disk.

Responsibility: filesystem traversal, file classification, language detection.
Does NOT clone the repository — that is IngestionService's responsibility.
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from uuid import UUID, uuid4

from config.constants import (
    MAX_ANALYZABLE_FILES,
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
)
from shared.types.manifest_types import (
    DirectoryEntry,
    FileEntry,
    LanguageStats,
    ManifestType,
    RepositoryManifest,
)

_EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".git", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".nuxt", "target",
    "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache",
})

_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
    ".java": "Java", ".rb": "Ruby", ".rs": "Rust", ".cs": "C#",
    ".cpp": "C++", ".c": "C", ".h": "C", ".kt": "Kotlin",
    ".swift": "Swift", ".scala": "Scala", ".php": "PHP",
}


def build_manifest(
    job_id: UUID,
    repo_url: str,
    repo_name: str,
    clone_path: str,
) -> RepositoryManifest:
    """Traverse the cloned repository and build a RepositoryManifest.

    Args:
        job_id: Parent job UUID.
        repo_url: Original GitHub URL.
        repo_name: Repository name extracted from URL.
        clone_path: Absolute path to the cloned repository on disk.

    Returns:
        Fully populated RepositoryManifest.
    """
    root = Path(clone_path)
    file_entries: list[FileEntry] = []
    dir_entries: list[DirectoryEntry] = []
    language_file_counts: dict[str, int] = defaultdict(int)
    language_byte_counts: dict[str, int] = defaultdict(int)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]

        rel_dir = Path(dirpath).relative_to(root)
        rel_dir_str = str(rel_dir) if str(rel_dir) != "." else ""

        dir_entries.append(
            DirectoryEntry(
                path=rel_dir_str or ".",
                depth=len(rel_dir.parts),
                file_count=len(filenames),
                subdirectory_count=len(dirnames),
            )
        )

        for filename in filenames:
            abs_path = Path(dirpath) / filename
            rel_path = abs_path.relative_to(root)
            rel_path_str = str(rel_path)
            ext = abs_path.suffix.lower()

            try:
                size_bytes = abs_path.stat().st_size
            except OSError:
                continue

            is_supported = ext in SUPPORTED_EXTENSIONS
            exceeds_size = size_bytes > MAX_FILE_SIZE_BYTES
            is_skipped = not is_supported or exceeds_size
            skip_reason: str | None = None
            if not is_supported:
                skip_reason = f"Unsupported extension '{ext}'"
            elif exceeds_size:
                skip_reason = f"File size {size_bytes} exceeds limit {MAX_FILE_SIZE_BYTES}"

            language = _EXTENSION_TO_LANGUAGE.get(ext, "Unknown") if is_supported else "Unknown"
            is_test = _is_test_file(rel_path_str)

            entry = FileEntry(
                path=rel_path_str,
                language=language if is_supported else "Unknown",
                size_bytes=size_bytes,
                is_test_file=is_test,
                is_skipped=is_skipped,
                skip_reason=skip_reason,
            )
            file_entries.append(entry)

            if not is_skipped:
                language_file_counts[language] += 1
                language_byte_counts[language] += size_bytes

    analyzable = [f for f in file_entries if not f.is_skipped]

    if len(analyzable) > MAX_ANALYZABLE_FILES:
        file_entries, analyzable, _ = _trim_to_limit(file_entries)

    languages = _build_language_stats(language_file_counts, language_byte_counts)
    primary_language = _pick_primary_language(language_file_counts)
    default_branch = _detect_default_branch(root)

    return RepositoryManifest(
        manifest_id=uuid4(),
        job_id=job_id,
        repo_url=repo_url,
        repo_name=repo_name,
        default_branch=default_branch,
        primary_language=primary_language,
        languages=languages,
        file_list=file_entries,
        directory_tree=dir_entries,
        total_file_count=len(file_entries),
        analyzable_file_count=len([f for f in file_entries if not f.is_skipped]),
        skipped_file_count=len([f for f in file_entries if f.is_skipped]),
        clone_timestamp=__import__("datetime").datetime.now(
            tz=__import__("datetime").timezone.utc
        ),
        temp_clone_path=clone_path,
    )


def _is_test_file(path: str) -> bool:
    lower = path.lower()
    parts = Path(lower).parts
    return (
        any(p in ("test", "tests", "spec", "specs", "__tests__") for p in parts)
        or Path(lower).name.startswith("test_")
        or Path(lower).stem.endswith("_test")
        or Path(lower).stem.endswith(".test")
        or Path(lower).stem.endswith(".spec")
    )


def _classify_manifest_type(filename: str) -> ManifestType:
    lower = filename.lower()
    if lower in ("package.json", "requirements.txt", "pyproject.toml",
                 "go.mod", "cargo.toml", "pom.xml", "build.gradle"):
        return ManifestType.DEPENDENCY
    if lower in ("dockerfile", "docker-compose.yml", "docker-compose.yaml"):
        return ManifestType.CONTAINER
    if lower in (".github", "ci.yml", ".travis.yml", "jenkinsfile"):
        return ManifestType.CI
    if lower in ("readme.md", "readme.rst", "readme.txt", "license"):
        return ManifestType.DOCUMENTATION
    return ManifestType.SOURCE


def _trim_to_limit(
    all_files: list[FileEntry],
) -> tuple[list[FileEntry], list[FileEntry], list[FileEntry]]:
    """Keep up to MAX_ANALYZABLE_FILES analyzable files; mark excess as skipped."""
    analyzable = [f for f in all_files if not f.is_skipped]
    skipped = [f for f in all_files if f.is_skipped]

    kept = analyzable[:MAX_ANALYZABLE_FILES]
    excess = analyzable[MAX_ANALYZABLE_FILES:]

    trimmed_excess = []
    for f in excess:
        trimmed_excess.append(FileEntry(
            path=f.path,
            language=f.language,
            size_bytes=f.size_bytes,
            is_test_file=f.is_test_file,
            is_skipped=True,
            skip_reason=f"Exceeds MAX_ANALYZABLE_FILES limit ({MAX_ANALYZABLE_FILES})",
        ))

    combined = kept + trimmed_excess + skipped
    return combined, kept, trimmed_excess + skipped


def _build_language_stats(
    file_counts: dict[str, int],
    byte_counts: dict[str, int],
) -> dict[str, LanguageStats]:
    total_files = sum(file_counts.values()) or 1
    return {
        lang: LanguageStats(
            language=lang,
            file_count=count,
            estimated_line_count=max(0, byte_counts[lang] // 40),
            percentage_of_codebase=round(count / total_files, 4),
        )
        for lang, count in file_counts.items()
    }


def _pick_primary_language(file_counts: dict[str, int]) -> str:
    if not file_counts:
        return "Unknown"
    return max(file_counts, key=lambda lang: file_counts[lang])


def _detect_default_branch(root: Path) -> str:
    head_file = root / ".git" / "HEAD"
    if head_file.exists():
        content = head_file.read_text(encoding="utf-8").strip()
        if content.startswith("ref: refs/heads/"):
            return content.removeprefix("ref: refs/heads/")
    return "main"
