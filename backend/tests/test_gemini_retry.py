"""Unit tests for Gemini retry logic and retry-after parsing.

Covers:
- _parse_retry_after: plain numbers, s/m/h suffixes, retryDelay key in string
- _is_rate_limit_error: detection from status and message
- generate(): immediate bail when retry_after > 120s
- generate(): short retry_after retries then raises RateLimitError
- generate(): non-429 ClientError re-raised immediately
- _user_facing_reason in architecture_node: RateLimitError formatting
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.gemini_client import (
    GeminiClient,
    _is_rate_limit_error,
    _parse_retry_after,
)
from shared.exceptions.llm_exceptions import RateLimitError

_PATCH_TARGET = "infrastructure.gemini_client.genai.Client"
_PATCH_SLEEP = "infrastructure.gemini_client.time.sleep"

_API_KEY = "test-key"
_MODEL = "gemini-test"
_EMBEDDING_MODEL = "models/gemini-embedding-001"


def _make_client(max_retries: int = 2) -> tuple[GeminiClient, MagicMock]:
    with patch(_PATCH_TARGET) as mock_cls:
        client = GeminiClient(
            api_key=_API_KEY,
            generation_model=_MODEL,
            embedding_model=_EMBEDDING_MODEL,
            temperature=0.0,
            max_output_tokens=1024,
            max_retries=max_retries,
        )
    mock_inner = mock_cls.return_value
    client._client = mock_inner
    return client, mock_inner


def _make_rate_limit_error(retry_delay: str = "5994s") -> "ClientError":
    from google.genai.errors import ClientError  # type: ignore[import]
    return ClientError(429, {
        "status": "RESOURCE_EXHAUSTED",
        "message": "Quota exceeded for model",
        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}],
    })


def _make_permission_error() -> "ClientError":
    from google.genai.errors import ClientError  # type: ignore[import]
    return ClientError(403, {
        "status": "PERMISSION_DENIED",
        "message": "Invalid API key",
    })


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


def test_parse_retry_after_plain_seconds():
    exc = Exception("retry after 30 seconds")
    assert _parse_retry_after(exc) == pytest.approx(30.0)


def test_parse_retry_after_with_s_suffix():
    exc = Exception("retryDelay: 5994s")
    result = _parse_retry_after(exc)
    assert result == pytest.approx(5994.0)


def test_parse_retry_after_with_m_suffix():
    exc = Exception("retryDelay: 90m")
    result = _parse_retry_after(exc)
    assert result == pytest.approx(5400.0)


def test_parse_retry_after_with_h_suffix():
    exc = Exception("retryDelay: 2h")
    result = _parse_retry_after(exc)
    assert result == pytest.approx(7200.0)


def test_parse_retry_after_retrydelay_in_details_dict():
    """Real ClientError stores response_json dict in .details; retryDelay is nested."""
    exc = Exception("quota exceeded")
    exc.details = {  # type: ignore[attr-defined]
        "status": "RESOURCE_EXHAUSTED",
        "details": [{"retryDelay": "5994s"}],
    }
    result = _parse_retry_after(exc)
    assert result == pytest.approx(5994.0)


def test_parse_retry_after_retrydelay_in_details_list():
    """Legacy format: .details is a flat list."""
    exc = Exception("quota exceeded")
    exc.details = [{"retryDelay": "5994s"}]  # type: ignore[attr-defined]
    result = _parse_retry_after(exc)
    assert result == pytest.approx(5994.0)


def test_parse_retry_after_returns_none_when_no_number():
    exc = Exception("something went wrong")
    assert _parse_retry_after(exc) is None


def test_parse_retry_after_handles_quoted_retrydelay_in_string():
    exc = Exception("{'retryDelay': '5994s', 'domain': 'googleapis.com'}")
    result = _parse_retry_after(exc)
    assert result == pytest.approx(5994.0)


# ---------------------------------------------------------------------------
# _is_rate_limit_error
# ---------------------------------------------------------------------------


def test_is_rate_limit_error_from_status():
    exc = MagicMock()
    exc.status = "RESOURCE_EXHAUSTED"
    exc.__str__ = lambda self: "some error"
    assert _is_rate_limit_error(exc) is True


def test_is_rate_limit_error_from_message():
    exc = MagicMock()
    exc.status = ""
    exc.__str__ = lambda self: "429 RESOURCE_EXHAUSTED quota exceeded"
    assert _is_rate_limit_error(exc) is True


def test_is_rate_limit_error_false_for_server_error():
    exc = MagicMock()
    exc.status = "INTERNAL"
    exc.__str__ = lambda self: "500 INTERNAL server error"
    assert _is_rate_limit_error(exc) is False


# ---------------------------------------------------------------------------
# generate(): immediate bail when retry_after > 120s
# ---------------------------------------------------------------------------


def test_generate_raises_rate_limit_immediately_when_retry_after_exceeds_threshold():
    client, mock_inner = _make_client(max_retries=3)
    mock_inner.models.generate_content.side_effect = _make_rate_limit_error("5994s")

    with patch(_PATCH_SLEEP) as mock_sleep:
        with pytest.raises(RateLimitError) as exc_info:
            client.generate(prompt="test")

    mock_sleep.assert_not_called()
    mock_inner.models.generate_content.assert_called_once()
    assert exc_info.value.retry_after_seconds == 5994


def test_generate_rate_limit_immediate_bail_stores_correct_retry_after():
    client, mock_inner = _make_client(max_retries=2)
    mock_inner.models.generate_content.side_effect = _make_rate_limit_error("200s")

    with patch(_PATCH_SLEEP):
        with pytest.raises(RateLimitError) as exc_info:
            client.generate(prompt="test")

    assert exc_info.value.retry_after_seconds == 200


# ---------------------------------------------------------------------------
# generate(): short retry_after retries then raises RateLimitError
# ---------------------------------------------------------------------------


def test_generate_retries_when_retry_after_under_threshold():
    client, mock_inner = _make_client(max_retries=2)
    mock_inner.models.generate_content.side_effect = _make_rate_limit_error("10s")

    with patch(_PATCH_SLEEP) as mock_sleep:
        with pytest.raises(RateLimitError):
            client.generate(prompt="test")

    assert mock_sleep.call_count == 2  # retried max_retries times
    assert mock_inner.models.generate_content.call_count == 3  # initial + 2 retries


def test_generate_uses_retry_after_sleep_duration_when_under_threshold():
    client, mock_inner = _make_client(max_retries=1)
    mock_inner.models.generate_content.side_effect = _make_rate_limit_error("15s")

    with patch(_PATCH_SLEEP) as mock_sleep:
        with pytest.raises(RateLimitError):
            client.generate(prompt="test")

    mock_sleep.assert_called_with(pytest.approx(15.0))


# ---------------------------------------------------------------------------
# generate(): non-429 ClientError re-raised immediately
# ---------------------------------------------------------------------------


def test_generate_reraises_non_rate_limit_client_error():
    from google.genai.errors import ClientError  # type: ignore[import]

    client, mock_inner = _make_client(max_retries=2)
    mock_inner.models.generate_content.side_effect = _make_permission_error()

    with patch(_PATCH_SLEEP) as mock_sleep:
        with pytest.raises(ClientError):
            client.generate(prompt="test")

    mock_sleep.assert_not_called()
    mock_inner.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# _user_facing_reason in architecture_node
# ---------------------------------------------------------------------------


def test_user_facing_reason_rate_limit_with_large_retry_after():
    from core.workflow.nodes.architecture_node import _user_facing_reason

    exc = RateLimitError(model_id="gemini-test", retry_after_seconds=5994)
    reason = _user_facing_reason(exc)
    assert "quota" in reason.lower() or "rate limit" in reason.lower()
    assert "5994" not in reason  # raw seconds not shown directly
    assert "minute" in reason or "hour" in reason


def test_user_facing_reason_rate_limit_with_minute_range():
    from core.workflow.nodes.architecture_node import _user_facing_reason

    exc = RateLimitError(model_id="gemini-test", retry_after_seconds=300)
    reason = _user_facing_reason(exc)
    assert "5 minute" in reason


def test_user_facing_reason_rate_limit_no_retry_after():
    from core.workflow.nodes.architecture_node import _user_facing_reason

    exc = RateLimitError(model_id="gemini-test", retry_after_seconds=None)
    reason = _user_facing_reason(exc)
    assert "rate limit" in reason.lower() or "quota" in reason.lower()
    assert "None" not in reason


def test_user_facing_reason_generic_exception_passes_through():
    from core.workflow.nodes.architecture_node import _user_facing_reason

    exc = ValueError("something broke internally")
    assert _user_facing_reason(exc) == "something broke internally"
