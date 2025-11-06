"""Persistence helpers for vector (pgvector) and Graphiti stores."""

from __future__ import annotations

import os
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Sequence

import psycopg  # type: ignore

from pgvector.psycopg import register_vector

from graphiti_core import Graphiti  # type: ignore
from graphiti_core.nodes import EpisodeType  # type: ignore

from .models import Chunk

LOGGER = logging.getLogger(__name__)


class VectorStoreWriter:
    """Persist embeddings into a pgvector-backed table."""

    def __init__(
        self,
        dsn: str | None,
        *,
        table: str = "document_chunks",
        embedding_dim: int = 1536,
        index_threshold: int = 1000,
    ) -> None:
        self._dsn = dsn
        self._table = table
        self._embedding_dim = embedding_dim
        self._index_threshold = index_threshold
        self._connection = None
        self._enabled = bool(dsn and psycopg is not None)

    def __enter__(self) -> "VectorStoreWriter":
        if not self._enabled:
            return self

        if psycopg is None:
            LOGGER.warning("psycopg not installed; skipping vector store writes")
            self._enabled = False
            return self

        try:  # pragma: no cover - relies on external database
            self._connection = psycopg.connect(self._dsn, autocommit=True)
            if register_vector is not None:
                register_vector(self._connection)
            self._ensure_schema()
        except Exception as exc:
            LOGGER.warning("Disabling vector store writes; connection failed (%s)", exc)
            self._enabled = False
            if self._connection is not None:
                self._connection.close()
                self._connection = None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._connection is not None:  # pragma: no branch
            self._connection.close()
            self._connection = None

    def _ensure_schema(self) -> None:
        """Ensure schema is compatible with existing chunks table."""
        if self._connection is None:
            return

        with self._connection.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception as exc:
                LOGGER.debug("Unable to create vector extension (%s); continuing", exc)

            # Check if table is 'chunks' from schema.sql or custom document_chunks
            if self._table == "chunks":
                # Use existing chunks table from schema.sql - no need to create
                LOGGER.info("Using existing 'chunks' table from schema.sql")
            else:
                # Create custom table with explicit vector dimension
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table} (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        section_path JSONB NOT NULL,
                        source_path TEXT NOT NULL,
                        text TEXT NOT NULL,
                        token_count INTEGER NOT NULL,
                        embedding VECTOR({self._embedding_dim}),
                        metadata JSONB
                    )
                    """
                )

    def _ensure_vector_index(self) -> None:
        """Create vector index only if chunk count exceeds threshold."""
        if self._connection is None:
            return

        with self._connection.cursor() as cur:
            # Check total row count
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            count_result = cur.fetchone()
            if count_result is None:
                return
            total_chunks = count_result[0]

            if total_chunks < self._index_threshold:
                LOGGER.info(
                    "Skipping vector index creation: %d chunks < %d threshold. "
                    "Sequential scan is faster for small datasets.",
                    total_chunks,
                    self._index_threshold,
                )
                return

            LOGGER.info(
                "Creating vector index: %d chunks >= %d threshold",
                total_chunks,
                self._index_threshold,
            )

            # Check if index already exists
            cur.execute(
                f"""
                SELECT COUNT(*) FROM pg_indexes
                WHERE tablename = '{self._table}'
                AND indexname IN ('{self._table}_embedding_hnsw_idx', '{self._table}_embedding_ivfflat_idx')
                """
            )
            index_result = cur.fetchone()
            if index_result and index_result[0] > 0:
                LOGGER.info("Vector index already exists on %s.embedding", self._table)
                return

            # Create HNSW index for fast vector similarity search
            try:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self._table}_embedding_hnsw_idx
                    ON {self._table} USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64)
                    """
                )
                LOGGER.info(
                    "HNSW index created on %s.embedding (%d chunks)", self._table, total_chunks
                )
            except Exception as exc:
                LOGGER.warning(
                    "Failed to create HNSW index (%s); falling back to IVFFlat. "
                    "Consider upgrading to PostgreSQL 16+ for HNSW support.",
                    exc,
                )
                # Fallback to IVFFlat if HNSW is not available (older pgvector versions)
                try:
                    cur.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS {self._table}_embedding_ivfflat_idx
                        ON {self._table} USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                        """
                    )
                    LOGGER.info(
                        "IVFFlat index created on %s.embedding (%d chunks)",
                        self._table,
                        total_chunks,
                    )
                except Exception as fallback_exc:
                    LOGGER.warning(
                        "Failed to create vector index (%s); queries will use sequential scan",
                        fallback_exc,
                    )

    def upsert_chunks(self, chunks: Sequence[Chunk]) -> int:
        if not self._enabled or self._connection is None:
            return 0

        inserted = 0
        with self._connection.cursor() as cur:
            for chunk in chunks:
                if chunk.embedding is None:
                    continue
                try:
                    cur.execute(
                        f"""
                        INSERT INTO {self._table} (
                            chunk_id, document_id, section_path, source_path, text, token_count, embedding, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chunk_id)
                        DO UPDATE SET
                            section_path = EXCLUDED.section_path,
                            source_path = EXCLUDED.source_path,
                            text = EXCLUDED.text,
                            token_count = EXCLUDED.token_count,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            json.dumps(chunk.section_path, ensure_ascii=False),
                            chunk.source_path,
                            chunk.text,
                            chunk.token_count,
                            chunk.embedding,
                            json.dumps(chunk.metadata, ensure_ascii=False),
                        ),
                    )
                    inserted += cur.rowcount
                except Exception as exc:
                    LOGGER.warning(
                        "Failed to upsert chunk %s into vector store (%s)", chunk.chunk_id, exc
                    )

        # Create vector index if chunk count exceeds threshold
        if inserted > 0:
            self._ensure_vector_index()

        return inserted


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
