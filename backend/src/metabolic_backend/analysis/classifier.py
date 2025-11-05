"""Heuristic question analysis and safety classification pipeline.

The implementation provides a lightweight, latency-aware classifier that labels
incoming counselor prompts with domain, complexity, and safety flags. The
heuristics are intentionally conservative—when in doubt, the classifier escalates
so that downstream components surface the "Consult the attending physician"
message required by AGENTS.md.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Sequence

from ..config import get_settings

LOGGER = logging.getLogger(__name__)


class SafetyLevel(str, Enum):
    CLEAR = "clear"
    CAUTION = "caution"
    ESCALATE = "escalate"


@dataclass(slots=True)
class QuestionAnalysisResult:
    """Structured output of the question analyzer."""

    domain: str
    complexity: str
    safety: SafetyLevel
    reasons: List[str]
    latency_ms: float


class QuestionAnalyzer:
    """Classify counselor prompts for routing and guardrails."""

    _DOMAIN_KEYWORDS = {
        "exercise": {"운동", "활동", "걷기", "조깅", "근력", "유산소"},
        "diet": {"식단", "음식", "칼로리", "식사", "영양", "탄수화물"},
        "medical": {"약", "처방", "복용", "약물", "증상", "통증"},
        "lifestyle": {"음주", "흡연", "스트레스", "수면", "생활"},
    }

    _SAFETY_ESCALATE = {
        r"\b약\b",
        r"\b처방\b",
        r"\b복용량\b",
        r"\b부작용\b",
        r"\b응급\b",
        r"\b통증\b",
        r"\b심장\b",
        r"혈압이\s*높",
        r"혈당이\s*위험",
    }

    _SAFETY_CAUTION = {
        r"\b질환\b",
        r"\b진단\b",
        r"\b위험\b",
        r"\b검사\b",
        r"\b수치\b",
        r"\b저혈당\b",
        r"\b고혈당\b",
    }

    _SAFETY_ESCALATE_KEYWORDS = {"약", "처방", "복용", "복용량", "응급", "심장", "약물"}
    _SAFETY_CAUTION_KEYWORDS = {"질환", "진단", "위험", "검사", "수치", "저혈당", "고혈당"}

    _COMPLEXITY_MULTI = {"그리고", "또", "동시에", "뿐만", "그러면", "만약"}

    def __init__(self, latency_budget: float | None = None) -> None:
        settings = get_settings()
        self.latency_budget = latency_budget or settings.safety_latency_budget

    # ------------------------------------------------------------------
    def analyze(self, question: str, *, context: str | None = None) -> QuestionAnalysisResult:
        start = time.perf_counter()
        text = question.strip()
        lowered = text.lower()
        reasons: List[str] = []

        domain = self._detect_domain(text, lowered, reasons)
        complexity = self._estimate_complexity(text, lowered, reasons)
        safety = self._detect_safety(text, lowered, reasons)

        latency_ms = (time.perf_counter() - start) * 1000
        if latency_ms > self.latency_budget * 1000:
            LOGGER.warning(
                "Question analysis exceeded latency budget %.2f ms > %.2f ms",
                latency_ms,
                self.latency_budget * 1000,
            )
            # Defensive escalation if classifier misbehaves
            safety = SafetyLevel.ESCALATE
            reasons.append("Latency budget exceeded")

        return QuestionAnalysisResult(
            domain=domain,
            complexity=complexity,
            safety=safety,
            reasons=reasons,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    def _detect_domain(self, text: str, lowered: str, reasons: List[str]) -> str:
        for domain, keywords in self._DOMAIN_KEYWORDS.items():
            if self._any_keyword(text, keywords):
                reasons.append(f"Domain keyword match: {domain}")
                return domain
        reasons.append("Defaulted to lifestyle domain")
        return "lifestyle"

    def _estimate_complexity(self, text: str, lowered: str, reasons: List[str]) -> str:
        if "?" in text and any(conn in text for conn in self._COMPLEXITY_MULTI):
            reasons.append("Detected multi-hop connectors")
            return "multi-hop"
        if text.count("?") > 1:
            reasons.append("Multiple questions detected")
            return "compound"
        if len(text.split()) > 30:
            reasons.append("Long question assumes compound context")
            return "compound"
        reasons.append("Classified as simple question")
        return "simple"

    def _detect_safety(self, text: str, lowered: str, reasons: List[str]) -> SafetyLevel:
        for keyword in self._SAFETY_ESCALATE_KEYWORDS:
            if keyword in text:
                reasons.append(f"Escalate keyword hit: {keyword}")
                return SafetyLevel.ESCALATE
        for pattern in self._SAFETY_ESCALATE:
            if re.search(pattern, text, flags=re.IGNORECASE):
                reasons.append(f"Escalate keyword hit: {pattern}")
                return SafetyLevel.ESCALATE
        for keyword in self._SAFETY_CAUTION_KEYWORDS:
            if keyword in text:
                reasons.append(f"Caution keyword hit: {keyword}")
                return SafetyLevel.CAUTION
        for pattern in self._SAFETY_CAUTION:
            if re.search(pattern, text, flags=re.IGNORECASE):
                reasons.append(f"Caution keyword hit: {pattern}")
                return SafetyLevel.CAUTION
        reasons.append("No safety flags detected")
        return SafetyLevel.CLEAR

    @staticmethod
    def _any_keyword(text: str, keywords: Iterable[str]) -> bool:
        return any(keyword in text for keyword in keywords)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    analyzer = QuestionAnalyzer()
    samples = [
        "환자가 약을 줄여도 되나요?",
        "기초운동은 얼마나 해야 할까요?",
        "혈당이 높은데 조깅을 해도 괜찮을까요?",
    ]
    for sample in samples:
        result = analyzer.analyze(sample)
        LOGGER.info("Sample: %s", sample)
        LOGGER.info(" -> %s", result)
