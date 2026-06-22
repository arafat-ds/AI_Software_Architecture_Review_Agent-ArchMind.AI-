"""Unit tests for rag/chunker.py.

All tests are pure: no I/O, no Gemini calls, no Qdrant, no .env required.
Tests verify chunking logic, chunk_id format, min-length filtering,
header splitting, and fixed-window fallback.
"""

from __future__ import annotations

import pytest

from rag.chunker import ChunkSpec, _extract_title, _fixed_window, _split_on_headers, chunk_document

_CATEGORY = "architecture"
_DOC_STEM = "layered_architecture"
_DOMAIN = "ARCHITECTURE"


# ---------------------------------------------------------------------------
# chunk_id format
# ---------------------------------------------------------------------------


def test_chunk_id_format_matches_spec():
    text = "# Title\n\n" + "x" * 200
    chunks = chunk_document(text, _CATEGORY, _DOC_STEM, _DOMAIN)
    assert len(chunks) > 0
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"{_CATEGORY}/{_DOC_STEM}/{i}"


def test_chunk_id_uses_provided_category_and_stem():
    text = "# Doc\n\n" + "y" * 200
    chunks = chunk_document(text, "security", "owasp_top10", "SECURITY")
    assert chunks[0].chunk_id.startswith("security/owasp_top10/")


# ---------------------------------------------------------------------------
# Domain propagation
# ---------------------------------------------------------------------------


def test_domain_propagated_to_all_chunks():
    text = "# Title\n\n" + "a" * 300 + "\n\n## Section\n\n" + "b" * 300
    chunks = chunk_document(text, _CATEGORY, _DOC_STEM, _DOMAIN)
    assert all(c.domain == _DOMAIN for c in chunks)


# ---------------------------------------------------------------------------
# Min-length filtering
# ---------------------------------------------------------------------------


def test_chunks_below_min_length_filtered():
    short_text = "## Tiny\n\nShort."
    chunks = chunk_document(short_text, _CATEGORY, _DOC_STEM, _DOMAIN, min_length=100)
    assert chunks == []


def test_chunks_above_min_length_included():
    long_text = "## Section\n\n" + "a" * 200
    chunks = chunk_document(long_text, _CATEGORY, _DOC_STEM, _DOMAIN, min_length=50)
    assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# Header splitting
# ---------------------------------------------------------------------------


def test_header_split_produces_multiple_chunks():
    text = (
        "# Title\n\n" + "a" * 200 + "\n\n"
        "## Section A\n\n" + "b" * 200 + "\n\n"
        "## Section B\n\n" + "c" * 200
    )
    chunks = chunk_document(text, _CATEGORY, _DOC_STEM, _DOMAIN, min_length=50)
    assert len(chunks) >= 3


def test_empty_text_returns_empty_list():
    chunks = chunk_document("", _CATEGORY, _DOC_STEM, _DOMAIN)
    assert chunks == []


def test_whitespace_only_text_returns_empty_list():
    chunks = chunk_document("   \n\n  \t  ", _CATEGORY, _DOC_STEM, _DOMAIN)
    assert chunks == []


# ---------------------------------------------------------------------------
# Fixed-window fallback
# ---------------------------------------------------------------------------


def test_fixed_window_triggers_for_long_section():
    long_section = "## Big Section\n\n" + "x" * 5000
    chunks = chunk_document(
        long_section, _CATEGORY, _DOC_STEM, _DOMAIN,
        min_length=50, max_window=500, overlap=50,
    )
    assert len(chunks) > 1


def test_fixed_window_produces_overlap():
    text = "a" * 1000
    windows = _fixed_window(text, window=400, overlap=100)
    assert len(windows) > 1
    # Overlap means windows share a 100-char suffix/prefix
    assert windows[0][-100:] == windows[1][:100]


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------


def test_title_extracted_from_h1():
    text = "# Layered Architecture\n\nSome content here."
    assert _extract_title(text, "fallback") == "Layered Architecture"


def test_title_falls_back_to_humanised_stem():
    text = "No headers here."
    assert _extract_title(text, "layered_architecture") == "Layered Architecture"


# ---------------------------------------------------------------------------
# char_count correctness
# ---------------------------------------------------------------------------


def test_char_count_matches_content_length():
    text = "# Title\n\n" + "z" * 300
    chunks = chunk_document(text, _CATEGORY, _DOC_STEM, _DOMAIN, min_length=50)
    for chunk in chunks:
        assert chunk.char_count == len(chunk.content)
