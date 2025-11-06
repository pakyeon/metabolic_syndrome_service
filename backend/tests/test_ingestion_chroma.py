"""Tests covering Chroma vector store integration within the ingestion pipeline."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from metabolic_backend.ingestion.models import Chunk
from metabolic_backend.ingestion.pipeline import IngestionPipeline


class _FakeChromaStore:
    instances: list["_FakeChromaStore"] = []

    def __init__(self, persist_directory, collection_name, embedding_client):  # noqa: ANN001
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.embedding_client = embedding_client
        self.upserts: list[list[Chunk]] = []
        self.force_rebuild_flags: list[bool] = []
        _FakeChromaStore.instances.append(self)

    def upsert_chunks(self, chunks, *, force_rebuild=False):  # noqa: ANN001
        captured = [chunk for chunk in chunks]
        self.upserts.append(captured)
        self.force_rebuild_flags.append(force_rebuild)
        return len(captured)

    def stats(self) -> dict:
        count = sum(len(batch) for batch in self.upserts)
        return {"documents": count}


class _FakeGraphWriter:
    instances: list["_FakeGraphWriter"] = []

    def __init__(self, uri: str, user: str, password: str, **kwargs) -> None:  # noqa: ANN001
        self.uri = uri
        self.user = user
        self.password = password
        self.kwargs = kwargs
        self.upserts: list[list[Chunk]] = []
        _FakeGraphWriter.instances.append(self)

    def upsert_chunks(self, chunks):  # noqa: ANN001
        captured = [chunk for chunk in chunks]
        self.upserts.append(captured)
        return len(captured)


class IngestionPipelineChromaTests(unittest.TestCase):
    """Integration-style tests ensuring ingestion pushes to Chroma and Graphiti."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._tmpdir.name)

        # Minimal document tree expected by the ingestion pipeline
        self.data_root = self.temp_path / "data"
        doc_dir = self.data_root / "documents" / "parsed" / "guideline"
        doc_dir.mkdir(parents=True, exist_ok=True)
        self.doc_path = doc_dir / "metabolic.md"
        self.doc_path.write_text("# Title\n\n운동과 식단 관리 예시.", encoding="utf-8")

        self.cache_root = self.temp_path / "cache"
        self.cache_root.mkdir(parents=True, exist_ok=True)

        _FakeChromaStore.instances.clear()
        _FakeGraphWriter.instances.clear()

    def tearDown(self) -> None:
        _FakeChromaStore.instances.clear()
        _FakeGraphWriter.instances.clear()
        self._tmpdir.cleanup()

    def test_pipeline_publishes_chunks_to_chroma_and_graphiti(self) -> None:
        def fake_chunk_markdown(self, document_id, md_path, *, content=None, starting_index=0):  # noqa: ANN001, D401
            return [
                Chunk(
                    chunk_id=f"{document_id}:{md_path.stem}:0000",
                    document_id=document_id,
                    section_path=["Title"],
                    source_path=str(md_path),
                    text="운동과 식단 개선을 병행하세요.",
                    token_count=24,
                    metadata={"heading": "Title"},
                )
            ]

        class _FakeEmbeddingClient:
            def embed_batch(self, texts):  # noqa: ANN001 - signature parity
                return [[0.1, 0.2, 0.3] for _ in texts]

            def embed_text(self, text):  # noqa: ANN001 - signature parity
                return [0.1, 0.2, 0.3]

        env_overrides = {
            "DATA_ROOT": str(self.data_root),
            "CACHE_ROOT": str(self.cache_root),
            "CHROMA_PERSIST_DIR": str(self.cache_root / "chroma"),
            "CHROMA_COLLECTION": "test_collection",
            "USE_VECTOR_DB": "1",
            "USE_GRAPH_DB": "1",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "secret",
        }

        with (
            mock.patch.dict(os.environ, env_overrides, clear=False),
            mock.patch(
                "metabolic_backend.ingestion.pipeline.SemanticChunker.chunk_markdown",
                new=fake_chunk_markdown,
            ),
            mock.patch(
                "metabolic_backend.ingestion.pipeline.ChromaVectorStore",
                new=_FakeChromaStore,
            ),
            mock.patch(
                "metabolic_backend.ingestion.pipeline.GraphitiWriter",
                new=_FakeGraphWriter,
            ),
        ):
            pipeline = IngestionPipeline(
                data_root=self.data_root,
                output_root=self.cache_root,
                embedding_client=_FakeEmbeddingClient(),
            )
            result = pipeline.run()

        self.assertEqual(result.total_chunks, 1)
        self.assertEqual(result.vector_records, 1)
        self.assertEqual(result.graph_records, 1)
        self.assertTrue(
            result.output_path.exists(), "Ingestion pipeline should emit chunks.jsonl cache."
        )

        self.assertTrue(_FakeChromaStore.instances, "Chroma store should be instantiated.")
        chroma_store = _FakeChromaStore.instances[0]
        self.assertEqual(len(chroma_store.upserts), 1)
        self.assertEqual(len(chroma_store.upserts[0]), 1)
        self.assertEqual(chroma_store.collection_name, env_overrides["CHROMA_COLLECTION"])

        self.assertTrue(_FakeGraphWriter.instances, "Graphiti writer should be instantiated.")
        graph_writer = _FakeGraphWriter.instances[0]
        self.assertEqual(len(graph_writer.upserts), 1)
        self.assertEqual(graph_writer.uri, env_overrides["NEO4J_URI"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
