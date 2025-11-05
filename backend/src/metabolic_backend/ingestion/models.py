"""Dataclasses and helpers shared across ingestion and retrieval layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Sequence


@dataclass(slots=True)
class Chunk:
    """Represents a semantically coherent document chunk."""

    chunk_id: str
    document_id: str
    section_path: List[str]
    source_path: str
    text: str
    token_count: int
    embedding: List[float] | None = field(default=None)
    score: float | None = field(default=None)
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def source(self) -> str:
        """Compatibility accessor for serialization helpers."""

        return self.source_path

    def as_record(self) -> Dict[str, object]:
        """Serialize chunk into a JSON-friendly payload."""

        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "section_path": list(self.section_path),
            "source_path": self.source_path,
            "text": self.text,
            "token_count": self.token_count,
            "embedding": list(self.embedding) if self.embedding is not None else None,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class IngestionStats:
    """Detailed counts produced by the ingestion pipeline."""

    documents_processed: int = 0
    chunks_created: int = 0
    vector_records: int = 0
    graph_nodes: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


__all__ = ["Chunk", "IngestionStats"]
