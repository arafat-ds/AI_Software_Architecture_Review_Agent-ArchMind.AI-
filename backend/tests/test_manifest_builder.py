"""Regression tests for services/ingestion/manifest_builder.py.

These tests use a real temporary directory (no mocks) to verify that
build_manifest() constructs DirectoryEntry, LanguageStats, and FileEntry
instances that satisfy their Pydantic model contracts.

Motivation: the original builder passed wrong field names to all three models
(children= instead of depth/file_count/subdirectory_count for DirectoryEntry;
byte_count=/percentage= instead of estimated_line_count/percentage_of_codebase
for LanguageStats; manifest_type= which doesn't exist on FileEntry). These
mismatches were pre-existing from the initial commit and went undetected
because all other tests mock IngestionService.run() directly.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from services.ingestion.manifest_builder import build_manifest
from shared.types.manifest_types import DirectoryEntry, FileEntry, LanguageStats, RepositoryManifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repository tree for testing."""
    # Simulate .git/HEAD so _detect_default_branch works
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    # src/ with two Python files
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main(): pass\n" * 10, encoding="utf-8")
    (src / "utils.py").write_text("def helper(): return 1\n" * 5, encoding="utf-8")

    # tests/ subdirectory
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test_it(): assert True\n", encoding="utf-8")

    # Unsupported files at root
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Core regression: Pydantic validation must not raise
# ---------------------------------------------------------------------------

def test_build_manifest_returns_valid_model(tmp_path):
    """build_manifest() must return a fully valid RepositoryManifest without
    any Pydantic ValidationError. This is the primary regression guard for the
    DirectoryEntry/LanguageStats/FileEntry field-name mismatches."""
    repo = _make_repo(tmp_path)
    job_id = uuid.uuid4()

    manifest = build_manifest(
        job_id=job_id,
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    assert isinstance(manifest, RepositoryManifest)


# ---------------------------------------------------------------------------
# DirectoryEntry schema
# ---------------------------------------------------------------------------

def test_directory_entries_have_required_fields(tmp_path):
    """Every DirectoryEntry must carry depth, file_count, subdirectory_count."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    for entry in manifest.directory_tree:
        assert isinstance(entry, DirectoryEntry)
        assert isinstance(entry.depth, int) and entry.depth >= 0
        assert isinstance(entry.file_count, int) and entry.file_count >= 0
        assert isinstance(entry.subdirectory_count, int) and entry.subdirectory_count >= 0


def test_root_directory_entry_depth_is_zero(tmp_path):
    """Root directory must have depth == 0."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    root_entry = next(e for e in manifest.directory_tree if e.path == ".")
    assert root_entry.depth == 0


def test_subdirectory_entry_depth_is_one(tmp_path):
    """Direct children of root must have depth == 1."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    src_entry = next(e for e in manifest.directory_tree if e.path in ("src", "tests"))
    assert src_entry.depth == 1


def test_root_file_count_matches_actual_files(tmp_path):
    """Root DirectoryEntry.file_count must equal files directly in root."""
    repo = _make_repo(tmp_path)
    # Root has README.md and requirements.txt (2 direct files)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    root_entry = next(e for e in manifest.directory_tree if e.path == ".")
    # .git is excluded, so subdirs = [src, tests] = 2
    assert root_entry.file_count == 2
    assert root_entry.subdirectory_count == 2


# ---------------------------------------------------------------------------
# LanguageStats schema
# ---------------------------------------------------------------------------

def test_language_stats_have_required_fields(tmp_path):
    """Every LanguageStats entry must carry language, estimated_line_count,
    percentage_of_codebase in 0.0–1.0."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    assert len(manifest.languages) > 0
    for lang_name, stats in manifest.languages.items():
        assert isinstance(stats, LanguageStats)
        assert stats.language == lang_name
        assert isinstance(stats.estimated_line_count, int) and stats.estimated_line_count >= 0
        assert 0.0 <= stats.percentage_of_codebase <= 1.0


def test_python_language_detected(tmp_path):
    """Python must be detected as primary language for a Python repo."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    assert manifest.primary_language == "Python"
    assert "Python" in manifest.languages


# ---------------------------------------------------------------------------
# FileEntry schema
# ---------------------------------------------------------------------------

def test_file_entries_have_no_manifest_type_attribute(tmp_path):
    """FileEntry must not expose a manifest_type attribute."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    for entry in manifest.file_list:
        assert isinstance(entry, FileEntry)
        assert not hasattr(entry, "manifest_type")


def test_test_files_flagged_correctly(tmp_path):
    """Files under tests/ must be marked is_test_file=True."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    test_entries = [f for f in manifest.file_list if "test" in f.path.lower()]
    assert len(test_entries) > 0
    for entry in test_entries:
        assert entry.is_test_file is True


# ---------------------------------------------------------------------------
# Counts integrity
# ---------------------------------------------------------------------------

def test_file_counts_are_consistent(tmp_path):
    """analyzable_file_count + skipped_file_count == total_file_count."""
    repo = _make_repo(tmp_path)
    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        repo_name="repo",
        clone_path=str(repo),
    )

    assert manifest.analyzable_file_count + manifest.skipped_file_count == manifest.total_file_count


# ---------------------------------------------------------------------------
# Grammar-supported-extensions filtering (Flutter / no-grammar language fix)
# ---------------------------------------------------------------------------

def _make_git(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir(exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")


def test_dart_only_repo_all_files_skipped(tmp_path):
    """A repo with only .dart files must have zero analyzable files.

    .dart is not in SUPPORTED_EXTENSIONS at all, so files are skipped as
    "Unsupported extension" — they never even reach the grammar check.
    """
    _make_git(tmp_path)
    (tmp_path / "main.dart").write_text("void main() {}\n", encoding="utf-8")
    (tmp_path / "widget.dart").write_text("class MyWidget {}\n", encoding="utf-8")

    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/flutter_app",
        repo_name="flutter_app",
        clone_path=str(tmp_path),
    )

    assert manifest.analyzable_file_count == 0
    dart_entries = [f for f in manifest.file_list if f.path.endswith(".dart")]
    assert len(dart_entries) == 2
    for entry in dart_entries:
        assert entry.is_skipped is True
        assert entry.skip_reason is not None
        assert "Unsupported extension" in entry.skip_reason


def test_python_repo_files_are_analyzable(tmp_path):
    """A repo with .py files must classify them as analyzable (not skipped)."""
    _make_git(tmp_path)
    (tmp_path / "app.py").write_text("def run(): pass\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper(): return 1\n", encoding="utf-8")

    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/py_app",
        repo_name="py_app",
        clone_path=str(tmp_path),
    )

    assert manifest.analyzable_file_count == 2
    py_entries = [f for f in manifest.file_list if f.path.endswith(".py")]
    for entry in py_entries:
        assert entry.is_skipped is False
        assert entry.skip_reason is None


def test_mixed_dart_python_repo_only_python_analyzable(tmp_path):
    """In a mixed Dart+Python repo, only .py files must be analyzable."""
    _make_git(tmp_path)
    (tmp_path / "main.dart").write_text("void main() {}\n", encoding="utf-8")
    (tmp_path / "helper.dart").write_text("class Foo {}\n", encoding="utf-8")
    (tmp_path / "script.py").write_text("def run(): pass\n", encoding="utf-8")

    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/mixed_app",
        repo_name="mixed_app",
        clone_path=str(tmp_path),
    )

    assert manifest.analyzable_file_count == 1
    py_entry = next(f for f in manifest.file_list if f.path.endswith(".py"))
    assert py_entry.is_skipped is False

    dart_entries = [f for f in manifest.file_list if f.path.endswith(".dart")]
    for entry in dart_entries:
        assert entry.is_skipped is True
        assert entry.skip_reason is not None
        assert "Unsupported extension" in entry.skip_reason


def test_cpp_files_skipped_no_grammar(tmp_path):
    """C++ files (.cpp) are in SUPPORTED_EXTENSIONS but have no Tree-sitter grammar.

    They must be skipped with 'No parser available' — not counted as analyzable.
    This mirrors the Flutter platform-layer files that caused the FatalNodeError.
    """
    _make_git(tmp_path)
    (tmp_path / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    (tmp_path / "util.cpp").write_text("void helper() {}\n", encoding="utf-8")

    manifest = build_manifest(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/cpp_lib",
        repo_name="cpp_lib",
        clone_path=str(tmp_path),
    )

    assert manifest.analyzable_file_count == 0
    cpp_entries = [f for f in manifest.file_list if f.path.endswith(".cpp")]
    assert len(cpp_entries) == 2
    for entry in cpp_entries:
        assert entry.is_skipped is True
        assert entry.skip_reason is not None
        assert "No parser available" in entry.skip_reason
