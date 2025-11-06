import os
import unittest

os.environ["DISABLE_INGESTION"] = "1"
os.environ.setdefault("DISABLE_VECTOR_DB", "1")
os.environ.setdefault("DISABLE_GRAPH_DB", "1")
os.environ.setdefault("EMBEDDING_BACKEND", "offline")

from fastapi.testclient import TestClient

from metabolic_backend.api import create_app


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app())

    def test_health_endpoint(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_retrieve_escalation(self) -> None:
        response = self.client.post("/v1/retrieve", json={"question": "약을 조절해도 될까요?"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["analysis"]["safety"], "escalate")
        self.assertEqual(payload["safety"]["level"], "escalate")
        self.assertIn("Consult the attending physician", payload["safety"]["escalationCopy"])
        self.assertTrue(payload["answer"])
        self.assertIn("timings", payload)
        self.assertIn("total", payload["timings"])

    def test_retrieve_rejects_blank(self) -> None:
        response = self.client.post("/v1/retrieve", json={"question": "   "})
        self.assertEqual(response.status_code, 422)

    def test_latency_metrics_endpoint(self) -> None:
        self.client.post("/v1/retrieve", json={"question": "약을 조절해도 될까요?"})
        metrics = self.client.get("/metrics/latency")
        self.assertEqual(metrics.status_code, 200)
        payload = metrics.json()
        self.assertIn("latency", payload)
        self.assertIn("total", payload["latency"])
        self.assertGreaterEqual(payload["latency"]["total"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
