"""Embedding provider with graceful fallbacks for ingestion and retrieval."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
from dataclasses import dataclass
from typing import List, Sequence

try:
    import numpy as np
except Exception:  # pragma: no cover - allows operation without numpy
    np = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


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
            response = self._client.embeddings.create(model=self._config.model_name, input=list(texts))
            return [item.embedding for item in response.data]

        if self._backend == "offline":
            return [self._hash_embedding(text) for text in texts]

        raise RuntimeError(
            "Embedding backend not initialized. Set METABOLIC_EMBEDDING_BACKEND=offline to use deterministic fallback."
        )

    # ------------------------------------------------------------------
    def _hash_embedding(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], byteorder="little", signed=False)

        if np is not None:  # pragma: no branch
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(self._config.embedding_size)
            norm = np.linalg.norm(vector)
            if norm == 0:
                return vector.tolist()
            return (vector / norm).tolist()

        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self._config.embedding_size)]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def resolve_embedding_config() -> EmbeddingConfig:
    """Construct embedding configuration from environment variables."""

    model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    backend = os.getenv("METABOLIC_EMBEDDING_BACKEND", "openai")
    embedding_size = int(os.getenv("METABOLIC_EMBEDDING_DIM", "1536"))
    return EmbeddingConfig(model_name=model_name, backend=backend, embedding_size=embedding_size)


__all__ = ["EmbeddingConfig", "EmbeddingProvider", "resolve_embedding_config"]
