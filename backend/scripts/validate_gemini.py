"""Phase 10 validation: confirm Gemini API key and models are working.

Uses the project's own GeminiClient and settings stack — no standalone client.
Makes two lightweight real API calls:
  1. generate() — one-word prompt, confirms LLM access
  2. embed()    — one-word text, confirms embedding access and vector dimension

Exit code 0 on full success, 1 on any failure.

Usage (from project root):
    PYTHONPATH=backend python backend/scripts/validate_gemini.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.constants import LLM_MAX_RETRIES, LLM_TEMPERATURE
from config.settings import get_settings
from infrastructure.gemini_client import GeminiClient
from shared.logging.logger import get_logger

logger = get_logger(__name__)

_GENERATE_PROMPT = "Reply with exactly one word: OK"
_EMBED_TEXT = "architecture"


def _masked(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def main() -> None:
    print("=" * 60)
    print("ArchMind AI — Gemini API Validation")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Load settings from .env
    # ------------------------------------------------------------------
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"\n[FAIL] settings load error: {exc}")
        print("       Check that .env exists at the project root and GEMINI_API_KEY is set.")
        sys.exit(1)

    print(f"\nKey (masked)     : {_masked(settings.gemini_api_key)}")
    print(f"Generation model : {settings.gemini_model}")
    print(f"Embedding model  : {settings.gemini_embedding_model}")
    print(f"Max output tokens: {settings.llm_max_tokens}")

    # ------------------------------------------------------------------
    # Instantiate GeminiClient (project's own wrapper, not raw google-genai)
    # ------------------------------------------------------------------
    client = GeminiClient(
        api_key=settings.gemini_api_key,
        generation_model=settings.gemini_model,
        embedding_model=settings.gemini_embedding_model,
        temperature=LLM_TEMPERATURE,
        max_output_tokens=settings.llm_max_tokens,
        max_retries=LLM_MAX_RETRIES,
    )

    all_passed = True

    # ------------------------------------------------------------------
    # Test 1: text generation
    # ------------------------------------------------------------------
    print("\n--- Test 1: generate() ---")
    print(f"Prompt: \"{_GENERATE_PROMPT}\"")
    try:
        t0 = time.perf_counter()
        response = client.generate(prompt=_GENERATE_PROMPT)
        latency = time.perf_counter() - t0
        print(f"[PASS] Response  : {response.text.strip()!r}")
        print(f"       Tokens in : {response.input_tokens}")
        print(f"       Tokens out: {response.output_tokens}")
        print(f"       Latency   : {latency:.2f}s")
    except Exception as exc:
        print(f"[FAIL] generate() raised: {type(exc).__name__}: {exc}")
        all_passed = False

    # ------------------------------------------------------------------
    # Test 2: embedding
    # ------------------------------------------------------------------
    print("\n--- Test 2: embed() ---")
    print(f"Input text: \"{_EMBED_TEXT}\"")
    try:
        t0 = time.perf_counter()
        vector = client.embed(text=_EMBED_TEXT)
        latency = time.perf_counter() - t0
        dim = len(vector)
        print(f"[PASS] Vector dim: {dim}")
        print(f"       Latency   : {latency:.2f}s")

        expected_dim = 3072
        if dim != expected_dim:
            print(f"[WARN] Expected dimension {expected_dim}, got {dim}.")
            print(f"       If GEMINI_EMBEDDING_MODEL was changed, Qdrant collection must be rebuilt.")
    except Exception as exc:
        print(f"[FAIL] embed() raised: {type(exc).__name__}: {exc}")
        all_passed = False

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if all_passed:
        print("RESULT: PASS — Gemini API fully operational")
    else:
        print("RESULT: FAIL — see errors above")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
