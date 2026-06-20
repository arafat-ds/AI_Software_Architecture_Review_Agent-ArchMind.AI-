"""Exceptions raised by the RAG subsystem.

All exceptions inherit from RAGError so callers can catch the entire family.
The RAG subsystem (rag/) is the only layer that raises these exceptions.
Infrastructure-level Qdrant client errors are wrapped into these exceptions
before propagating to the LangGraph RAGRetrievalNode.

Note: EmbeddingError from llm_exceptions.py is the exception for embedding
failures. RAGError subclasses cover Qdrant-specific and retrieval-level failures.

Dependency rule: no imports from other application modules.
"""

from __future__ import annotations


class RAGError(Exception):
    """Base exception for all RAG subsystem failures.

    Raised by rag/ components. The LangGraph RAGRetrievalNode treats most
    RAGError subclasses as non-fatal: the workflow continues with an empty
    RAGContext, and the Recommendation Agent notes reduced context quality.
    QdrantConnectionError is treated as fatal when the service is completely
    unreachable at startup.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class QdrantConnectionError(RAGError):
    """Raised when the Qdrant client cannot establish a connection to the server.

    Checked at application startup via the health endpoint. If Qdrant is
    unavailable at startup, the application should refuse to serve requests.
    """

    def __init__(self, host: str, port: int, reason: str) -> None:
        super().__init__(
            f"Cannot connect to Qdrant at {host}:{port}: {reason}"
        )
        self.host = host
        self.port = port
        self.reason = reason


class CollectionNotFoundError(RAGError):
    """Raised when the configured Qdrant collection does not exist.

    Indicates the knowledge base has not been loaded. The operator must run
    scripts/load_knowledge_base.py before the application can serve analysis requests.
    """

    def __init__(self, collection_name: str) -> None:
        super().__init__(
            f"Qdrant collection '{collection_name}' does not exist. "
            "Run scripts/load_knowledge_base.py to initialise the knowledge base."
        )
        self.collection_name = collection_name


class RetrievalError(RAGError):
    """Raised when a Qdrant similarity search fails at the query level.

    Non-fatal: the RAGRetrievalNode records this in AnalysisState.errors
    and continues with an empty RAGContext for the affected query.
    """

    def __init__(self, query_text: str, reason: str) -> None:
        super().__init__(
            f"Qdrant similarity search failed for query '{query_text[:80]}...': {reason}"
        )
        self.query_text = query_text
        self.reason = reason


class KnowledgeBaseLoadError(RAGError):
    """Raised when the knowledge base document loader encounters a fatal failure.

    Raised by rag/loader/loader.py during application startup when the loader
    cannot read, chunk, or upsert a document into Qdrant.
    """

    def __init__(self, document_path: str, reason: str) -> None:
        super().__init__(
            f"Failed to load knowledge base document '{document_path}': {reason}"
        )
        self.document_path = document_path
        self.reason = reason
