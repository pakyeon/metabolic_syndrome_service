"""Vector retrieval utilities backed by a persisted Chroma store."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import List, Sequence

from ..config import get_settings
from ..embeddings import OpenAIEmbeddings
from ..ingestion import Chunk, iter_chunks
from ..ingestion.stores import ChromaVectorStore

LOGGER = logging.getLogger(__name__)


class VectorRetriever:
    """Search chunks using vector similarity stored in Chroma."""

    def __init__(
        self,
        *,
        chunks: Sequence[Chunk] | None = None,
        embedding_client: OpenAIEmbeddings | None = None,
        persist_directory: str | Path | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._settings = get_settings()
        self._embedding_client = embedding_client or OpenAIEmbeddings(
            model=self._settings.embedding_model
        )

        self._chunks = list(chunks) if chunks is not None else list(iter_chunks())
        self._chunk_index = {chunk.chunk_id: chunk for chunk in self._chunks}

        default_dir = self._settings.cache_root / "vector_store" / "chroma_db"
        if persist_directory is not None:
            persist_path = Path(persist_directory).expanduser()
            if not persist_path.is_absolute():
                persist_path = (default_dir / persist_path).resolve()
        else:
            persist_path = default_dir

        self._persist_directory = persist_path
        self._collection_name = collection_name or os.getenv("CHROMA_COLLECTION", "metabolic_chunks")

        try:
            self._store: ChromaVectorStore | None = ChromaVectorStore(
                persist_directory=self._persist_directory,
                collection_name=self._collection_name,
                embedding_client=self._embedding_client,
            )
        except Exception as exc:  # pragma: no cover - dependency issues
            LOGGER.warning(
                "Chroma vector store unavailable (%s); vector retrieval disabled.", exc
            )
            self._store = None

    # ------------------------------------------------------------------
    def retrieve(self, query: str, *, limit: int = 3) -> List[Chunk]:
        if limit <= 0 or not query.strip():
            return []

        if self._store is None:
            LOGGER.debug("Chroma vector store not initialized; returning no results")
            return []

        try:
            vectorstore = self._store.load()
            return self._search(vectorstore, query, limit)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("Vector search failed (%s)", exc)
            return []

    async def retrieve_async(self, query: str, *, limit: int = 3) -> List[Chunk]:
        """Async wrapper around synchronous retrieval."""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.retrieve(query, limit=limit))

    # ------------------------------------------------------------------
    def _search(self, vectorstore, query: str, limit: int) -> List[Chunk]:
        try:
            doc_pairs = vectorstore.similarity_search_with_relevance_scores(query, k=limit)
            score_fn = float
        except AttributeError:
            doc_pairs = vectorstore.similarity_search_with_score(query, k=limit)
            score_fn = self._distance_to_score

        results: List[Chunk] = []
        for doc, raw_score in doc_pairs:
            chunk = self._document_to_chunk(doc)
            chunk.metadata.setdefault("retrieval", "vector")
            try:
                chunk.score = score_fn(raw_score)
            except Exception:  # pragma: no cover - defensive
                chunk.score = 0.0
            results.append(chunk)
        return results

    # ------------------------------------------------------------------
    def _document_to_chunk(self, doc) -> Chunk:
        metadata = dict(getattr(doc, "metadata", {}) or {})

        section_path = metadata.get("section_path", [])
        if isinstance(section_path, str):
            try:
                section_path = json.loads(section_path)
            except json.JSONDecodeError:
                section_path = [section_path]
        elif not isinstance(section_path, list):
            section_path = [section_path]

        chunk_meta = metadata.get("chunk_metadata", {})
        if isinstance(chunk_meta, str):
            try:
                chunk_meta = json.loads(chunk_meta)
            except json.JSONDecodeError:
                chunk_meta = {"raw": chunk_meta}

        chunk_id = metadata.get("chunk_id") or metadata.get("id")
        base = self._chunk_index.get(chunk_id) if chunk_id else None

        document_id = metadata.get("document_id")
        if not document_id and base is not None:
            document_id = base.document_id
        if not document_id:
            document_id = chunk_id or "unknown"

        source_path = metadata.get("source_path") or (base.source_path if base else "")
        token_count = metadata.get("token_count") or (base.token_count if base else 0)
        try:
            token_count = int(token_count)
        except (TypeError, ValueError):
            token_count = 0

        if base is not None and chunk_id is None:
            resolved_chunk_id = base.chunk_id
        elif chunk_id is not None:
            resolved_chunk_id = chunk_id
        else:
            digest = hashlib.sha1(getattr(doc, "page_content", "").encode("utf-8")).hexdigest()
            resolved_chunk_id = f"chroma:{digest}"

        chunk = Chunk(
            chunk_id=resolved_chunk_id,
            document_id=document_id,
            section_path=list(section_path),
            source_path=source_path,
            text=getattr(doc, "page_content", ""),
            token_count=token_count,
            metadata=dict(chunk_meta),
        )
        return chunk

    # ------------------------------------------------------------------
    @staticmethod
    def _distance_to_score(value) -> float:
        try:
            distance = float(value)
        except (TypeError, ValueError):
            return 0.0
        if distance < 0:
            return 0.0
        return 1.0 / (1.0 + distance)


__all__ = ["VectorRetriever"]
