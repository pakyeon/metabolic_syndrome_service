"""Safety guardrail utilities for counselor responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from ..analysis.classifier import QuestionAnalysisResult, SafetyLevel

ESCALATION_SENTENCE = (
    "This topic requires medical supervision. Consult the attending physician for any treatment decisions."
)
ESCALATION_SENTENCE_KO = (
    "의학적 판단이 필요한 주제입니다. 치료 결정은 반드시 담당 의사와 상의해 주세요."
)


@dataclass(slots=True)
class SafetyEnvelope:
    """Structured guardrail metadata returned alongside answers."""

    level: SafetyLevel
    banner_title: str
    banner_body: str
    escalation_copy: str
    answer_override: str | None = None


_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", flags=re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"\b(?:0\d{1,2}-?\d{3,4}-?\d{4})\b")
_RRN_PATTERN = re.compile(r"\b\d{6}-?\d{7}\b")
_ACCOUNT_PATTERN = re.compile(r"\b\d{3,4}-\d{3,4}-\d{3,4}\b")
_NAME_TAG_PATTERN = re.compile(r"(?:이름|성명)\s*[:：]\s*[가-힣]{2,4}")
_PATTERNS = [_EMAIL_PATTERN, _PHONE_PATTERN, _RRN_PATTERN, _ACCOUNT_PATTERN, _NAME_TAG_PATTERN]


def build_safety_envelope(analysis: QuestionAnalysisResult) -> SafetyEnvelope:
    """Map classifier output to counselor-facing guardrail messaging."""

    if analysis.safety is SafetyLevel.ESCALATE:
        override = (
            "현재 질문은 의학적 판단이 필요한 주제입니다. 일반적인 생활 정보를 제외한 구체적인 답변은 제공할 수 없으며, "
            "필수 안내: 담당 의사와 즉시 상담해 주세요. (Consult the attending physician.)"
        )
        return SafetyEnvelope(
            level=analysis.safety,
            banner_title="의료 에스컬레이션 필요",
            banner_body="이 질문은 의료 전문가의 직접적인 판단이 필요한 주제입니다.",
            escalation_copy=f"{ESCALATION_SENTENCE_KO} {ESCALATION_SENTENCE}",
            answer_override=override,
        )

    if analysis.safety is SafetyLevel.CAUTION:
        return SafetyEnvelope(
            level=analysis.safety,
            banner_title="의학적 주의가 필요한 내용",
            banner_body="상담 시 근거 자료를 강조하며 의료진 확인이 필요함을 함께 안내하세요.",
            escalation_copy=f"{ESCALATION_SENTENCE_KO} {ESCALATION_SENTENCE}",
        )

    return SafetyEnvelope(
        level=analysis.safety,
        banner_title="",
        banner_body="",
        escalation_copy="",
        answer_override=None,
    )


def scrub_text(value: str) -> str:
    """Remove common PII tokens from counselor-facing output."""

    scrubbed = value
    for pattern in _PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed


def scrub_observations(observations: Sequence) -> List:
    """Scrub PII from trace events to keep counselor timeline compliant."""

    scrubbed = []
    for item in observations:
        if isinstance(item, dict):
            # Handle structured AG-UI messages
            scrubbed_item = item.copy()
            if "content" in scrubbed_item and isinstance(scrubbed_item["content"], str):
                scrubbed_item["content"] = scrub_text(scrubbed_item["content"])
            if "title" in scrubbed_item and isinstance(scrubbed_item["title"], str):
                scrubbed_item["title"] = scrub_text(scrubbed_item["title"])
            scrubbed.append(scrubbed_item)
        elif isinstance(item, str):
            # Handle legacy string observations
            scrubbed.append(scrub_text(item))
        else:
            # Pass through other types unchanged
            scrubbed.append(item)
    return scrubbed


def append_caution_guidance(answer: str, envelope: SafetyEnvelope) -> str:
    """Append escalation guidance when the classifier signals caution."""

    guidance = f"{envelope.escalation_copy}".strip()
    if not guidance:
        return answer

    if guidance in answer:
        return answer

    if answer.endswith("."):
        return f"{answer} {guidance}"

    return f"{answer}. {guidance}"

