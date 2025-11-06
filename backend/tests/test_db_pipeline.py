"""Tests covering automatic DB provisioning and ingestion pipeline behaviour."""

from __future__ import annotations

import os
import tempfile
import types
from pathlib import Path
import unittest
from unittest import mock

from metabolic_backend.ingestion.models import Chunk
from metabolic_backend.ingestion import stores as stores_module
from metabolic_backend.ingestion.pipeline import IngestionPipeline


class _FakeCursor:
    """Lightweight cursor that records executed SQL statements."""

    def __init__(self, connection: "_FakeConnection", table_name: str) -> None:
        self._connection = connection
        self._table_name = table_name
        self.rowcount = 0
        self._last_query = ""

    # Context manager helpers -------------------------------------------------
    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    # psycopg cursor API ------------------------------------------------------
    def execute(self, sql: str, params=None) -> None:  # noqa: ANN001 - psycopg parity
        normalized = " ".join(sql.split())
        self._last_query = normalized
        self._connection.commands.append((normalized, params))
        self.rowcount = 1 if normalized.upper().startswith("INSERT") else 0

    def fetchone(self):  # noqa: ANN001 - psycopg parity
        if f"COUNT(*) FROM {self._table_name}" in self._last_query:
            return (5,)
        if "FROM pg_indexes" in self._last_query:
            return (0,)
        return None


class _FakeConnection:
    """Minimal psycopg connection used for testing."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        self.commands: list[tuple[str, object]] = []
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self, self.table_name)

    def close(self) -> None:
        self.closed = True


class VectorStoreWriterTests(unittest.TestCase):
    """Unit tests exercising VectorStoreWriter auto-provisioning."""

    def test_schema_and_index_are_created_on_connect(self) -> None:
        table_name = "test_chunks"
        fake_connection = _FakeConnection(table_name)

        def fake_connect(dsn: str, autocommit: bool = True):  # noqa: ARG001
            fake_connection.dsn = dsn
            fake_connection.autocommit = autocommit
            return fake_connection

        fake_psycopg = types.SimpleNamespace(connect=fake_connect)

        with (
            mock.patch.object(stores_module, "psycopg", fake_psycopg),
            mock.patch.object(stores_module, "register_vector", lambda conn: None),
        ):
            writer = stores_module.VectorStoreWriter(
                "postgresql://stub", table=table_name, embedding_dim=3, index_threshold=1
            )

            chunk = Chunk(
                chunk_id="doc:chunk:0001",
                document_id="doc",
                section_path=["intro"],
                source_path="doc.md",
                text="Example chunk text.",
                token_count=12,
                embedding=[0.1, 0.2, 0.3],
                metadata={"heading": "Intro"},
            )

            with writer:
                inserted = writer.upsert_chunks([chunk])

        self.assertEqual(inserted, 1)
        self.assertTrue(fake_connection.closed)

        normalized_sql = [sql for sql, _ in fake_connection.commands]

        self.assertTrue(
            any(f"CREATE TABLE IF NOT EXISTS {table_name}" in sql for sql in normalized_sql),
            "VectorStoreWriter should create the chunks table automatically.",
        )
        self.assertTrue(
            any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in normalized_sql),
            "pgvector extension should be created on first connect.",
        )
        self.assertTrue(
            any(
                f"CREATE INDEX IF NOT EXISTS {table_name}_embedding_hnsw_idx" in sql
                for sql in normalized_sql
            ),
            "Vector index should be created when chunk threshold is met.",
        )


class _FakeVectorWriter:
    instances: list["_FakeVectorWriter"] = []

    def __init__(self, dsn: str, **kwargs) -> None:  # noqa: ANN001 - parity with real writer
        self.dsn = dsn
        self.kwargs = kwargs
        self.upserts: list[list[Chunk]] = []
        self.entered = False
        self.was_entered = False
        _FakeVectorWriter.instances.append(self)

    def __enter__(self) -> "_FakeVectorWriter":
        self.entered = True
        self.was_entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.entered = False

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        captured = [chunk for chunk in chunks]
        self.upserts.append(captured)
        return len(captured)


class _FakeGraphWriter:
    instances: list["_FakeGraphWriter"] = []

    def __init__(
        self, uri: str, user: str, password: str, **kwargs
    ) -> None:  # noqa: ANN001 - parity
        self.uri = uri
        self.user = user
        self.password = password
        self.kwargs = kwargs
        self.upserts: list[list[Chunk]] = []
        _FakeGraphWriter.instances.append(self)

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        captured = [chunk for chunk in chunks]
        self.upserts.append(captured)
        return len(captured)


class IngestionPipelineNeonTests(unittest.TestCase):
    """Integration-style tests ensuring ingestion pushes to both stores."""

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

        _FakeVectorWriter.instances.clear()
        _FakeGraphWriter.instances.clear()

    def tearDown(self) -> None:
        _FakeVectorWriter.instances.clear()
        _FakeGraphWriter.instances.clear()
        self._tmpdir.cleanup()

    def test_pipeline_publishes_chunks_to_neon_and_graphiti(self) -> None:
        def fake_chunk_markdown(
            self, document_id, md_path, *, content=None, starting_index=0
        ):  # noqa: ANN001, D401
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

        def fake_embed(self, texts):  # noqa: ANN001 - match EmbeddingProvider signature
            return [[0.1, 0.2, 0.3] for _ in texts]

        env_overrides = {
            "DATA_ROOT": str(self.data_root),
            "CACHE_ROOT": str(self.cache_root),
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/metabolic",
            "USE_VECTOR_DB": "1",
            "USE_GRAPH_DB": "1",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "secret",
            "EMBEDDING_BACKEND": "offline",
        }

        # Ensure disable flags from other tests do not leak into this run
        os.environ.pop("DISABLE_VECTOR_DB", None)
        os.environ.pop("DISABLE_GRAPH_DB", None)

        with (
            mock.patch.dict(os.environ, env_overrides, clear=False),
            mock.patch(
                "metabolic_backend.ingestion.pipeline.SemanticChunker.chunk_markdown",
                new=fake_chunk_markdown,
            ),
            mock.patch(
                "metabolic_backend.ingestion.pipeline.EmbeddingProvider.embed", new=fake_embed
            ),
            mock.patch(
                "metabolic_backend.ingestion.pipeline.VectorStoreWriter", new=_FakeVectorWriter
            ),
            mock.patch("metabolic_backend.ingestion.pipeline.GraphitiWriter", new=_FakeGraphWriter),
        ):
            pipeline = IngestionPipeline(data_root=self.data_root, output_root=self.cache_root)
            result = pipeline.run()

        self.assertEqual(result.total_chunks, 1)
        self.assertEqual(result.vector_records, 1)
        self.assertEqual(result.graph_records, 1)
        self.assertTrue(
            result.output_path.exists(), "Ingestion pipeline should emit chunks.jsonl cache."
        )

        self.assertTrue(_FakeVectorWriter.instances, "Vector writer should be instantiated.")
        vector_writer = _FakeVectorWriter.instances[0]
        self.assertEqual(vector_writer.dsn, env_overrides["DATABASE_URL"])
        self.assertTrue(
            vector_writer.was_entered, "Vector writer context manager should be entered."
        )
        self.assertEqual(len(vector_writer.upserts), 1)
        self.assertEqual(vector_writer.upserts[0][0].embedding, [0.1, 0.2, 0.3])

        self.assertTrue(_FakeGraphWriter.instances, "Graphiti writer should be instantiated.")
        graph_writer = _FakeGraphWriter.instances[0]
        self.assertEqual(len(graph_writer.upserts), 1)
        self.assertEqual(graph_writer.uri, env_overrides["NEO4J_URI"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
