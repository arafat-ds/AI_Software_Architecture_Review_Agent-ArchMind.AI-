"""Unit tests for GeminiClient.generate() token count extraction.

Verifies that GenerationResult is returned with correct token counts from
usage_metadata, and that None/missing fields default to 0.

No real Gemini API calls — genai.Client is mocked at the class level.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.gemini_client import GeminiClient, GenerationResult

_PATCH_TARGET = "infrastructure.gemini_client.genai.Client"

_API_KEY = "test-key"
_MODEL = "gemini-test"
_EMBEDDING_MODEL = "models/gemini-embedding-001"


def _make_client() -> tuple[GeminiClient, MagicMock]:
    with patch(_PATCH_TARGET) as mock_genai_client_cls:
        client = GeminiClient(
            api_key=_API_KEY,
            generation_model=_MODEL,
            embedding_model=_EMBEDDING_MODEL,
            temperature=0.0,
            max_output_tokens=1024,
            max_retries=0,
        )
    mock_inner = mock_genai_client_cls.return_value
    client._client = mock_inner
    return client, mock_inner


def _mock_response(text: str, prompt_tokens: int | None, candidates_tokens: int | None) -> MagicMock:
    response = MagicMock()
    response.text = text
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidates_tokens
    response.usage_metadata = usage
    return response


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_generate_returns_generation_result():
    client, mock_inner = _make_client()
    mock_inner.models.generate_content.return_value = _mock_response("OK", 10, 5)
    result = client.generate(prompt="hello")
    assert isinstance(result, GenerationResult)


def test_generate_result_text_matches_response():
    client, mock_inner = _make_client()
    mock_inner.models.generate_content.return_value = _mock_response("hello world", 10, 5)
    result = client.generate(prompt="test")
    assert result.text == "hello world"


# ---------------------------------------------------------------------------
# Token extraction — normal case
# ---------------------------------------------------------------------------


def test_generate_extracts_prompt_token_count():
    client, mock_inner = _make_client()
    mock_inner.models.generate_content.return_value = _mock_response("OK", 42, 7)
    result = client.generate(prompt="test")
    assert result.input_tokens == 42


def test_generate_extracts_candidates_token_count():
    client, mock_inner = _make_client()
    mock_inner.models.generate_content.return_value = _mock_response("OK", 42, 17)
    result = client.generate(prompt="test")
    assert result.output_tokens == 17


# ---------------------------------------------------------------------------
# Token extraction — None/missing fields default to 0
# ---------------------------------------------------------------------------


def test_generate_defaults_input_tokens_to_zero_when_usage_metadata_is_none():
    client, mock_inner = _make_client()
    response = MagicMock()
    response.text = "OK"
    response.usage_metadata = None
    mock_inner.models.generate_content.return_value = response
    result = client.generate(prompt="test")
    assert result.input_tokens == 0


def test_generate_defaults_output_tokens_to_zero_when_usage_metadata_is_none():
    client, mock_inner = _make_client()
    response = MagicMock()
    response.text = "OK"
    response.usage_metadata = None
    mock_inner.models.generate_content.return_value = response
    result = client.generate(prompt="test")
    assert result.output_tokens == 0


def test_generate_defaults_input_tokens_to_zero_when_prompt_token_count_is_none():
    client, mock_inner = _make_client()
    mock_inner.models.generate_content.return_value = _mock_response("OK", None, 5)
    result = client.generate(prompt="test")
    assert result.input_tokens == 0


def test_generate_defaults_output_tokens_to_zero_when_candidates_token_count_is_none():
    client, mock_inner = _make_client()
    mock_inner.models.generate_content.return_value = _mock_response("OK", 10, None)
    result = client.generate(prompt="test")
    assert result.output_tokens == 0


# ---------------------------------------------------------------------------
# Token counts propagate to GenerationMetadata via service layer
# ---------------------------------------------------------------------------


def test_generate_result_is_frozen_dataclass():
    result = GenerationResult(text="hello", input_tokens=10, output_tokens=5)
    with pytest.raises((AttributeError, TypeError)):
        result.input_tokens = 99  # type: ignore[misc]
