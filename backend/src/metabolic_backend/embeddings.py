"""Simple OpenAI embeddings wrapper aligned with LangChain usage."""

from __future__ import annotations

import os
from typing import List

from langchain_openai import OpenAIEmbeddings as _LangChainOpenAIEmbeddings


class OpenAIEmbeddings:
    """OpenAI embedding client backed by LangChain's implementation."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable must be set to use OpenAI embeddings."
            )

        self._client = _LangChainOpenAIEmbeddings(model=model, openai_api_key=self.api_key)

    # ------------------------------------------------------------------
    def embed_text(self, text: str) -> List[float]:
        return self._client.embed_query(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self._client.embed_documents(texts)

    # ------------------------------------------------------------------
    def get_langchain_embeddings(self) -> _LangChainOpenAIEmbeddings:
        return self._client


__all__ = ["OpenAIEmbeddings"]
