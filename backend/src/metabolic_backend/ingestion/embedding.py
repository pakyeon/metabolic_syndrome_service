"""Embedding provider with graceful fallbacks for ingestion and retrieval."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Sequence

try:
    import numpy as np
except Exception:  # pragma: no cover - allows operation without numpy
    np = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


_MODEL_SPECS = {
    "text-embedding-3-small": {"dimensions": 1536, "max_tokens": 8191},
    "text-embedding-3-large": {"dimensions": 3072, "max_tokens": 8191},
    "text-embedding-ada-002": {"dimensions": 1536, "max_tokens": 8191},
}


@dataclass(slots=True)
class EmbeddingConfig:
    """Configuration describing embedding behaviour."""

    model_name: str
    backend: str = "openai"
    embedding_size: int = 1536


class EmbeddingProvider:
    """Generate embeddings using the configured backend with safe fallbacks."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config
        self._client = None
        self._backend = self._config.backend.lower()

        spec = _MODEL_SPECS.get(self._config.model_name, {})
        self._embedding_dim = spec.get("dimensions", self._config.embedding_size)
        self._max_tokens = spec.get("max_tokens")

        self._batch_size = max(1, int(os.getenv("EMBED_BATCH_SIZE", "1000")))
        self._max_retries = max(1, int(os.getenv("EMBED_RETRIES", "3")))
        self._retry_delay = float(os.getenv("EMBED_RETRY_DELAY", "1.0"))

        cache_size = max(0, int(os.getenv("EMBED_CACHE_SIZE", "0")))
        self._cache_capacity = cache_size
        self._cache: OrderedDict[str, List[float]] | None = (
            OrderedDict() if cache_size > 0 else None
        )

        self._initialize_backend()

    # ------------------------------------------------------------------
    def _initialize_backend(self) -> None:
        if self._backend == "openai":
            try:  # pragma: no cover - network dependent
                from openai import OpenAI  # type: ignore

                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError("OPENAI_API_KEY must be set for OpenAI embeddings.")
                self._client = OpenAI(api_key=api_key)
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(f"OpenAI embedding backend unavailable: {exc}") from exc
        elif self._backend == "offline":
            LOGGER.warning("Using offline hash-based embeddings (test mode).")
        else:
            raise ValueError(f"Unsupported embedding backend: {self._config.backend}")

    # ------------------------------------------------------------------
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if self._backend == "openai":
            if self._client is None:
                raise RuntimeError("OpenAI embedding client not initialized")
            return self._embed_openai(list(texts))

        if self._backend == "offline":
            return self._embed_offline(list(texts))

        raise RuntimeError(
            "Embedding backend not initialized. Set EMBEDDING_BACKEND=offline to use deterministic fallback."
        )

    # ------------------------------------------------------------------
    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        prepared: List[str] = []
        blanks: List[bool] = []
        for text in texts:
            normalized, is_blank = self._prepare_text(text)
            prepared.append(normalized)
            blanks.append(is_blank)

        results: List[List[float] | None] = [None] * len(prepared)
        pending_indices: List[int] = []
        pending_payloads: List[str] = []

        for idx, (payload, is_blank) in enumerate(zip(prepared, blanks)):
            if is_blank:
                results[idx] = self._zero_vector()
                continue

            cached = self._cache_get(payload)
            if cached is not None:
                results[idx] = cached
                continue

            pending_indices.append(idx)
            pending_payloads.append(payload)

        for start in range(0, len(pending_payloads), self._batch_size):
            batch_payloads = pending_payloads[start : start + self._batch_size]
            batch_indices = pending_indices[start : start + self._batch_size]

            embeddings = self._request_batch(batch_payloads)

            if embeddings is None:
                embeddings = []
                for payload in batch_payloads:
                    vector = self._request_single(payload)
                    embeddings.append(vector or self._zero_vector())

            for idx, payload, vector in zip(batch_indices, batch_payloads, embeddings):
                vector = vector or self._zero_vector()
                self._cache_set(payload, vector)
                results[idx] = vector

        final_results: List[List[float]] = []
        for value in results:
            final_results.append(value if value is not None else self._zero_vector())

        return final_results

    def _embed_offline(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            payload, is_blank = self._prepare_text(text)
            if is_blank:
                vectors.append(self._zero_vector())
                continue

            cached = self._cache_get(payload)
            if cached is not None:
                vectors.append(cached)
                continue

            vector = self._hash_embedding(payload)
            self._cache_set(payload, vector)
            vectors.append(vector)
        return vectors

    # ------------------------------------------------------------------
    def _request_batch(self, texts: List[str]) -> List[List[float]] | None:
        RateLimitError, APIError = self._openai_error_classes()
        for attempt in range(self._max_retries):
            try:
                response = self._client.embeddings.create(
                    model=self._config.model_name,
                    input=texts,
                )
                return [item.embedding for item in response.data]
            except RateLimitError as exc:  # pragma: no cover - depends on network usage
                if attempt == self._max_retries - 1:
                    LOGGER.warning("Embedding batch failed due to rate limit: %s", exc)
                    return None
                delay = self._retry_delay * (2**attempt)
                LOGGER.warning("Embedding batch rate-limited; retrying in %.2fs", delay)
                time.sleep(delay)
            except APIError as exc:  # pragma: no cover - depends on network usage
                if attempt == self._max_retries - 1:
                    LOGGER.warning("Embedding batch API error: %s", exc)
                    return None
                LOGGER.warning("Embedding batch API error; retrying: %s", exc)
                time.sleep(self._retry_delay)
            except Exception as exc:  # pragma: no cover - defensive fallback
                if attempt == self._max_retries - 1:
                    LOGGER.warning("Embedding batch unexpected error: %s", exc)
                    return None
                LOGGER.warning("Embedding batch unexpected error; retrying: %s", exc)
                time.sleep(self._retry_delay)
        return None

    def _request_single(self, text: str) -> List[float] | None:
        embeddings = self._request_batch([text])
        return embeddings[0] if embeddings else None

    # ------------------------------------------------------------------
    def _prepare_text(self, text: str) -> tuple[str, bool]:
        if text is None:
            return "", True

        stripped = text.strip()
        if not stripped:
            return "", True

        if self._max_tokens:
            max_chars = self._max_tokens * 4
            if len(stripped) > max_chars:
                stripped = stripped[:max_chars]

        return stripped, False

    def _zero_vector(self) -> List[float]:
        return [0.0] * self._embedding_dim

    def _cache_get(self, text: str) -> List[float] | None:
        if self._cache is None:
            return None
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        vector = self._cache.get(key)
        if vector is not None:
            self._cache.move_to_end(key)
        return vector

    def _cache_set(self, text: str, vector: List[float]) -> None:
        if self._cache is None or self._cache_capacity == 0:
            return
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self._cache[key] = vector
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_capacity:
            self._cache.popitem(last=False)

    @staticmethod
    def _openai_error_classes():
        try:  # pragma: no cover - optional dependency
            from openai import APIError, RateLimitError  # type: ignore

            return RateLimitError, APIError
        except Exception:  # pragma: no cover - module unavailable
            return Exception, Exception

    # ------------------------------------------------------------------
    def _hash_embedding(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], byteorder="little", signed=False)

        if np is not None:  # pragma: no branch
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(self._embedding_dim)
            norm = np.linalg.norm(vector)
            if norm == 0:
                return vector.tolist()
            return (vector / norm).tolist()

        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self._embedding_dim)]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def resolve_embedding_config() -> EmbeddingConfig:
    """Construct embedding configuration from environment variables."""

    model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    backend = os.getenv("EMBEDDING_BACKEND", "openai")
    embedding_size = int(os.getenv("EMBEDDING_DIM", "1536"))
    return EmbeddingConfig(model_name=model_name, backend=backend, embedding_size=embedding_size)


__all__ = ["EmbeddingConfig", "EmbeddingProvider", "resolve_embedding_config"]
