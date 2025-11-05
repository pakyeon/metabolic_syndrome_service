"""Document ingestion pipeline that prepares semantic chunks, embeddings, and persistence."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from ..config import get_settings
from .chunking import ChunkingConfig, SemanticChunker
from .embedding import EmbeddingProvider, resolve_embedding_config
from .models import Chunk
from .stores import GraphitiWriter, VectorStoreWriter

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    """Summary of pipeline execution."""

    total_documents: int
    total_chunks: int
    output_path: Path
    vector_records: int
    graph_records: int


class IngestionPipeline:
    """Pipeline for ingesting markdown knowledge base into chunk artifacts."""

    def __init__(
        self,
        data_root: Path | None = None,
        output_root: Path | None = None,
        *,
        chunk_config: ChunkingConfig | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        settings = get_settings()
        self.data_root = data_root or settings.data_root
        cache_root = output_root or settings.cache_root
        self.output_root = cache_root / "vector_store"
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.chunker = SemanticChunker(chunk_config)
        self.embedding_provider = embedding_provider or EmbeddingProvider(
            resolve_embedding_config()
        )

        self.database_url = os.getenv("DATABASE_URL")
        self.vector_table = os.getenv("METABOLIC_VECTOR_TABLE", "document_chunks")
        self.vector_index_threshold = settings.vector_index_threshold
        self.neo4j_uri = os.getenv("NEO4J_URI", settings.neo4j_uri)
        self.neo4j_user = os.getenv("NEO4J_USER", settings.neo4j_user)
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", settings.neo4j_password)
        self.use_vector_store = (
            os.getenv("METABOLIC_USE_VECTOR_DB") is not None
            and os.getenv("METABOLIC_DISABLE_VECTOR_DB") is None
        )
        self.use_graph_store = (
            os.getenv("METABOLIC_USE_GRAPH_DB") is not None
            and os.getenv("METABOLIC_DISABLE_GRAPH_DB") is None
        )

    # ------------------------------------------------------------------
    def run(self) -> IngestionResult:
        """Execute the ingestion pipeline."""

        markdown_dirs = list((self.data_root / "documents" / "parsed").glob("*"))
        if not markdown_dirs:
            raise FileNotFoundError("No parsed documents found under data/documents/parsed")

        chunks: List[Chunk] = []
        for doc_dir in markdown_dirs:
            LOGGER.info("Processing document directory: %s", doc_dir)
            for md_file in sorted(doc_dir.glob("*.md")):
                doc_chunks = self.chunker.chunk_markdown(doc_dir.name, md_file)
                for chunk in doc_chunks:
                    chunk.source_path = self._make_relative_path(chunk.source_path)
                    chunk.metadata.setdefault("document_id", chunk.document_id)
                chunks.extend(doc_chunks)

        if not chunks:
            return IngestionResult(0, 0, self.output_root / "chunks.jsonl", 0, 0)

        LOGGER.info("Generating embeddings for %s chunks", len(chunks))
        embeddings = self.embedding_provider.embed([chunk.text for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        output_path = self.output_root / "chunks.jsonl"
        with output_path.open("w", encoding="utf-8") as fout:
            for chunk in chunks:
                fout.write(json.dumps(chunk.as_record(), ensure_ascii=False) + "\n")

        vector_records = 0
        if self.use_vector_store and self.database_url:
            embedding_dim = self.embedding_provider._config.embedding_size
            with VectorStoreWriter(
                self.database_url,
                table=self.vector_table,
                embedding_dim=embedding_dim,
                index_threshold=self.vector_index_threshold,
            ) as writer:
                vector_records = writer.upsert_chunks(chunks)
                LOGGER.info(
                    "Persisted %s records to pgvector table %s", vector_records, self.vector_table
                )
        else:
            LOGGER.info("Vector store persistence disabled or not configured")

        graph_records = 0
        if self.use_graph_store and self.neo4j_uri and self.neo4j_user and self.neo4j_password:
            graph_writer = GraphitiWriter(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
            graph_records = graph_writer.upsert_chunks(chunks)
            LOGGER.info("Persisted %s episodes to Graphiti", graph_records)
        else:
            LOGGER.info("Graphiti persistence disabled or not configured")

        return IngestionResult(
            total_documents=len(markdown_dirs),
            total_chunks=len(chunks),
            output_path=output_path,
            vector_records=vector_records,
            graph_records=graph_records,
        )

    # ------------------------------------------------------------------
    def _make_relative_path(self, source_path: str) -> str:
        path = Path(source_path)
        try:
            return str(path.relative_to(self.data_root))
        except ValueError:
            return path.name


def iter_chunks() -> Iterator[Chunk]:
    """Utility generator yielding chunks from the current cache."""

    settings = get_settings()
    cache_path = settings.cache_root / "vector_store" / "chunks.jsonl"
    if not cache_path.exists():
        return iter(())

    def _load() -> Iterable[Chunk]:
        with cache_path.open("r", encoding="utf-8") as fin:
            for line in fin:
                payload = json.loads(line)
                if "metadata" not in payload:
                    payload["metadata"] = {}
                yield Chunk(**payload)

    return iter(_load())


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    pipeline = IngestionPipeline()
    result = pipeline.run()
    LOGGER.info(
        "Ingestion complete: %s documents -> %s chunks (output: %s)",
        result.total_documents,
        result.total_chunks,
        result.output_path,
    )
