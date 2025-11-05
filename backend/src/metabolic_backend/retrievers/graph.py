"""Graph retrieval utilities leveraging Graphiti with keyword fallbacks."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import replace
from typing import Iterable, List, Sequence

try:
    from graphiti_core import Graphiti  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Graphiti = None  # type: ignore[assignment]

from ..config import get_settings
from ..ingestion import Chunk, iter_chunks

LOGGER = logging.getLogger(__name__)


class GraphRetriever:
    """Retrieve supporting facts from Graphiti knowledge graph with safe fallback."""

    def __init__(
        self,
        *,
        chunks: Sequence[Chunk] | None = None,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        llm_client=None,
    ) -> None:
        settings = get_settings()
        self._chunks = list(chunks) if chunks is not None else list(iter_chunks())
        self._chunk_index = {chunk.chunk_id: chunk for chunk in self._chunks}
        self._uri = uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self._llm_client = llm_client or self._create_default_llm_client()
        self._graphiti_ready = bool(Graphiti is not None and self._uri and self._user and self._password)
        if not self._graphiti_ready:
            LOGGER.debug("Graphiti search unavailable; graph retrieval will use local cache fallback.")

    # ------------------------------------------------------------------
    def _create_default_llm_client(self):
        """Create default LLM client for Graphiti (OpenAI with structured output support)."""
        try:
            from openai import AsyncOpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                return AsyncOpenAI(api_key=api_key)
        except Exception as exc:
            LOGGER.debug("OpenAI client unavailable for Graphiti (%s)", exc)
        return None

    # ------------------------------------------------------------------
    def close(self) -> None:
        # Graphiti connections are short-lived per query; nothing to close.
        return None

    # ------------------------------------------------------------------
    def retrieve(self, query: str, *, limit: int = 3) -> List[Chunk]:
        if self._graphiti_ready:
            try:
                results = self._retrieve_from_graphiti(query, limit)
                if results:
                    return results
            except Exception as exc:  # pragma: no cover - depends on external service
                LOGGER.warning("Graphiti search failed (%s); falling back to keyword scan.", exc)

        return self._retrieve_from_cache(query, limit)

    async def retrieve_async(self, query: str, *, limit: int = 3) -> List[Chunk]:
        """Async version of retrieve for parallel execution."""
        if self._graphiti_ready:
            try:
                results = await self._search_graphiti(query, limit)
                if results:
                    return results
            except Exception as exc:  # pragma: no cover - depends on external service
                LOGGER.warning("Graphiti search failed (%s); falling back to keyword scan.", exc)

        # Fallback to cache (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._retrieve_from_cache, query, limit)

    # ------------------------------------------------------------------
    async def _search_graphiti(self, query: str, limit: int) -> List[Chunk]:
        """Internal async search method for Graphiti."""
        assert Graphiti is not None  # for type checkers
        if self._llm_client is not None:
            client = Graphiti(
                self._uri,
                self._user,
                self._password,
                llm_client=self._llm_client
            )
        else:
            client = Graphiti(self._uri, self._user, self._password)
        try:
            edges = await client.search(query=query, num_results=limit * 2)
        finally:
            await client.close()

        seen: set[str] = set()
        results: List[Chunk] = []
        for edge in edges:
            episodes = getattr(edge, "episodes", []) or []
            for episode in episodes:
                chunk_id = getattr(episode, "name", None) or getattr(episode, "episode_id", None)
                if not isinstance(chunk_id, str) or chunk_id in seen:
                    continue
                seen.add(chunk_id)
                base = self._chunk_index.get(chunk_id)
                if base is None:
                    content = getattr(episode, "body", None) or getattr(episode, "content", "")
                    if not content:
                        continue
                    base = Chunk(
                        chunk_id=chunk_id,
                        document_id=getattr(episode, "group_id", "graphiti"),
                        section_path=[],
                        source_path=getattr(episode, "source_description", "graphiti"),
                        text=content,
                        token_count=len(content.split()),
                    )
                    self._chunks.append(base)
                    self._chunk_index[chunk_id] = base
                enriched = replace(base)
                enriched.metadata = dict(base.metadata)
                enriched.metadata["graph_fact"] = getattr(edge, "fact", "")
                enriched.metadata["graph_uuid"] = str(getattr(edge, "uuid", ""))
                enriched.metadata["retrieval"] = "graphiti"
                enriched.score = float(getattr(edge, "score", 1.0))
                results.append(enriched)
                if len(results) >= limit:
                    return results
        return results

    def _retrieve_from_graphiti(self, query: str, limit: int) -> List[Chunk]:
        """Synchronous wrapper for Graphiti search."""
        try:
            return asyncio.run(self._search_graphiti(query, limit))
        except RuntimeError as exc:
            # Try nest_asyncio to allow nested event loops
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(self._search_graphiti(query, limit))
            except Exception as nested_exc:
                LOGGER.warning(
                    "Event loop already running; skipping Graphiti search. "
                    "Install nest_asyncio or run outside async context: %s",
                    exc
                )
                return []

    # ------------------------------------------------------------------
    def _retrieve_from_cache(self, query: str, limit: int) -> List[Chunk]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        scored: List[tuple[int, Chunk]] = []
        for chunk in self._chunks:
            lowered = chunk.text.lower()
            score = sum(lowered.count(keyword.lower()) for keyword in keywords)
            if score:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        top: List[Chunk] = []
        for score, chunk in scored[:limit]:
            enriched = replace(chunk)
            enriched.metadata = dict(chunk.metadata)
            enriched.metadata["retrieval"] = "keyword"
            enriched.score = float(score)
            top.append(enriched)
        return top

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        candidates = [token.strip() for token in re.split(r"[\\s,.;:?!]", text) if token.strip()]
        return [token for token in candidates if len(token) > 1]


__all__ = ["GraphRetriever"]
