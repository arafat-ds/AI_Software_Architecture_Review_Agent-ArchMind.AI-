"""Exceptions raised by the Code Parser service.

All exceptions inherit from ParseError so callers can catch the entire
family while still handling specific sub-cases when needed.

Dependency rule: no imports from other application modules.
"""

from __future__ import annotations


class ParseError(Exception):
    """Base exception for all code parsing failures.

    Raised by services/parser/ components. The LangGraph ParseNode treats
    ZeroParseableFilesError as a fatal error. Individual file parse failures
    are non-fatal and are recorded in ParseMetadata.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnsupportedLanguageError(ParseError):
    """Raised when a file's language has no Tree-sitter grammar available.

    Non-fatal at the file level: the file is added to the skipped list in
    ParseMetadata and the workflow continues with remaining files.
    """

    def __init__(self, file_path: str, language: str) -> None:
        super().__init__(
            f"No Tree-sitter grammar available for language '{language}' "
            f"in file '{file_path}'. File will be skipped."
        )
        self.file_path = file_path
        self.language = language


class ZeroParseableFilesError(ParseError):
    """Raised when no files could be successfully parsed across the entire repository.

    Fatal workflow error. The ArchitectureSection and SecuritySection cannot
    be produced without at least one successfully parsed file.
    """

    def __init__(self, files_attempted: int, files_skipped: int) -> None:
        super().__init__(
            f"No files were successfully parsed. "
            f"Attempted: {files_attempted}, Skipped: {files_skipped}. "
            "Ensure the repository contains supported language files."
        )
        self.files_attempted = files_attempted
        self.files_skipped = files_skipped


class TreeSitterInitError(ParseError):
    """Raised when Tree-sitter fails to initialise a language grammar.

    Typically indicates a missing grammar library or misconfigured
    Tree-sitter language binding.
    """

    def __init__(self, language: str, reason: str) -> None:
        super().__init__(
            f"Failed to initialise Tree-sitter grammar for '{language}': {reason}"
        )
        self.language = language
        self.reason = reason


class PCRAssemblyError(ParseError):
    """Raised when the ParsedCodeRepresentation cannot be assembled from file analyses.

    Indicates a programming error in the PCR assembly logic, not a user input error.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Failed to assemble ParsedCodeRepresentation: {reason}"
        )
        self.reason = reason
