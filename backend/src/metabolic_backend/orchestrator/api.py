"""Serialization helpers for exposing RetrievalPipeline results via HTTP."""

from __future__ import annotations

from typing import Any, Dict

from .pipeline import RetrievalOutput


def serialize_retrieval_output(output: RetrievalOutput) -> Dict[str, Any]:
    """Convert retrieval output into a JSON-serializable payload."""

    # Handle both structured AG-UI messages and legacy string observations
    observations = []
    for obs in output.observations:
        if isinstance(obs, dict):
            # Structured AG-UI message
            observations.append({
                "role": obs.get("role", "observation"),
                "title": obs.get("title", ""),
                "content": obs.get("content", ""),
            })
        else:
            # Legacy string observation - parse it
            obs_str = str(obs)
            if ":" in obs_str:
                parts = obs_str.split(":", 1)
                role_hint = parts[0].strip().lower()
                content = parts[1].strip()
                if "thought" in role_hint:
                    observations.append({"role": "reasoning", "title": "분석", "content": content})
                elif "action" in role_hint:
                    observations.append({"role": "action", "title": "실행", "content": content})
                else:
                    observations.append({"role": "observation", "title": "관찰", "content": content})
            else:
                observations.append({"role": "observation", "title": "정보", "content": obs_str})

    result = {
        "analysis": {
            "domain": output.analysis.domain,
            "complexity": output.analysis.complexity,
            "safety": output.analysis.safety.value,
            "reasons": list(output.analysis.reasons),
            "latency_ms": output.analysis.latency_ms,
        },
        "answer": output.answer,
        "citations": list(output.citations),
        "observations": observations,
        "safety": {
            "level": output.safety.level.value,
            "bannerTitle": output.safety.banner_title,
            "bannerBody": output.safety.banner_body,
            "escalationCopy": output.safety.escalation_copy,
            "answerOverride": output.safety.answer_override,
        },
        "timings": {stage: value for stage, value in output.timings.items()},
        "evidence": [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "sectionPath": list(chunk.section_path),
                "source": chunk.source,
                "score": getattr(chunk, "score", None),
                "metadata": dict(chunk.metadata),
            }
            for chunk in output.evidence
        ],
    }

    # Add preparation analysis if present
    if output.preparation_analysis:
        prep = output.preparation_analysis
        result["preparationAnalysis"] = {
            "patientState": {
                "summary": prep.patient_state.summary,
                "keyMetrics": prep.patient_state.key_metrics,
                "concerns": prep.patient_state.concerns,
            },
            "consultationPattern": {
                "previousTopics": prep.consultation_pattern.previous_topics,
                "adherenceNotes": prep.consultation_pattern.adherence_notes,
                "difficulties": prep.consultation_pattern.difficulties,
            } if prep.consultation_pattern else None,
            "expectedQuestions": [
                {
                    "question": eq.question,
                    "recommendedAnswer": eq.recommended_answer,
                    "citations": eq.citations,
                    "evidenceCount": len(eq.evidence_chunks),
                }
                for eq in prep.expected_questions
            ],
            "deliveryExamples": [
                {
                    "topic": de.topic,
                    "technicalVersion": de.technical_version,
                    "patientFriendlyVersion": de.patient_friendly_version,
                    "framingNotes": de.framing_notes,
                }
                for de in prep.delivery_examples
            ],
            "warnings": prep.warnings,
        }

    return result
