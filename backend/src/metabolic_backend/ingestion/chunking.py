"""Semantic markdown chunking utilities."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

try:
    import numpy as np
except Exception:  # pragma: no cover - fallback for lean environments
    np = None  # type: ignore[assignment]

from sklearn.feature_extraction.text import TfidfVectorizer

import tiktoken

from .models import Chunk

LOGGER = logging.getLogger(__name__)

_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _estimate_tokens(text: str) -> int:
    """Estimate token count for a string using tiktoken when available."""

    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover - fallback when encoding missing
            encoding = None
        if encoding is not None:
            return len(encoding.encode(text))

    return max(1, len(text.split()))


@dataclass(slots=True)
class ChunkingConfig:
    """Configuration for semantic chunking."""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_tokens: int = 120
    similarity_threshold: float = 0.18


class SemanticChunker:
    """Split markdown documents into semantically aware chunks."""

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig()

    # ------------------------------------------------------------------
    def chunk_markdown(
        self,
        document_id: str,
        md_path: Path,
        *,
        content: str | None = None,
        starting_index: int = 0,
    ) -> List[Chunk]:
        """Split a markdown file into chunks preserving heading context."""

        text = content if content is not None else md_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        headings: List[str] = []
        buffer: List[str] = []
        chunks: List[Chunk] = []
        chunk_idx = starting_index

        for line in lines:
            stripped = line.strip()
            if not stripped:
                buffer.append("")
                continue

            if stripped.startswith("#"):
                if buffer:
                    chunk_idx = self._flush_buffer(
                        document_id=document_id,
                        md_path=md_path,
                        headings=headings,
                        buffer=buffer,
                        chunk_index_start=chunk_idx,
                        chunks=chunks,
                    )
                    buffer = []
                level = stripped.count("#", 0, len(stripped.split(" ")[0]))
                heading_text = stripped.lstrip("#").strip()
                headings = self._update_headings(headings, level, heading_text)
            else:
                buffer.append(stripped)

        if buffer:
            chunk_idx = self._flush_buffer(
                document_id=document_id,
                md_path=md_path,
                headings=headings,
                buffer=buffer,
                chunk_index_start=chunk_idx,
                chunks=chunks,
            )

        return chunks

    # ------------------------------------------------------------------
    def _flush_buffer(
        self,
        *,
        document_id: str,
        md_path: Path,
        headings: Sequence[str],
        buffer: Sequence[str],
        chunk_index_start: int,
        chunks: List[Chunk],
    ) -> int:
        text = "\n".join(buffer).strip()
        if not text:
            return chunk_index_start

        semantic_spans = self._semantic_split(text)
        for relative_idx, span in enumerate(semantic_spans):
            chunk_id = f"{document_id}:{md_path.stem}:{chunk_index_start + relative_idx:04d}"
            chunk_text = span.strip()
            if not chunk_text.endswith("."):
                chunk_text += "."
            token_count = _estimate_tokens(chunk_text)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    section_path=list(headings),
                    source_path=str(md_path),
                    text=chunk_text,
                    token_count=token_count,
                    metadata={"heading": headings[-1] if headings else ""},
                )
            )
        return chunk_index_start + len(semantic_spans)

    # ------------------------------------------------------------------
    def _semantic_split(self, text: str) -> List[str]:
        sentences = self._split_sentences(text)
        if not sentences:
            return [text]

        if len(sentences) == 1:
            return sentences

        if TfidfVectorizer is None or np is None:
            return self._simple_split(sentences)

        try:  # pragma: no cover - heavy branch
            vectorizer = TfidfVectorizer(max_features=2048, token_pattern=r"(?u)\b\w+\b")
            matrix = vectorizer.fit_transform(sentences).toarray()
        except ValueError:
            return self._simple_split(sentences)

        chunks: List[List[tuple[str, int]]] = []
        current: List[tuple[str, int]] = []
        current_tokens = 0

        for idx, sentence in enumerate(sentences):
            tokens = _estimate_tokens(sentence)
            similarity = 1.0
            if current:
                prev_vec = matrix[idx - 1]
                similarity = self._cosine_similarity(matrix[idx], prev_vec)

            should_split = current_tokens + tokens > self._config.chunk_size or (
                similarity < self._config.similarity_threshold
                and current_tokens >= self._config.min_chunk_tokens
            )
            if should_split and current:
                chunks.append(list(current))
                current = self._overlap_tail(current)
                current_tokens = sum(item[1] for item in current)

            current.append((sentence, tokens))
            current_tokens += tokens

        if current:
            chunks.append(list(current))

        return [" ".join(sentence for sentence, _ in span).strip() for span in chunks if span]

    # ------------------------------------------------------------------
    def _simple_split(self, sentences: Sequence[str]) -> List[str]:
        """Fallback splitter that enforces size limits without semantics."""

        spans: List[List[tuple[str, int]]] = []
        current: List[tuple[str, int]] = []
        current_tokens = 0

        for sentence in sentences:
            tokens = _estimate_tokens(sentence)
            if current and current_tokens + tokens > self._config.chunk_size:
                spans.append(list(current))
                current = self._overlap_tail(current)
                current_tokens = sum(item[1] for item in current)

            current.append((sentence, tokens))
            current_tokens += tokens

        if current:
            spans.append(list(current))

        return [" ".join(sentence for sentence, _ in span).strip() for span in spans if span]

    # ------------------------------------------------------------------
    def _overlap_tail(self, current: Sequence[tuple[str, int]]) -> List[tuple[str, int]]:
        if self._config.chunk_overlap <= 0:
            return []

        overlap: List[tuple[str, int]] = []
        token_budget = 0
        for sentence, tokens in reversed(current):
            overlap.insert(0, (sentence, tokens))
            token_budget += tokens
            if token_budget >= self._config.chunk_overlap:
                break
        return overlap

    # ------------------------------------------------------------------
    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        sentences = [
            segment.strip() for segment in _SENTENCE_PATTERN.split(text) if segment.strip()
        ]
        if not sentences:
            sentences = [text.strip()]
        return sentences

    @staticmethod
    def _cosine_similarity(vec_a, vec_b) -> float:
        if np is None:
            return 1.0
        denominator = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        if denominator == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denominator)

    @staticmethod
    def _update_headings(headings: Sequence[str], level: int, heading_text: str) -> List[str]:
        if level <= 0:
            return list(headings)

        prefix = list(headings[: level - 1])
        prefix.append(heading_text)
        return prefix


__all__ = ["ChunkingConfig", "SemanticChunker", "_estimate_tokens"]
