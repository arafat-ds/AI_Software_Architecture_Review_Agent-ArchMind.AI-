"""RAG retrieval service.

Executes semantic queries against the Qdrant knowledge base and assembles
a RAGContext. Domain filtering is mandatory per query — an ARCHITECTURE
query only retrieves chunks with payload field domain="ARCHITECTURE".

Per-query failure model:
  - EmbeddingError: skip the query, append to empty_result_queries, continue.
  - RetrievalError: skip the query, append to empty_result_queries, continue.
  - CollectionNotFoundError: propagates to caller (RAGRetrievalNode).

The RAGRetrievalNode catches all exceptions and returns rag_context=None.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from config.constants import RAG_RELEVANCE_THRESHOLD, RAG_TOP_K
from infrastructure.gemini_client import GeminiClient
from infrastructure.qdrant_client import QdrantClient
from shared.exceptions.llm_exceptions import EmbeddingError
from shared.exceptions.rag_exceptions import RetrievalError
from shared.logging.logger import get_logger
from shared.types.enums import RAGDomain
from shared.types.rag_types import RAGChunk, RAGContext, RAGQuery

logger = get_logger(__name__)


class RAGRetrievalService:
    """Execute typed semantic queries against Qdrant and return a RAGContext.

    Stateless — safe to call run() multiple times.
    """

    def __init__(
        self,
        gemini_client: GeminiClient,
        qdrant_client: QdrantClient,
        collection_name: str,
    ) -> None:
        self._gemini = gemini_client
        self._qdrant = qdrant_client
        self._collection = collection_name

    def run(self, queries: list[RAGQuery], job_id: UUID) -> RAGContext:
        """Execute queries and assemble a RAGContext.

        Domain filtering is applied per query via Qdrant payload filter.
        Chunks are deduplicated by chunk_id; the highest score is kept.
        query.result_chunk_ids is populated in-place after all queries run.

        Args:
            queries: list[RAGQuery] from query_builder.build_rag_queries().
            job_id: Parent analysis job UUID for audit fields.

        Returns:
            RAGContext with all retrieved chunks. retrieved_chunks may be
            empty if no queries exceeded the relevance threshold.

        Raises:
            CollectionNotFoundError: KB collection does not exist in Qdrant.
        """
        t_start = time.monotonic()
        chunk_map: dict[str, RAGChunk] = {}
        empty_result_queries: list[str] = []

        for query in queries:
            self._execute_query(query, chunk_map, empty_result_queries)

        all_chunks = list(chunk_map.values())

        for query in queries:
            matched_ids = [
                chunk.chunk_id for chunk in all_chunks
                if query.query_id in chunk.query_ids_matched
            ]
            query.result_chunk_ids = matched_ids

        duration_ms = int((time.monotonic() - t_start) * 1000)

        logger.info("RAG retrieval complete", extra={
            "job_id": str(job_id),
            "queries": len(queries),
            "chunks": len(all_chunks),
            "empty_queries": len(empty_result_queries),
            "duration_ms": duration_ms,
        })

        return RAGContext(
            context_id=uuid4(),
            job_id=job_id,
            queries=queries,
            retrieved_chunks=all_chunks,
            total_queries_made=len(queries),
            total_chunks_retrieved=len(all_chunks),
            chunks_filtered_count=0,
            retrieval_timestamp=datetime.now(tz=timezone.utc),
            relevance_threshold_used=RAG_RELEVANCE_THRESHOLD,
            retrieval_duration_ms=duration_ms,
            empty_result_queries=empty_result_queries if empty_result_queries else None,
        )

    def _execute_query(
        self,
        query: RAGQuery,
        chunk_map: dict[str, RAGChunk],
        empty_result_queries: list[str],
    ) -> None:
        """Run a single query and merge results into chunk_map.

        CollectionNotFoundError is intentionally not caught here — it
        propagates to run() → RAGRetrievalNode for non-fatal handling.
        """
        try:
            vector = self._gemini.embed(query.query_text)
        except EmbeddingError as exc:
            logger.warning("Embed failed, skipping query", extra={
                "query_id": query.query_id,
                "error": str(exc),
            })
            empty_result_queries.append(query.query_text)
            return

        try:
            hits = self._qdrant.search(
                collection_name=self._collection,
                query_vector=vector,
                top_k=RAG_TOP_K,
                score_threshold=RAG_RELEVANCE_THRESHOLD,
                domain_filter=query.source_domain.value,
            )
        except RetrievalError as exc:
            logger.warning("Search failed, skipping query", extra={
                "query_id": query.query_id,
                "error": str(exc),
            })
            empty_result_queries.append(query.query_text)
            return

        if not hits:
            empty_result_queries.append(query.query_text)
            return

        for hit in hits:
            payload = hit["payload"]
            chunk_id = payload.get("chunk_id", hit["id"])
            score = hit["score"]

            if chunk_id in chunk_map:
                existing = chunk_map[chunk_id]
                if query.query_id not in existing.query_ids_matched:
                    existing.query_ids_matched.append(query.query_id)
                if score > existing.relevance_score:
                    existing.relevance_score = score
            else:
                domain_str = payload.get("domain", query.source_domain.value)
                chunk_map[chunk_id] = RAGChunk(
                    chunk_id=chunk_id,
                    document_title=payload.get("document_title", ""),
                    domain=RAGDomain(domain_str),
                    content_excerpt=payload.get("content_excerpt", ""),
                    relevance_score=score,
                    query_ids_matched=[query.query_id],
                )
