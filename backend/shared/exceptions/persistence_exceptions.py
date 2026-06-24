"""Exceptions raised by the persistence subsystem.

Wraps third-party Supabase/PostgREST exceptions so orchestration layers
never import postgrest.exceptions directly. Follows the same pattern as
LLMError (wraps google.api_core) and RAGError (wraps qdrant UnexpectedResponse).

Dependency rule: no imports from other application modules.
"""

from __future__ import annotations


class PersistenceError(Exception):
    """Base exception for all Supabase persistence failures.

    Raised by PersistenceService. PersistenceNode catches this family
    and determines fatal vs non-fatal handling per operation.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PersistenceWriteError(PersistenceError):
    """Raised when a Supabase write operation fails after all retry attempts.

    Covers insert_report() failures only. Treated as fatal by PersistenceNode
    because a report that cannot be saved represents unrecoverable data loss.

    update_job() failures are handled as non-fatal warnings and do not raise
    this exception — they are surfaced as log warnings in PersistenceService.
    """

    def __init__(self, operation: str, reason: str, attempts: int) -> None:
        super().__init__(
            f"Persistence write failed for operation '{operation}' after {attempts} "
            f"attempt(s): {reason}"
        )
        self.operation = operation
        self.reason = reason
        self.attempts = attempts
