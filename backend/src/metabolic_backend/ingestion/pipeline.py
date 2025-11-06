"""Document ingestion pipeline that prepares semantic chunks, embeddings, and persistence."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from ..config import get_settings
from ..embeddings import OpenAIEmbeddings
from .chunking import ChunkingConfig, SemanticChunker
from .models import Chunk
from .stores import ChromaVectorStore, GraphitiWriter

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
        embedding_client: OpenAIEmbeddings | None = None,
    ) -> None:
        settings = get_settings()
        self.data_root = data_root or settings.data_root
        cache_root = output_root or settings.cache_root
        self.output_root = cache_root / "vector_store"
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.chunker = SemanticChunker(chunk_config)
        self.embedding_client = embedding_client or OpenAIEmbeddings(
            model=settings.embedding_model
        )

        default_persist = settings.chroma_persist_dir
        persist_override = os.getenv("CHROMA_PERSIST_DIR")
        if persist_override:
            persist_path = Path(persist_override).expanduser()
            if not persist_path.is_absolute():
                persist_path = (self.output_root / persist_path).resolve()
        else:
            persist_path = default_persist
        self.chroma_persist_directory = persist_path
        self.chroma_collection = os.getenv("CHROMA_COLLECTION", "metabolic_chunks")
        self.force_vector_rebuild = os.getenv("VECTOR_FORCE_REBUILD") is not None
        self.neo4j_uri = os.getenv("NEO4J_URI", settings.neo4j_uri)
        self.neo4j_user = os.getenv("NEO4J_USER", settings.neo4j_user)
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", settings.neo4j_password)
        self.use_vector_store = (
            os.getenv("USE_VECTOR_DB") is not None and os.getenv("DISABLE_VECTOR_DB") is None
        )
        self.use_graph_store = (
            os.getenv("USE_GRAPH_DB") is not None and os.getenv("DISABLE_GRAPH_DB") is None
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
        embeddings = self.embedding_client.embed_batch([chunk.text for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        output_path = self.output_root / "chunks.jsonl"
        with output_path.open("w", encoding="utf-8") as fout:
            for chunk in chunks:
                fout.write(json.dumps(chunk.as_record(), ensure_ascii=False) + "\n")

        vector_records = 0
        if self.use_vector_store:
            try:
                chroma_store = ChromaVectorStore(
                    persist_directory=self.chroma_persist_directory,
                    collection_name=self.chroma_collection,
                    embedding_client=self.embedding_client,
                )
                vector_records = chroma_store.upsert_chunks(
                    chunks, force_rebuild=self.force_vector_rebuild
                )
                stats = chroma_store.stats()
                LOGGER.info(
                    "Persisted %s records to Chroma collection %s (total: %s)",
                    vector_records,
                    self.chroma_collection,
                    stats.get("documents"),
                )
            except Exception as exc:
                LOGGER.warning("Chroma persistence failed; skipping vector store update (%s)", exc)
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
