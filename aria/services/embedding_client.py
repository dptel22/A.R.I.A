"""Embedding adapter for A.R.I.A. RAG.

Wraps the Gemini embedding model (``gemini-embedding-001``) behind a tiny
protocol so the retrieval stack can be unit-tested with a fake client.

Task types matter for retrieval quality:
* documents are embedded with ``RETRIEVAL_DOCUMENT``
* queries are embedded with ``RETRIEVAL_QUERY``

Reference: https://ai.google.dev/gemini-api/docs/embeddings
"""
from __future__ import annotations

import logging
import os
import time
from typing import Protocol

log: logging.Logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_OUTPUT_DIMENSIONALITY = 768
_BATCH_SIZE = 32
_MAX_ATTEMPTS = 3


class EmbeddingClient(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingUnavailableError(RuntimeError):
    """Raised when no embedding backend is configured (e.g. no API key)."""


class GeminiEmbeddingClient:
    """Gemini embeddings via the google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
        output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
    ):
        from google import genai  # imported lazily so the rest of ARIA runs without it
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._output_dimensionality = output_dimensionality

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=self._types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self._output_dimensionality,
            ),
        )
        embeddings = [e.values for e in response.embeddings]
        if any(v is None for v in embeddings):
            raise RuntimeError("Gemini returned an empty embedding")
        return embeddings  # type: ignore[return-value]

    def _embed_batched(self, texts: list[str], task_type: str) -> list[list[float]]:
        results: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    results.extend(self._embed(batch, task_type))
                    break
                except Exception as exc:  # transient API/network errors
                    if attempt == _MAX_ATTEMPTS:
                        raise
                    wait = 2**attempt
                    log.warning(
                        "Embedding batch failed (attempt %d/%d): %s — retrying in %ds",
                        attempt, _MAX_ATTEMPTS, exc, wait,
                    )
                    time.sleep(wait)
        return results

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed_batched(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batched([text], "RETRIEVAL_QUERY")[0]


def get_embedding_client() -> GeminiEmbeddingClient:
    """Build the configured embedding client or raise EmbeddingUnavailableError."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise EmbeddingUnavailableError("GEMINI_API_KEY is not configured")
    model = os.environ.get("ARIA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return GeminiEmbeddingClient(api_key=api_key, model=model)
