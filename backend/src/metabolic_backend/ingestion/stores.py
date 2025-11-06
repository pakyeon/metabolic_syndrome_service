"""Persistence helpers for the Chroma vector store and Graphiti."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence

from graphiti_core import Graphiti  # type: ignore
from graphiti_core.nodes import EpisodeType  # type: ignore

from langchain_chroma import Chroma  # type: ignore

from langchain_core.embeddings import Embeddings

from .models import Chunk

LOGGER = logging.getLogger(__name__)


class _EmbeddingAdapter(Embeddings):
    """Bridge OpenAIEmbeddings to LangChain's Embeddings protocol."""

    def __init__(self, client) -> None:
        self._client = client

    def embed_documents(self, texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        return self._client.embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:  # type: ignore[override]
        return self._client.embed_text(text)


class ChromaVectorStore:
    """Persist chunk embeddings into a local Chroma collection."""

    def __init__(
        self,
        *,
        persist_directory: str | Path,
        collection_name: str,
        embedding_client,
    ) -> None:
        if Chroma is None:  # pragma: no cover - runtime guard
            raise RuntimeError("langchain-chroma must be installed to use the Chroma vector store.")

        self._persist_directory = Path(persist_directory)
        self._collection_name = collection_name
        self._embedding_client = embedding_client
        self._embedding_adapter = _EmbeddingAdapter(embedding_client)
        self._vectorstore: Chroma | None = None

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Completely remove the persisted collection."""

        if self._persist_directory.exists():
            shutil.rmtree(self._persist_directory)
        self._vectorstore = None

    # ------------------------------------------------------------------
    def upsert_chunks(self, chunks: Sequence[Chunk], *, force_rebuild: bool = False) -> int:
        """Upsert the provided chunks into Chroma."""

        if not chunks:
            return 0

        if force_rebuild:
            LOGGER.info("Force rebuild requested; resetting Chroma collection")
            self.reset()

        vectorstore = self._ensure_vectorstore()
        ids, texts, metadatas, embeddings = self._prepare_payload(chunks)

        vectorstore._collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        vectorstore.persist()

        return len(ids)

    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, object]:
        """Return lightweight stats about the persisted collection."""

        vectorstore = self._ensure_vectorstore()
        count = vectorstore._collection.count()

        total_size = 0
        if self._persist_directory.exists():
            for path in self._persist_directory.rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size

        return {
            "collection": self._collection_name,
            "persist_directory": str(self._persist_directory),
            "documents": count,
            "size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0.0,
        }

    # ------------------------------------------------------------------
    def load(self) -> "Chroma":
        """Return a LangChain Chroma vector store instance."""

        return self._ensure_vectorstore()

    # ------------------------------------------------------------------
    def _ensure_vectorstore(self) -> "Chroma":
        if self._vectorstore is None:
            self._persist_directory.mkdir(parents=True, exist_ok=True)
            self._vectorstore = Chroma(
                collection_name=self._collection_name,
                embedding_function=self._embedding_adapter,
                persist_directory=str(self._persist_directory),
            )
        return self._vectorstore

    # ------------------------------------------------------------------
    def _prepare_payload(self, chunks: Sequence[Chunk]):
        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[Dict[str, object]] = []
        embeddings: List[List[float]] = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            texts.append(chunk.text)
            metadatas.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "section_path": list(chunk.section_path),
                    "source_path": chunk.source_path,
                    "token_count": chunk.token_count,
                    "chunk_metadata": dict(chunk.metadata),
                }
            )

            if chunk.embedding is None:
                chunk.embedding = self._embedding_client.embed_text(chunk.text)
            embeddings.append(chunk.embedding)

        return ids, texts, metadatas, embeddings


_GROUP_SANITIZE_PATTERN = re.compile(r"[^0-9A-Za-z_-]+")


def _sanitize_group_id(value: str, fallback: str = "document") -> str:
    sanitized = _GROUP_SANITIZE_PATTERN.sub("-", value or "")
    sanitized = sanitized.strip("-")
    return sanitized or fallback


class GraphitiWriter:
    """Persist chunk content into Graphiti knowledge graph."""

    def __init__(
        self, uri: str | None, user: str | None, password: str | None, *, llm_client=None
    ) -> None:
        self._enabled = bool(
            uri and user and password and Graphiti is not None and EpisodeType is not None
        )
        self._uri = uri
        self._user = user
        self._password = password
        self._llm_client = llm_client or self._create_default_llm_client()

    def _create_default_llm_client(self):
        """Create default LLM client for Graphiti (OpenAI with structured output support)."""
        try:
            from openai import AsyncOpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                LOGGER.info("Initializing Graphiti with OpenAI LLM client")
                return AsyncOpenAI(api_key=api_key)
        except Exception as exc:
            LOGGER.debug("OpenAI client unavailable for Graphiti (%s)", exc)

    def upsert_chunks(self, chunks: Sequence[Chunk]) -> int:
        if not self._enabled or not chunks:
            return 0

        async def _ingest() -> int:
            # Initialize Graphiti with LLM client for structured output
            if self._llm_client is not None:
                client = Graphiti(
                    self._uri, self._user, self._password, llm_client=self._llm_client
                )  # type: ignore[call-arg]
            else:
                client = Graphiti(self._uri, self._user, self._password)  # type: ignore[call-arg]
            processed = 0
            try:
                await client.build_indices_and_constraints()
                for chunk in chunks:
                    heading = (
                        chunk.metadata.get("heading", "")
                        if isinstance(chunk.metadata, dict)
                        else ""
                    )
                    source_description = heading or "document chunk"
                    try:
                        group_id = _sanitize_group_id(chunk.document_id)
                        await client.add_episode(
                            name=chunk.chunk_id,
                            episode_body=chunk.text,
                            source=EpisodeType.text,  # type: ignore[attr-defined]
                            source_description=source_description,
                            reference_time=datetime.now(timezone.utc),
                            group_id=group_id,
                        )
                        processed += 1
                    except Exception as exc:  # pragma: no cover - depends on external service
                        LOGGER.warning(
                            "Graphiti add_episode failed for %s (%s)", chunk.chunk_id, exc
                        )
                return processed
            finally:
                await client.close()

        try:
            return asyncio.run(_ingest())
        except RuntimeError as exc:  # Event loop already running
            # Try nest_asyncio to allow nested event loops
            try:
                import nest_asyncio

                nest_asyncio.apply()
                return asyncio.run(_ingest())
            except Exception as nested_exc:
                LOGGER.warning(
                    "Asyncio loop conflict: %s. Install nest_asyncio or run ingestion outside async context. "
                    "Skipping Graphiti ingestion.",
                    exc,
                )
                return 0


__all__ = ["VectorStoreWriter", "GraphitiWriter"]
