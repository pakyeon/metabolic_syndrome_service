import unittest

from metabolic_backend.analysis.classifier import QuestionAnalysisResult, SafetyLevel
from metabolic_backend.orchestrator.guardrails import (
    append_caution_guidance,
    build_safety_envelope,
    scrub_text,
)
from metabolic_backend.orchestrator.pipeline import RetrievalOutput
from metabolic_backend.orchestrator.api import serialize_retrieval_output


class GuardrailTests(unittest.TestCase):
    def _analysis(self, level: SafetyLevel) -> QuestionAnalysisResult:
        return QuestionAnalysisResult(
            domain="medical",
            complexity="simple",
            safety=level,
            reasons=["unit-test"],
            latency_ms=12.0,
        )

    def test_build_safety_envelope_escalate(self) -> None:
        envelope = build_safety_envelope(self._analysis(SafetyLevel.ESCALATE))
        self.assertEqual(envelope.level, SafetyLevel.ESCALATE)
        self.assertIn("Consult the attending physician", envelope.escalation_copy)
        self.assertIsNotNone(envelope.answer_override)

    def test_append_caution_guidance(self) -> None:
        envelope = build_safety_envelope(self._analysis(SafetyLevel.CAUTION))
        answer = "생활습관 교육을 강조하세요."
        updated = append_caution_guidance(answer, envelope)
        self.assertIn(envelope.escalation_copy, updated)

    def test_scrub_text_masks_pii(self) -> None:
        raw = "문의: honggildong@example.com / 010-1234-5678"
        scrubbed = scrub_text(raw)
        self.assertNotIn("example.com", scrubbed)
        self.assertNotIn("010-1234-5678", scrubbed)
        self.assertIn("[REDACTED]", scrubbed)

    def test_serialize_retrieval_output(self) -> None:
        analysis = self._analysis(SafetyLevel.CLEAR)
        envelope = build_safety_envelope(analysis)
        output = RetrievalOutput(
            analysis=analysis,
            answer="테스트 응답",
            citations=["[doc-1]"],
            observations=["Thought: test"],
            safety=envelope,
            timings={"analysis": 0.01, "total": 0.02},
            evidence=[],
        )
        payload = serialize_retrieval_output(output)
        self.assertEqual(payload["analysis"]["safety"], "clear")
        self.assertEqual(payload["answer"], "테스트 응답")
        self.assertEqual(payload["safety"]["level"], "clear")


if __name__ == "__main__":
    unittest.main()
