"""Knowledge base loader.

Walks the knowledge_base/{architecture,security} directories, chunks each
markdown document, embeds chunks with Gemini gemini-embedding-001, and upserts
them into the configured Qdrant collection.

Point IDs are deterministic UUID5 values derived from chunk_id. Repeated
load() calls with the same content are idempotent (upsert semantics).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from config.constants import EMBEDDING_VECTOR_SIZE, KB_CATEGORY_DOMAIN_MAP
from infrastructure.gemini_client import GeminiClient
from infrastructure.qdrant_client import QdrantClient
from rag.chunker import chunk_document
from shared.exceptions.rag_exceptions import KnowledgeBaseLoadError
from shared.logging.logger import get_logger

logger = get_logger(__name__)

_UUID5_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass
class LoadResult:
    documents_processed: int = 0
    chunks_indexed: int = 0
    chunks_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class KnowledgeBaseLoader:
    """Ingests markdown KB files into Qdrant.

    Stateless — safe to call load() multiple times (idempotent upserts).
    """

    def __init__(self, gemini_client: GeminiClient, qdrant_client: QdrantClient) -> None:
        self._gemini = gemini_client
        self._qdrant = qdrant_client

    def load(
        self,
        kb_root: Path,
        collection_name: str,
        recreate: bool = False,
    ) -> LoadResult:
        """Walk kb_root subdirs and index all qualifying chunks into Qdrant.

        Args:
            kb_root: Root directory containing architecture/ and security/ subdirs.
            collection_name: Qdrant collection to write to.
            recreate: If True, delete and recreate the collection before loading.

        Returns:
            LoadResult with counts and any non-fatal per-document errors.

        Raises:
            KnowledgeBaseLoadError: On fatal Qdrant setup failures.
        """
        result = LoadResult()
        self._ensure_collection(kb_root, collection_name, recreate)

        for category, domain in KB_CATEGORY_DOMAIN_MAP.items():
            category_dir = kb_root / category
            if not category_dir.is_dir():
                logger.warning("KB category dir missing", extra={"path": str(category_dir)})
                continue

            for md_file in sorted(category_dir.glob("*.md")):
                self._load_document(md_file, category, domain, collection_name, result)

        logger.info("KB load complete", extra={
            "docs": result.documents_processed,
            "indexed": result.chunks_indexed,
            "skipped": result.chunks_skipped,
            "errors": len(result.errors),
        })
        return result

    def _ensure_collection(
        self, kb_root: Path, collection_name: str, recreate: bool
    ) -> None:
        try:
            if recreate and self._qdrant.collection_exists(collection_name):
                self._qdrant.create_collection(collection_name, EMBEDDING_VECTOR_SIZE)
                logger.info("Recreated Qdrant collection", extra={"collection": collection_name})
            elif not self._qdrant.collection_exists(collection_name):
                self._qdrant.create_collection(collection_name, EMBEDDING_VECTOR_SIZE)
                logger.info("Created Qdrant collection", extra={"collection": collection_name})
        except Exception as exc:
            raise KnowledgeBaseLoadError(
                str(kb_root), f"Qdrant collection setup failed: {exc}"
            ) from exc

    def _load_document(
        self,
        path: Path,
        category: str,
        domain: str,
        collection_name: str,
        result: LoadResult,
    ) -> None:
        doc_stem = path.stem
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            result.errors.append(f"{path.name}: read error: {exc}")
            return

        chunks = chunk_document(text, category, doc_stem, domain)
        if not chunks:
            result.documents_processed += 1
            logger.debug("No indexable chunks", extra={"file": path.name})
            return

        ids: list[str] = []
        vectors: list[list[float]] = []
        payloads: list[dict] = []

        for chunk in chunks:
            try:
                vector = self._gemini.embed(chunk.content)
            except Exception as exc:
                result.errors.append(f"{chunk.chunk_id}: embed error: {exc}")
                result.chunks_skipped += 1
                continue

            point_id = str(uuid.uuid5(_UUID5_NAMESPACE, chunk.chunk_id))
            ids.append(point_id)
            vectors.append(vector)
            payloads.append({
                "chunk_id": chunk.chunk_id,
                "document_title": chunk.document_title,
                "domain": domain,
                "content_excerpt": chunk.content,
                "char_count": chunk.char_count,
            })

        if ids:
            try:
                self._qdrant.upsert_points(collection_name, ids, vectors, payloads)
                result.chunks_indexed += len(ids)
            except Exception as exc:
                result.errors.append(f"{doc_stem}: upsert error: {exc}")
                result.chunks_skipped += len(ids)

        result.documents_processed += 1
        logger.debug("Document loaded", extra={"file": path.name, "chunks": len(ids)})
