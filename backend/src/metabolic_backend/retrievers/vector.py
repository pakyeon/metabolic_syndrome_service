"""Vector retrieval utilities backed by pgvector with local fallbacks."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import replace
from typing import List, Sequence

import psycopg
from psycopg.rows import dict_row

from pgvector.psycopg import register_vector
from ..config import get_settings
from ..ingestion import Chunk, iter_chunks
from ..ingestion.embedding import EmbeddingProvider, resolve_embedding_config

LOGGER = logging.getLogger(__name__)


class VectorRetriever:
    """Search chunks using vector similarity with pgvector fallback."""

    def __init__(
        self,
        *,
        chunks: Sequence[Chunk] | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        table_name: str | None = None,
        database_url: str | None = None,
    ) -> None:
        self._settings = get_settings()
        self._chunks = list(chunks) if chunks is not None else list(iter_chunks())
        self._embedding_provider = embedding_provider or EmbeddingProvider(
            resolve_embedding_config()
        )
        self._table = table_name or "document_chunks"
        self._database_url = database_url
        self._local_vectors: List[tuple[Chunk, List[float]]] | None = None
        self._chunk_index = {chunk.chunk_id: chunk for chunk in self._chunks}

    # ------------------------------------------------------------------
    def retrieve(self, query: str, *, limit: int = 3) -> List[Chunk]:
        if limit <= 0:
            return []

        if self._database_url and psycopg is not None:
            try:
                results = self._retrieve_from_database(query, limit)
                if results:
                    return results
            except Exception as exc:  # pragma: no cover - depends on external DB
                LOGGER.warning("Vector DB query failed, falling back to local cache (%s)", exc)

        return self._retrieve_from_cache(query, limit)

    async def retrieve_async(self, query: str, *, limit: int = 3) -> List[Chunk]:
        """Async version of retrieve for parallel execution."""
        if limit <= 0:
            return []

        # Use run_in_executor for DB queries
        if self._database_url and psycopg is not None:
            try:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    None, self._retrieve_from_database, query, limit
                )
                if results:
                    return results
            except Exception as exc:  # pragma: no cover - depends on external DB
                LOGGER.warning("Vector DB query failed, falling back to local cache (%s)", exc)

        # Fallback to local cache (also run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._retrieve_from_cache, query, limit)

    # ------------------------------------------------------------------
    def _retrieve_from_database(self, query: str, limit: int) -> List[Chunk]:
        embedding = self._embedding_provider.embed([query])[0]
        if dict_row is None:  # pragma: no cover - psycopg optional
            return []

        with psycopg.connect(self._database_url, row_factory=dict_row) as conn:
            if register_vector is not None:
                register_vector(conn)

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT chunk_id, document_id, section_path, source_path, text,
                               token_count, embedding, metadata,
                               embedding <=> %s AS distance
                        FROM {self._table}
                        ORDER BY embedding <=> %s
                        LIMIT %s
                        """,
                        (embedding, embedding, limit),
                    )
                    rows = cur.fetchall()
            except Exception as exc:  # pragma: no cover - depends on DB
                LOGGER.warning("Vector DB query error: %s", exc)
                return []

        results: List[Chunk] = []
        for row in rows:
            metadata = row.get("metadata") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {"raw": metadata}
            section_path = row.get("section_path") or []
            if isinstance(section_path, str):
                try:
                    section_path = json.loads(section_path)
                except json.JSONDecodeError:
                    section_path = [section_path]

            base = self._chunk_index.get(row["chunk_id"]) or Chunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                section_path=list(section_path),
                source_path=row["source_path"],
                text=row["text"],
                token_count=row["token_count"],
            )
            chunk = replace(base)
            chunk.embedding = row.get("embedding")
            chunk.metadata = dict(metadata) if metadata else dict(base.metadata)
            chunk.metadata["retrieval"] = "vector"
            distance = float(row.get("distance", 0.0) or 0.0)
            chunk.score = 1.0 / (1.0 + distance)
            results.append(chunk)

        return results

    # ------------------------------------------------------------------
    def _retrieve_from_cache(self, query: str, limit: int) -> List[Chunk]:
        local_vectors = self._cached_vectors()
        if not local_vectors:
            return []

        query_vector = self._embedding_provider.embed([query])[0]
        scored: List[tuple[float, Chunk]] = []
        for chunk, vector in local_vectors:
            score = self._cosine_similarity(query_vector, vector)
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_chunks: List[Chunk] = []
        for score, chunk in scored[:limit]:
            enriched = replace(chunk)
            enriched.metadata = dict(chunk.metadata)
            enriched.metadata["retrieval"] = "vector"
            enriched.score = score
            top_chunks.append(enriched)

        return top_chunks

    # ------------------------------------------------------------------
    def _cached_vectors(self) -> List[tuple[Chunk, List[float]]]:
        if self._local_vectors is not None:
            return self._local_vectors

        vectors: List[tuple[Chunk, List[float]]] = []
        for chunk in self._chunks:
            embedding = chunk.embedding
            if embedding is None:
                embedding = self._embedding_provider.embed([chunk.text])[0]
                chunk.embedding = embedding
            vectors.append((chunk, embedding))

        self._local_vectors = vectors
        return vectors

    # ------------------------------------------------------------------
    @staticmethod
    def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        dot = sum(x * y for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(y * y for y in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


__all__ = ["VectorRetriever"]
