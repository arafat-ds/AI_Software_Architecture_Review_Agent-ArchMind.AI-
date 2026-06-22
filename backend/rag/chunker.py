"""Knowledge base document chunker.

Splits markdown documents into overlapping fixed-window or header-delimited
chunks for Qdrant indexing. Pure text transformation — no I/O, no LLM calls.

Chunk ID format: "{category}/{doc_stem}/{index}"
This matches the RAGChunk.chunk_id format expected by the retrieval service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config.constants import KB_CHUNK_MIN_LENGTH


@dataclass
class ChunkSpec:
    chunk_id: str          # "{category}/{doc_stem}/{index}"
    document_title: str
    domain: str            # RAGDomain value string (e.g. "ARCHITECTURE")
    content: str
    char_count: int


def chunk_document(
    text: str,
    category: str,
    doc_stem: str,
    domain: str,
    min_length: int = KB_CHUNK_MIN_LENGTH,
    max_window: int = 1500,
    overlap: int = 150,
) -> list[ChunkSpec]:
    """Split a markdown document into ChunkSpecs for Qdrant indexing.

    Strategy:
      1. Split on H1/H2/H3 headers — each section becomes a candidate chunk.
      2. If a section exceeds max_window chars, apply fixed-window with overlap.
      3. Filter chunks shorter than min_length after stripping.

    Args:
        text: Full markdown document text.
        category: KB subdirectory name (e.g. "architecture").
        doc_stem: Filename without extension (e.g. "layered_architecture").
        domain: RAGDomain value string for the Qdrant payload.
        min_length: Minimum characters for a chunk to be indexed.
        max_window: Maximum characters per chunk before fixed-window splits.
        overlap: Character overlap between consecutive fixed-window chunks.

    Returns:
        List of ChunkSpec objects ready for embedding and upsert.
    """
    title = _extract_title(text, doc_stem)
    raw_sections = _split_on_headers(text)

    segments: list[str] = []
    for section in raw_sections:
        if len(section) > max_window:
            segments.extend(_fixed_window(section, max_window, overlap))
        else:
            segments.append(section)

    chunks: list[ChunkSpec] = []
    index = 0
    for segment in segments:
        content = segment.strip()
        if len(content) < min_length:
            continue
        chunks.append(ChunkSpec(
            chunk_id=f"{category}/{doc_stem}/{index}",
            document_title=title,
            domain=domain,
            content=content,
            char_count=len(content),
        ))
        index += 1

    return chunks


def _extract_title(text: str, fallback: str) -> str:
    """Extract the first H1 title from markdown, or humanise doc_stem."""
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else fallback.replace("_", " ").title()


def _split_on_headers(text: str) -> list[str]:
    """Split markdown text on H1/H2/H3 header boundaries."""
    parts = re.split(r"(?m)(?=^#{1,3}\s)", text)
    return [p for p in parts if p.strip()]


def _fixed_window(text: str, window: int, overlap: int) -> list[str]:
    """Split a long text section into fixed-size windows with character overlap."""
    segments: list[str] = []
    step = max(1, window - overlap)
    start = 0
    while start < len(text):
        segments.append(text[start:start + window])
        start += step
    return segments
