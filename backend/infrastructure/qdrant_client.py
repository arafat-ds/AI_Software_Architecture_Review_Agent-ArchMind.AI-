"""Qdrant vector store client wrapper.

Wraps qdrant-client for collection management, vector upsert, and similarity
search. Callers receive plain Python dicts and lists — no Qdrant library types
leak past this module boundary.

Callers must not import qdrant_client directly — all Qdrant-specific logic
is contained here.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient as _QdrantLibClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

from shared.exceptions.rag_exceptions import (
    CollectionNotFoundError,
    QdrantConnectionError,
    RetrievalError,
)
from shared.logging.logger import get_logger

logger = get_logger(__name__)


class QdrantClient:
    """Thin wrapper around the Qdrant vector store.

    All methods accept and return plain Python types. Qdrant-specific
    models (PointStruct, ScoredPoint, etc.) are used internally only.
    """

    def __init__(self, host: str, port: int) -> None:
        try:
            self._client = _QdrantLibClient(host=host, port=port)
        except Exception as exc:
            raise QdrantConnectionError(host=host, port=port, reason=str(exc)) from exc
        self._host = host
        self._port = port

    def collection_exists(self, collection_name: str) -> bool:
        """Return True if the named collection exists in Qdrant."""
        try:
            return self._client.collection_exists(collection_name)
        except Exception as exc:
            raise QdrantConnectionError(
                host=self._host, port=self._port, reason=str(exc)
            ) from exc

    def create_collection(self, collection_name: str, vector_size: int) -> None:
        """Create a collection with cosine-similarity vectors.

        Args:
            collection_name: Name of the collection to create.
            vector_size: Dimensionality of the embedding vectors.
        """
        try:
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("Qdrant collection created", extra={
                "collection": collection_name,
                "vector_size": vector_size,
            })
        except Exception as exc:
            raise QdrantConnectionError(
                host=self._host, port=self._port, reason=str(exc)
            ) from exc

    def upsert_points(
        self,
        collection_name: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        """Upsert vectors with payloads into a collection.

        Args:
            collection_name: Target collection name.
            ids: String UUIDs for each point (one per vector).
            vectors: Embedding vectors, one per point.
            payloads: Metadata dicts, one per point.

        Raises:
            CollectionNotFoundError: Collection does not exist.
            QdrantConnectionError: Qdrant is unreachable.
        """
        if len(ids) != len(vectors) or len(ids) != len(payloads):
            raise ValueError(
                f"ids ({len(ids)}), vectors ({len(vectors)}), and payloads "
                f"({len(payloads)}) must have equal length."
            )

        points = [
            PointStruct(id=point_id, vector=vector, payload=payload)
            for point_id, vector, payload in zip(ids, vectors, payloads)
        ]

        try:
            self._client.upsert(collection_name=collection_name, points=points)
            logger.info("Qdrant upsert OK", extra={
                "collection": collection_name,
                "count": len(points),
            })
        except UnexpectedResponse as exc:
            if "not found" in str(exc).lower():
                raise CollectionNotFoundError(collection_name=collection_name) from exc
            raise QdrantConnectionError(
                host=self._host, port=self._port, reason=str(exc)
            ) from exc
        except Exception as exc:
            raise QdrantConnectionError(
                host=self._host, port=self._port, reason=str(exc)
            ) from exc

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, Any]]:
        """Search for the most similar vectors above a relevance threshold.

        Args:
            collection_name: Collection to search.
            query_vector: The query embedding vector.
            top_k: Maximum number of results to return.
            score_threshold: Minimum cosine similarity score (0.0–1.0).

        Returns:
            List of dicts with keys: ``id``, ``score``, ``payload``.

        Raises:
            CollectionNotFoundError: Collection does not exist.
            RetrievalError: Search failed for any other reason.
        """
        try:
            results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
            logger.debug("Qdrant search OK", extra={
                "collection": collection_name,
                "hits": len(results),
                "top_k": top_k,
            })
            return [
                {"id": str(hit.id), "score": hit.score, "payload": hit.payload or {}}
                for hit in results
            ]
        except UnexpectedResponse as exc:
            if "not found" in str(exc).lower():
                raise CollectionNotFoundError(collection_name=collection_name) from exc
            raise RetrievalError(
                query_text="<vector query>", reason=str(exc)
            ) from exc
        except Exception as exc:
            raise RetrievalError(
                query_text="<vector query>", reason=str(exc)
            ) from exc
