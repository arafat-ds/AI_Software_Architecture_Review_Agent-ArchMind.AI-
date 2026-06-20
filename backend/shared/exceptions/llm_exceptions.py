"""Exceptions raised by the Gemini LLM infrastructure layer.

All exceptions inherit from LLMError so callers can catch the entire family.
The LLM Service (infrastructure/gemini/gemini_client.py) is the only layer
that raises these exceptions; agents receive them via the service call.

Dependency rule: no imports from other application modules.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for all Gemini API failures.

    Raised exclusively by infrastructure/gemini/. Agents must not catch
    LLMError silently — unhandled LLM failures propagate to the LangGraph
    node, which records them in AnalysisState.errors.
    """

    def __init__(self, message: str, model_id: str | None = None) -> None:
        self.model_id = model_id
        super().__init__(message)


class MaxRetriesExceededError(LLMError):
    """Raised when the Gemini API fails on all retry attempts.

    The LLM Service retries transient failures up to LLM_MAX_RETRIES times
    (configured in config/constants.py). This exception is raised when all
    attempts are exhausted.
    """

    def __init__(self, model_id: str, attempts: int, last_error: str) -> None:
        super().__init__(
            f"Gemini API call to model '{model_id}' failed after {attempts} attempts. "
            f"Last error: {last_error}",
            model_id=model_id,
        )
        self.attempts = attempts
        self.last_error = last_error


class TokenLimitExceededError(LLMError):
    """Raised when the prompt exceeds the model's context window or token limit.

    The LLM Service enforces llm_max_tokens from config/settings.py before
    dispatching to the API. This exception is raised either pre-flight or
    when the API returns a token limit error.
    """

    def __init__(self, model_id: str, token_count: int, limit: int) -> None:
        super().__init__(
            f"Prompt for model '{model_id}' has {token_count} tokens which exceeds "
            f"the configured limit of {limit} tokens.",
            model_id=model_id,
        )
        self.token_count = token_count
        self.limit = limit


class RateLimitError(LLMError):
    """Raised when the Gemini API returns a rate limit response (HTTP 429).

    The LLM Service retries with exponential backoff before raising this.
    If retries are exhausted during a rate limit period, MaxRetriesExceededError
    is raised instead.
    """

    def __init__(self, model_id: str, retry_after_seconds: int | None = None) -> None:
        msg = f"Gemini API rate limit exceeded for model '{model_id}'."
        if retry_after_seconds is not None:
            msg += f" Retry after {retry_after_seconds} seconds."
        super().__init__(msg, model_id=model_id)
        self.retry_after_seconds = retry_after_seconds


class LLMTimeoutError(LLMError):
    """Raised when a Gemini API call does not respond within the request timeout.

    Distinct from MaxRetriesExceededError: this is a single-call timeout,
    not an exhausted retry sequence. The LLM Service wraps this and retries.
    """

    def __init__(self, model_id: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Gemini API call to model '{model_id}' timed out after {timeout_seconds}s.",
            model_id=model_id,
        )
        self.timeout_seconds = timeout_seconds


class LLMResponseParseError(LLMError):
    """Raised when the Gemini API response cannot be parsed into the expected structure.

    Indicates the model returned output that does not match the prompt's
    requested output schema. Prompt engineering should be revised when this
    occurs repeatedly.
    """

    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__(
            f"Failed to parse Gemini response from model '{model_id}': {reason}",
            model_id=model_id,
        )
        self.reason = reason


class EmbeddingError(LLMError):
    """Raised when the Gemini embedding API call fails.

    Used by infrastructure/gemini/embedding_client.py and propagated through
    rag/embedder/embedder.py to the RAG subsystem.
    """

    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__(
            f"Gemini embedding call failed for model '{model_id}': {reason}",
            model_id=model_id,
        )
        self.reason = reason
