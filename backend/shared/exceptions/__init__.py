"""Shared exceptions package.

All custom exception classes for ArchMind AI are defined in sub-modules and
re-exported from this package. Import from the specific sub-module in production
code for clarity; use this package-level import in tests or error handlers that
need to catch broad exception families.

Dependency rule: shared/exceptions imports nothing from other application modules.
"""

from shared.exceptions.ingestion_exceptions import (
    CloneFailedError,
    CloneTimeoutError,
    EmptyRepositoryError,
    IngestionError,
    InvalidGitHubURLError,
    PrivateRepoError,
    RepositoryTooLargeError,
)
from shared.exceptions.llm_exceptions import (
    EmbeddingError,
    LLMError,
    LLMResponseParseError,
    LLMTimeoutError,
    MaxRetriesExceededError,
    RateLimitError,
    TokenLimitExceededError,
)
from shared.exceptions.parse_exceptions import (
    ParseError,
    PCRAssemblyError,
    TreeSitterInitError,
    UnsupportedLanguageError,
    ZeroParseableFilesError,
)
from shared.exceptions.rag_exceptions import (
    CollectionNotFoundError,
    KnowledgeBaseLoadError,
    QdrantConnectionError,
    RAGError,
    RetrievalError,
)
from shared.exceptions.workflow_exceptions import (
    FatalNodeError,
    JobNotFoundError,
    NodeInputMissingError,
    WorkflowException,
    WorkflowStateError,
)

__all__ = [
    # Ingestion
    "IngestionError",
    "InvalidGitHubURLError",
    "PrivateRepoError",
    "CloneTimeoutError",
    "RepositoryTooLargeError",
    "EmptyRepositoryError",
    "CloneFailedError",
    # Parse
    "ParseError",
    "UnsupportedLanguageError",
    "ZeroParseableFilesError",
    "TreeSitterInitError",
    "PCRAssemblyError",
    # LLM
    "LLMError",
    "MaxRetriesExceededError",
    "TokenLimitExceededError",
    "RateLimitError",
    "LLMTimeoutError",
    "LLMResponseParseError",
    "EmbeddingError",
    # RAG
    "RAGError",
    "QdrantConnectionError",
    "CollectionNotFoundError",
    "RetrievalError",
    "KnowledgeBaseLoadError",
    # Workflow
    "WorkflowException",
    "FatalNodeError",
    "NodeInputMissingError",
    "WorkflowStateError",
    "JobNotFoundError",
]
