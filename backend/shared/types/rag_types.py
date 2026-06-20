"""Data contracts for the RAG subsystem.

RAGContext is produced by the RAG Retrieval Node and consumed exclusively
by the Recommendation Agent. It represents the result of semantic queries
against the Qdrant knowledge base.

Dependency rule: imports only from shared/types/enums and stdlib/pydantic.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.types.enums import RAGDomain


class RAGQuery(BaseModel):
    """A single semantic query issued to the Qdrant knowledge base.

    One query is generated per source finding. The RAGRetrievalNode
    builds queries from ArchitectureSection weaknesses and SecuritySection
    findings before querying Qdrant.
    """

    query_id: str = Field(
        ...,
        description=(
            "Scoped unique identifier within the RAGContext. "
            "Format: 'Q-NNN' where NNN is zero-padded to three digits (e.g. 'Q-001')."
        ),
    )
    query_text: str = Field(
        ...,
        min_length=10,
        description="Semantic query string sent to the Qdrant similarity search.",
    )
    source_domain: RAGDomain = Field(
        ...,
        description="Knowledge base domain that this query targets.",
    )
    source_finding_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Finding or weakness IDs from ArchitectureSection or SecuritySection "
            "that triggered this query (e.g. ['AW-001', 'SF-002'])."
        ),
    )
    result_chunk_ids: list[str] = Field(
        default_factory=list,
        description=(
            "chunk_id values of all RAGChunks retrieved for this query "
            "(after relevance threshold filtering)."
        ),
    )

    @field_validator("query_id", mode="before")
    @classmethod
    def validate_query_id_format(cls, value: str) -> str:
        """Enforce the Q-NNN scoped identifier format."""
        if not re.match(r"^Q-\d{3}$", str(value)):
            raise ValueError(
                f"query_id '{value}' does not match required format 'Q-NNN' (e.g. 'Q-001')."
            )
        return value


class RAGChunk(BaseModel):
    """A single knowledge base document chunk returned by Qdrant similarity search.

    Only chunks with a relevance_score at or above the configured threshold
    (RAG_RELEVANCE_THRESHOLD in config/constants.py) are included in RAGContext.
    """

    chunk_id: str = Field(
        ...,
        description=(
            "Stable unique identifier derived from the document path and chunk index. "
            "Format: '{category}/{document_name}/{chunk_index}' "
            "(e.g. 'security/owasp_a03_injection/0')."
        ),
    )
    document_title: str = Field(
        ...,
        description="Human-readable title of the source knowledge base document.",
    )
    domain: RAGDomain = Field(
        ...,
        description="Knowledge base domain this chunk belongs to.",
    )
    content_excerpt: str = Field(
        ...,
        min_length=1,
        description="Retrieved text content of this chunk from the knowledge base.",
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Qdrant cosine similarity score for this chunk. "
            "Always >= RAG_RELEVANCE_THRESHOLD (enforced by validator)."
        ),
    )
    query_ids_matched: list[str] = Field(
        default_factory=list,
        description=(
            "query_id values of all RAGQuery instances that retrieved this chunk. "
            "A chunk may be matched by multiple queries (deduplication is applied)."
        ),
    )

    @model_validator(mode="after")
    def validate_relevance_score_meets_threshold(self) -> "RAGChunk":
        """Enforce that relevance_score meets the configured threshold.

        Chunks below the threshold must be filtered before constructing RAGContext.
        """
        from config.constants import RAG_RELEVANCE_THRESHOLD

        if self.relevance_score < RAG_RELEVANCE_THRESHOLD:
            raise ValueError(
                f"RAGChunk '{self.chunk_id}' has relevance_score {self.relevance_score:.4f} "
                f"which is below the configured threshold {RAG_RELEVANCE_THRESHOLD}. "
                "Chunks below threshold must be filtered before building RAGContext."
            )
        return self


class RAGContext(BaseModel):
    """Complete output of the RAG Retrieval Node for a single analysis job.

    Contains all queries issued and all qualifying chunks retrieved. Consumed
    exclusively by the Recommendation Agent to ground LLM synthesis in
    curated knowledge base content.

    Ownership rules:
    - RAGRetrievalNode creates and fully populates this contract.
    - Recommendation Agent reads it. Does not modify it.
    - Not persisted to Supabase; exists only in AnalysisState during workflow.
    """

    context_id: UUID = Field(..., description="Unique identifier for this RAGContext instance.")
    job_id: UUID = Field(..., description="Parent analysis job.")
    queries: list[RAGQuery] = Field(
        default_factory=list,
        description="All semantic queries sent to Qdrant for this analysis job.",
    )
    retrieved_chunks: list[RAGChunk] = Field(
        default_factory=list,
        description=(
            "Deduplicated set of all qualifying chunks returned across all queries. "
            "Only chunks above RAG_RELEVANCE_THRESHOLD are included."
        ),
    )
    total_queries_made: int = Field(
        ..., ge=0, description="Total number of queries sent to Qdrant."
    )
    total_chunks_retrieved: int = Field(
        ...,
        ge=0,
        description="Total chunks returned above the relevance threshold (after deduplication).",
    )
    chunks_filtered_count: int = Field(
        ...,
        ge=0,
        description="Count of chunks discarded because they fell below the relevance threshold.",
    )
    retrieval_timestamp: datetime = Field(
        ..., description="UTC timestamp when the RAG retrieval phase completed."
    )
    relevance_threshold_used: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "The RAG_RELEVANCE_THRESHOLD value from config/constants.py applied "
            "during this retrieval. Recorded for audit and debugging."
        ),
    )
    retrieval_duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Total wall-clock time for the retrieval phase in milliseconds.",
    )
    empty_result_queries: list[str] | None = Field(
        default=None,
        description=(
            "Query texts for which no chunks above the threshold were returned. "
            "None when all queries returned at least one result."
        ),
    )

    @model_validator(mode="after")
    def validate_total_queries_consistent(self) -> "RAGContext":
        """Enforce that total_queries_made matches the length of the queries list."""
        if self.total_queries_made != len(self.queries):
            raise ValueError(
                f"total_queries_made ({self.total_queries_made}) does not match "
                f"len(queries) ({len(self.queries)})."
            )
        return self

    @model_validator(mode="after")
    def validate_total_chunks_consistent(self) -> "RAGContext":
        """Enforce that total_chunks_retrieved matches the length of retrieved_chunks."""
        if self.total_chunks_retrieved != len(self.retrieved_chunks):
            raise ValueError(
                f"total_chunks_retrieved ({self.total_chunks_retrieved}) does not match "
                f"len(retrieved_chunks) ({len(self.retrieved_chunks)})."
            )
        return self

    @model_validator(mode="after")
    def validate_query_ids_unique(self) -> "RAGContext":
        """Enforce uniqueness of query_id values."""
        ids = [q.query_id for q in self.queries]
        if len(ids) != len(set(ids)):
            duplicates = [qid for qid in ids if ids.count(qid) > 1]
            raise ValueError(
                f"Duplicate query_id values detected in RAGContext: {duplicates}"
            )
        return self

    @model_validator(mode="after")
    def validate_chunk_ids_unique(self) -> "RAGContext":
        """Enforce uniqueness of chunk_id values in the deduplicated result set."""
        ids = [c.chunk_id for c in self.retrieved_chunks]
        if len(ids) != len(set(ids)):
            duplicates = [cid for cid in ids if ids.count(cid) > 1]
            raise ValueError(
                f"Duplicate chunk_id values detected in RAGContext retrieved_chunks: {duplicates}"
            )
        return self

    @model_validator(mode="after")
    def validate_chunk_relevance_threshold_consistent(self) -> "RAGContext":
        """Enforce that the recorded threshold matches the constant."""
        from config.constants import RAG_RELEVANCE_THRESHOLD

        if abs(self.relevance_threshold_used - RAG_RELEVANCE_THRESHOLD) > 1e-9:
            raise ValueError(
                f"relevance_threshold_used ({self.relevance_threshold_used}) does not match "
                f"RAG_RELEVANCE_THRESHOLD ({RAG_RELEVANCE_THRESHOLD}) from config/constants.py."
            )
        return self
