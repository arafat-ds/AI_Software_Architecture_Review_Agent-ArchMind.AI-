"""CLI script: load the ArchMind AI knowledge base into Qdrant.

Reads markdown files from knowledge_base/{architecture,security}/,
chunks them, embeds each chunk with Gemini text-embedding-004, and
upserts into the configured Qdrant collection.

Usage (from project root):
    PYTHONPATH=backend python backend/scripts/load_knowledge_base.py
    PYTHONPATH=backend python backend/scripts/load_knowledge_base.py --recreate
    PYTHONPATH=backend python backend/scripts/load_knowledge_base.py --kb-root /custom/path

Exit code 0 on success, 1 if any document errors occurred.
Requires a valid .env file with GEMINI_API_KEY, QDRANT_HOST, etc.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure backend/ is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.constants import LLM_MAX_RETRIES, LLM_TEMPERATURE
from config.settings import get_settings
from infrastructure.gemini_client import GeminiClient
from infrastructure.qdrant_client import QdrantClient
from rag.loader import KnowledgeBaseLoader
from shared.logging.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_KB_ROOT = Path(__file__).parent.parent / "knowledge_base"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load ArchMind AI knowledge base into Qdrant."
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=_DEFAULT_KB_ROOT,
        help=f"Knowledge base root directory (default: {_DEFAULT_KB_ROOT})",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Qdrant collection before loading.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings()

    gemini = GeminiClient(
        api_key=settings.gemini_api_key,
        generation_model=settings.gemini_model,
        embedding_model=settings.gemini_embedding_model,
        temperature=LLM_TEMPERATURE,
        max_output_tokens=settings.llm_max_tokens,
        max_retries=LLM_MAX_RETRIES,
    )
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    loader = KnowledgeBaseLoader(gemini_client=gemini, qdrant_client=qdrant)

    logger.info("KB load started", extra={
        "kb_root": str(args.kb_root),
        "collection": settings.qdrant_collection_name,
        "recreate": args.recreate,
    })

    result = loader.load(
        kb_root=args.kb_root,
        collection_name=settings.qdrant_collection_name,
        recreate=args.recreate,
    )

    print(f"Documents processed : {result.documents_processed}")
    print(f"Chunks indexed      : {result.chunks_indexed}")
    print(f"Chunks skipped      : {result.chunks_skipped}")
    print(f"Errors              : {len(result.errors)}")
    for err in result.errors:
        print(f"  ERROR: {err}", file=sys.stderr)

    sys.exit(1 if result.errors else 0)


if __name__ == "__main__":
    main()
