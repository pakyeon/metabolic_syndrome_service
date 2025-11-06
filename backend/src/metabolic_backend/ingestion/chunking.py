"""Markdown chunking utilities using LangChain splitters."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    from langchain_text_splitters import (
        RecursiveCharacterTextSplitter,
        MarkdownHeaderTextSplitter,
    )
except ImportError:
    MarkdownHeaderTextSplitter = None  # type: ignore
    RecursiveCharacterTextSplitter = None  # type: ignore

import tiktoken

from .models import Chunk

LOGGER = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Estimate token count for a string using tiktoken when available."""
    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = None
        if encoding is not None:
            return len(encoding.encode(text))

    return max(1, len(text.split()))


@dataclass(slots=True)
class ChunkingConfig:
    """Configuration for chunking."""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_tokens: int = 120
    min_content_length: int = 50
    max_merge_size: int = 2000


class SemanticChunker:
    """Split markdown documents into chunks with header context."""

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig()

        if MarkdownHeaderTextSplitter is None or RecursiveCharacterTextSplitter is None:
            LOGGER.warning("LangChain text splitters not available. Install langchain-text-splitters.")
            self._header_splitter = None
            self._text_splitter = None
        else:
            # Split on H1-H3 headers
            self._header_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header 1"),
                    ("##", "Header 2"),
                    ("###", "Header 3"),
                ],
                strip_headers=False,
            )

            # For additional splitting of large chunks
            self._text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self._config.chunk_size,
                chunk_overlap=self._config.chunk_overlap,
            )

    def chunk_markdown(
        self,
        document_id: str,
        md_path: Path,
        *,
        content: str | None = None,
        starting_index: int = 0,
    ) -> List[Chunk]:
        """Split a markdown file into chunks preserving heading context."""

        if self._header_splitter is None or self._text_splitter is None:
            LOGGER.error("Text splitters not initialized. Cannot chunk documents.")
            return []

        text = content if content is not None else md_path.read_text(encoding="utf-8")

        chunks: List[Chunk] = []
        chunk_idx = starting_index

        # Step 1: Split by H1-H3 headers
        splits = self._header_splitter.split_text(text)

        for split in splits:
            split_content = split.page_content.strip()
            if not split_content:
                continue

            # Step 2: Extract H1-H3 from metadata
            base_metadata = split.metadata

            # Step 3: Extract H4-H6 from content
            lower_headers = self._extract_lower_level_headers(split_content)
            merged_metadata = {**base_metadata, **lower_headers}

            # Step 4: Build header_path (H1 > H2 > H3 > ...)
            header_path = self._compose_header_path(merged_metadata)

            # Step 5: Further split if content exceeds chunk_size
            if len(split_content) > self._config.chunk_size:
                sub_chunks = self._text_splitter.split_text(split_content)
                for sub_chunk in sub_chunks:
                    chunks.append(self._create_chunk(
                        document_id=document_id,
                        md_path=md_path,
                        chunk_index=chunk_idx,
                        text=sub_chunk,
                        header_path=header_path,
                        metadata=merged_metadata,
                    ))
                    chunk_idx += 1
            else:
                chunks.append(self._create_chunk(
                    document_id=document_id,
                    md_path=md_path,
                    chunk_index=chunk_idx,
                    text=split_content,
                    header_path=header_path,
                    metadata=merged_metadata,
                ))
                chunk_idx += 1

        # Step 6: Merge small chunks
        merged_chunks = self._merge_small_chunks(chunks, document_id)

        # Step 7: Remove duplicates
        unique_chunks = self._remove_duplicates(merged_chunks)

        return unique_chunks

    def _create_chunk(
        self,
        *,
        document_id: str,
        md_path: Path,
        chunk_index: int,
        text: str,
        header_path: str,
        metadata: dict,
    ) -> Chunk:
        """Create a Chunk object with proper metadata."""
        chunk_id = f"{document_id}:{md_path.stem}:{chunk_index:04d}"
        chunk_text = text.strip()

        # Ensure text ends with period for consistency
        if chunk_text and not chunk_text.endswith("."):
            chunk_text += "."

        token_count = _estimate_tokens(chunk_text)

        # Build section_path from headers
        section_path = []
        for i in range(1, 7):
            header = metadata.get(f"Header {i}")
            if header:
                section_path.append(header)

        return Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            section_path=section_path,
            source_path=str(md_path),
            text=chunk_text,
            token_count=token_count,
            metadata={
                "header_path": header_path,
                **{k: v for k, v in metadata.items() if k.startswith("Header")},
            },
        )

    @staticmethod
    def _extract_lower_level_headers(content: str) -> dict:
        """Extract H4, H5, H6 headers from content."""
        headers = {}
        lines = content.split("\n")
        patterns = {
            "Header 4": re.compile(r"^\s*####\s+(.+)"),
            "Header 5": re.compile(r"^\s*#####\s+(.+)"),
            "Header 6": re.compile(r"^\s*######\s+(.+)"),
        }

        # Get first occurrence of each level
        for key, pattern in patterns.items():
            for line in lines:
                match = pattern.match(line)
                if match:
                    headers[key] = match.group(1).strip()
                    break

        return headers

    @staticmethod
    def _compose_header_path(metadata: dict) -> str:
        """Compose header path from metadata (H1 > H2 > H3 > ...)."""
        parts = []
        for i in range(1, 7):
            header = metadata.get(f"Header {i}")
            if header:
                parts.append(header.strip())
        return " > ".join(parts)

    def _is_header_only_chunk(self, text: str) -> bool:
        """Check if chunk contains only headers."""
        header_pattern = r"^#{1,6}\s+.+$"
        lines = text.strip().split("\n")
        non_empty_lines = [line.strip() for line in lines if line.strip()]

        if not non_empty_lines:
            return True

        header_only = all(re.match(header_pattern, line) for line in non_empty_lines)
        content_without_headers = "\n".join(
            [line for line in non_empty_lines if not re.match(header_pattern, line)]
        )
        too_short = len(content_without_headers.strip()) < self._config.min_content_length

        return header_only or too_short

    def _can_merge_chunks(self, chunk1: Chunk, chunk2: Chunk) -> bool:
        """Check if two chunks can be merged."""
        # Must be from same document
        if chunk1.document_id != chunk2.document_id:
            return False

        # Check header levels
        level1 = len(chunk1.section_path)
        level2 = len(chunk2.section_path)

        # Both have no headers
        if level1 == 0 and level2 == 0:
            return True

        # Same level
        if level1 == level2:
            return True

        # level2 is sub-section of level1 (within 2 levels)
        if level1 > 0 and level1 < level2 <= level1 + 2:
            return True

        return False

    def _dedup_overlap(self, left: str, right: str) -> str:
        """Remove overlapping text between two strings."""
        if not left or not right:
            return right

        if right.strip() and right in left:
            return ""

        max_len = min(len(left), len(right), 1000)
        for k in range(max_len, 0, -1):
            if left.endswith(right[:k]):
                return right[k:]

        return right

    def _merge_small_chunks(self, chunks: List[Chunk], document_id: str) -> List[Chunk]:
        """Merge small chunks together."""
        if not chunks:
            return chunks

        merged: List[Chunk] = []
        i = 0

        while i < len(chunks):
            current = chunks[i]
            current_text = current.text.strip()

            # If chunk is already large enough and not header-only, keep it
            if (
                len(current_text) >= self._config.min_chunk_tokens
                and not self._is_header_only_chunk(current_text)
            ):
                merged.append(current)
                i += 1
                continue

            # Try to merge with following chunks
            merged_text = current_text
            merged_metadata = dict(current.metadata)
            merged_section_path = list(current.section_path)
            j = i + 1

            while j < len(chunks) and len(merged_text) < self._config.max_merge_size:
                next_chunk = chunks[j]

                # Only merge within same document
                if next_chunk.document_id != document_id:
                    break

                if not self._can_merge_chunks(current, next_chunk):
                    break

                # Dedup overlap
                next_text = self._dedup_overlap(merged_text, next_chunk.text.strip())
                if not next_text:
                    j += 1
                    continue

                candidate = merged_text + "\n\n" + next_text
                if len(candidate) > self._config.max_merge_size:
                    break

                merged_text = candidate

                # Merge metadata (don't overwrite)
                for k, v in next_chunk.metadata.items():
                    if k not in merged_metadata:
                        merged_metadata[k] = v

                # Update section_path to include deeper headers
                if len(next_chunk.section_path) > len(merged_section_path):
                    merged_section_path = list(next_chunk.section_path)

                # Stop if we've reached minimum size
                if (
                    len(merged_text) >= self._config.min_chunk_tokens
                    and not self._is_header_only_chunk(merged_text)
                ):
                    j += 1
                    break

                j += 1

            # Create merged chunk
            if merged_text.strip():
                chunk_id = f"{document_id}:{Path(current.source_path).stem}:{len(merged):04d}"
                merged.append(Chunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    section_path=merged_section_path,
                    source_path=current.source_path,
                    text=merged_text,
                    token_count=_estimate_tokens(merged_text),
                    metadata=merged_metadata,
                ))

            i = j

        LOGGER.info("Merged %d chunks into %d chunks", len(chunks), len(merged))
        return merged

    @staticmethod
    def _remove_duplicates(chunks: List[Chunk]) -> List[Chunk]:
        """Remove duplicate chunks."""
        unique: List[Chunk] = []
        seen = set()

        normalize = lambda t: re.sub(r"\s+", " ", t.strip())

        for chunk in chunks:
            key = (normalize(chunk.text), chunk.document_id)
            if key not in seen:
                seen.add(key)
                unique.append(chunk)

        if len(chunks) != len(unique):
            LOGGER.info("Removed %d duplicate chunks", len(chunks) - len(unique))

        return unique


__all__ = ["ChunkingConfig", "SemanticChunker", "_estimate_tokens"]
