"""Integration test for retrieval pipeline with vector + graph backends."""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock
from dataclasses import replace
from typing import Dict, Optional

from fastapi.testclient import TestClient

# Provide a lightweight psycopg2 stub so importing the API module succeeds in
# environments where the driver is not installed during testing.
if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")

    def _stub_connect(*_args, **_kwargs):
        raise RuntimeError("psycopg2 stub activated during tests; install driver for DB access.")

    psycopg2_stub.connect = _stub_connect

    extras_stub = types.ModuleType("psycopg2.extras")

    class _RealDictCursor:  # minimal stand-in used only for type references
        pass

    extras_stub.RealDictCursor = _RealDictCursor
    psycopg2_stub.extras = extras_stub

    sys.modules["psycopg2"] = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub

from langchain_core.messages import AIMessage

from metabolic_backend.api import create_app
from metabolic_backend.ingestion.models import Chunk


class RetrievalPipelineIntegrationTest(unittest.TestCase):
    """Exercise the /v1/retrieve endpoint assuming external stores are populated."""

    @classmethod
    def setUpClass(cls) -> None:
        # Snapshot environment so we can restore after the suite finishes.
        cls._env_backup: Dict[str, Optional[str]] = {
            "DISABLE_VECTOR_DB": os.environ.pop("DISABLE_VECTOR_DB", None),
            "DISABLE_GRAPH_DB": os.environ.pop("DISABLE_GRAPH_DB", None),
        }

        os.environ.setdefault("DISABLE_INGESTION", "1")
        os.environ.setdefault("EMBEDDING_BACKEND", "offline")
        os.environ.setdefault("USE_VECTOR_DB", "1")
        os.environ.setdefault("USE_GRAPH_DB", "1")

        # Provide stub connection details so the pipeline believes databases exist.
        os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/dummy")
        os.environ.setdefault("NEO4J_URI", "neo4j://localhost:7687")
        os.environ.setdefault("NEO4J_USER", "neo4j")
        os.environ.setdefault("NEO4J_PASSWORD", "password")

        cls.vector_chunk = Chunk(
            chunk_id="vector:001",
            document_id="exercise-plan",
            section_path=["exercise", "walking"],
            source_path="knowledge/exercise.md",
            text="주 5회 30분 빠르게 걷기 운동을 권장합니다.",
            token_count=18,
            score=0.92,
            metadata={"retrieval": "vector_db"},
        )
        cls.graph_chunk = Chunk(
            chunk_id="graph:alpha",
            document_id="exercise-effects",
            section_path=["relationships", "glucose"],
            source_path="knowledge/relationships.md",
            text="유산소 운동은 혈당 감소에 긍정적인 영향을 줍니다.",
            token_count=20,
            score=0.88,
            metadata={"retrieval": "graph_db"},
        )

        class _StubEmbeddingClient:
            def __init__(self) -> None:
                self._vector = [0.1, 0.2, 0.3]

            def embed_text(self, text: str):  # noqa: ANN001 - signature parity
                return list(self._vector)

            def embed_batch(self, texts):  # noqa: ANN001 - signature parity
                return [list(self._vector) for _ in texts]

        class _StubLLM:
            def __init__(self, reply: str) -> None:
                self._reply = reply

            def invoke(self, messages):  # noqa: ANN001 - LangChain parity
                return AIMessage(content=self._reply)

        cls.small_llm = _StubLLM(
            "하위 질문 1: 걷기 운동 권장 시간은?\n하위 질문 2: 걷기 운동과 혈당의 관계는?"
        )
        cls.main_llm = _StubLLM(
            "걷기 운동은 주 5회 30분 이상 권장됩니다. (vector:001, graph:alpha)"
        )

        # Monkeypatch the retrievers so they return the prepared chunks without
        # reaching external services. We patch during class setup so that every
        # request issued by the TestClient uses the fake backends.
        cls._patchers = []

        async def fake_vector_async(self, query: str, limit: int = 5):
            return [cls._clone_chunk(cls.vector_chunk)]

        def fake_vector_sync(self, query: str, limit: int = 5):
            return [cls._clone_chunk(cls.vector_chunk)]

        async def fake_graph_async(self, query: str, limit: int = 5):
            return [cls._clone_chunk(cls.graph_chunk)]

        def fake_graph_sync(self, query: str, limit: int = 5):
            return [cls._clone_chunk(cls.graph_chunk)]

        cls._patchers.extend(
            [
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.VectorRetriever.retrieve_async",
                    new=fake_vector_async,
                ),
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.VectorRetriever.retrieve",
                    new=fake_vector_sync,
                ),
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.GraphRetriever.retrieve_async",
                    new=fake_graph_async,
                ),
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.GraphRetriever.retrieve",
                    new=fake_graph_sync,
                ),
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.get_small_llm",
                    return_value=cls.small_llm,
                ),
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.get_main_llm",
                    return_value=cls.main_llm,
                ),
                mock.patch(
                    "metabolic_backend.orchestrator.pipeline.OpenAIEmbeddings",
                    new=lambda *args, **kwargs: _StubEmbeddingClient(),
                ),
                mock.patch(
                    "metabolic_backend.retrievers.vector.OpenAIEmbeddings",
                    new=lambda *args, **kwargs: _StubEmbeddingClient(),
                ),
            ]
        )

        for patcher in cls._patchers:
            patcher.start()

        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls) -> None:
        for patcher in cls._patchers:
            patcher.stop()

        # Restore original environment values.
        for key, value in cls._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @staticmethod
    def _clone_chunk(chunk: Chunk) -> Chunk:
        clone = replace(chunk)
        clone.metadata = dict(chunk.metadata)
        return clone

    def test_retrieve_aggregates_vector_and_graph_evidence(self) -> None:
        """Ensure the API response includes evidence from both sources."""

        payload = {
            "question": "걷기 운동은 얼마나 해야 하나요? 혈당과 운동의 관계는 무엇인가요?",
            "mode": "live",
        }

        response = self.client.post("/v1/retrieve", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Evidence should include our synthetic vector and graph records.
        evidence = data.get("evidence", [])
        self.assertGreaterEqual(len(evidence), 2)
        retrieval_sources = {item["metadata"].get("retrieval") for item in evidence}
        self.assertIn("vector_db", retrieval_sources)
        self.assertIn("graph_db", retrieval_sources)

        # Retrieved answer should contain text and reference citations.
        self.assertTrue(data.get("answer", "").strip())
        citations = data.get("citations", [])
        self.assertTrue(any(ref.startswith("[vector") for ref in citations))
        self.assertTrue(any(ref.startswith("[graph") for ref in citations))


if __name__ == "__main__":
    unittest.main()
