"""Gemini API client wrapper.

Wraps google-genai for text generation and text embedding.
Handles retry logic for transient Gemini API errors.

Callers must not import google.genai directly — all Gemini-specific
logic is contained here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import google.genai as genai
import google.genai.types as genai_types
from google.api_core.exceptions import (
    DeadlineExceeded,
    InternalServerError,
    ResourceExhausted,
    ServiceUnavailable,
)

from shared.exceptions.llm_exceptions import (
    EmbeddingError,
    LLMResponseParseError,
    LLMTimeoutError,
    MaxRetriesExceededError,
    RateLimitError,
    TokenLimitExceededError,
)
from shared.logging.logger import get_logger

logger = get_logger(__name__)

_RETRYABLE_EXCEPTIONS = (ResourceExhausted, InternalServerError, ServiceUnavailable)
_BACKOFF_BASE_SECONDS: float = 2.0


@dataclass(frozen=True)
class GenerationResult:
    """Return value of GeminiClient.generate().

    Bundles the generated text with token usage from usage_metadata.
    Token counts are 0 when usage_metadata is absent or its fields are None.
    """

    text: str
    input_tokens: int
    output_tokens: int


class GeminiClient:
    """Thin wrapper around the Google Gemini API.

    Provides text generation and text embedding. Handles retries for
    transient rate-limit and server errors. Does not implement caching,
    prompt construction, or any business logic.
    """

    def __init__(
        self,
        api_key: str,
        generation_model: str,
        embedding_model: str,
        temperature: float,
        max_output_tokens: int,
        max_retries: int,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._generation_model = generation_model
        self._embedding_model = embedding_model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._max_retries = max_retries

    def generate(self, prompt: str, system_prompt: str | None = None) -> GenerationResult:
        """Generate text from a prompt.

        Args:
            prompt: The user-facing prompt text.
            system_prompt: Optional system instruction for the model.

        Returns:
            GenerationResult with generated text and token usage counts.

        Raises:
            TokenLimitExceededError: Input exceeds the model's token limit.
            RateLimitError: Rate limit hit and all retries exhausted.
            LLMTimeoutError: Request timed out.
            MaxRetriesExceededError: All retry attempts failed.
            LLMResponseParseError: Response contained no usable text.
        """
        config = genai_types.GenerateContentConfig(
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
            system_instruction=system_prompt,
        )

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._generation_model,
                    contents=prompt,
                    config=config,
                )
                text = _extract_text(response, self._generation_model)
                usage = response.usage_metadata
                input_tokens = (usage.prompt_token_count or 0) if usage else 0
                output_tokens = (usage.candidates_token_count or 0) if usage else 0
                logger.debug("Gemini generate OK", extra={
                    "model": self._generation_model,
                    "attempt": attempt,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })
                return GenerationResult(
                    text=text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            except ResourceExhausted as exc:
                retry_after = _parse_retry_after(exc)
                if attempt < self._max_retries:
                    logger.warning("Gemini rate limit, retrying", extra={
                        "attempt": attempt + 1,
                        "retry_after": retry_after,
                    })
                    time.sleep(retry_after or _backoff(attempt))
                    last_exc = exc
                else:
                    raise RateLimitError(
                        model_id=self._generation_model,
                        retry_after_seconds=retry_after or 0,
                    ) from exc

            except DeadlineExceeded as exc:
                raise LLMTimeoutError(
                    model_id=self._generation_model,
                    timeout_seconds=0,
                ) from exc

            except _RETRYABLE_EXCEPTIONS as exc:  # type: ignore[misc]
                if attempt < self._max_retries:
                    logger.warning("Gemini transient error, retrying", extra={
                        "attempt": attempt + 1,
                        "error": str(exc),
                    })
                    time.sleep(_backoff(attempt))
                    last_exc = exc
                else:
                    last_exc = exc

        raise MaxRetriesExceededError(
            model_id=self._generation_model,
            attempts=self._max_retries + 1,
            last_error=str(last_exc),
        )

    def probe(self) -> bool:
        """Check Gemini API reachability via a zero-token models.get() call.

        Validates the API key and generation model without generating content.
        Returns True if reachable, False on any failure. Never raises.
        """
        try:
            self._client.models.get(model=self._generation_model)
            logger.debug("Gemini probe OK", extra={"model": self._generation_model})
            return True
        except Exception as exc:
            logger.warning(
                "Gemini probe failed",
                extra={"model": self._generation_model, "error": str(exc)},
            )
            return False

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector.

        Args:
            text: The text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            EmbeddingError: Embedding call failed or returned no vector.
        """
        try:
            result = self._client.models.embed_content(
                model=self._embedding_model,
                contents=text,
            )
            embedding = _extract_embedding(result, self._embedding_model)
            logger.debug("Gemini embed OK", extra={
                "model": self._embedding_model,
                "vector_dim": len(embedding),
            })
            return embedding

        except Exception as exc:
            raise EmbeddingError(
                model_id=self._embedding_model,
                reason=str(exc),
            ) from exc


def _extract_text(response: object, model_id: str) -> str:
    try:
        text = response.text  # type: ignore[union-attr]
        if not text:
            raise LLMResponseParseError(
                model_id=model_id,
                reason="Response contained empty text",
            )
        return text
    except AttributeError as exc:
        raise LLMResponseParseError(
            model_id=model_id,
            reason=f"Response has no text attribute: {exc}",
        ) from exc


def _extract_embedding(result: object, model_id: str) -> list[float]:
    try:
        embedding = result.embeddings[0].values  # type: ignore[union-attr]
        if not embedding:
            raise EmbeddingError(model_id=model_id, reason="Empty embedding vector returned")
        return list(embedding)
    except (AttributeError, IndexError, TypeError) as exc:
        raise EmbeddingError(
            model_id=model_id,
            reason=f"Could not extract embedding from response: {exc}",
        ) from exc


def _backoff(attempt: int) -> float:
    return _BACKOFF_BASE_SECONDS ** (attempt + 1)


def _parse_retry_after(exc: Exception) -> float | None:
    msg = str(exc).lower()
    for part in msg.split():
        try:
            return float(part)
        except ValueError:
            continue
    return None
