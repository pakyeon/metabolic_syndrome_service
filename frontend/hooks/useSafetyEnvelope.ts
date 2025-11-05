"use client";

import { useCopilotChat } from "@copilotkit/react-core";
import { useMemo } from "react";
import { TransparencyItem } from "./useTransparencyStream";

export type SafetyLevel = "clear" | "caution" | "escalate";

export type SafetyBannerState = {
  level: SafetyLevel;
  headline: string;
  body: string;
  escalationCopy: string;
  shouldShow: boolean;
};

type RawMessage = {
  role?: unknown;
  metadata?: Record<string, unknown> | null;
  content?: unknown;
  guardrail?: unknown;
};

type EnvelopeCandidate = {
  level?: unknown;
  bannerTitle?: unknown;
  bannerBody?: unknown;
  title?: unknown;
  body?: unknown;
  message?: unknown;
  escalationCopy?: unknown;
  escalationMessage?: unknown;
  guidance?: unknown;
  requiresEscalation?: unknown;
  severity?: unknown;
};

const ESCALATION_SENTENCE_EN = "Consult the attending physician.";
const ESCALATION_SENTENCE_KO = "담당 의사와 반드시 상담해 주세요.";

const DEFAULT_CLEAR: SafetyBannerState = {
  level: "clear",
  headline: "",
  body: "",
  escalationCopy: "",
  shouldShow: false
};

function normalizeBannerState(state: SafetyBannerState): SafetyBannerState {
  return {
    level: state.level,
    headline: state.headline,
    body: state.body,
    escalationCopy: state.escalationCopy,
    shouldShow: state.level !== "clear" && state.shouldShow !== false
  };
}
function coerceString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function coerceBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return ["true", "1", "yes", "y"].includes(value.toLowerCase());
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  return false;
}

function coerceLevel(value: unknown): SafetyLevel | null {
  if (typeof value === "string") {
    const normalized = value.toLowerCase();
    if (["escalate", "high", "critical", "block"].includes(normalized)) {
      return "escalate";
    }
    if (["caution", "warn", "warning", "medium", "watch"].includes(normalized)) {
      return "caution";
    }
    if (["clear", "low", "ok", "none"].includes(normalized)) {
      return "clear";
    }
  }
  if (typeof value === "number") {
    if (value >= 0.8) {
      return "escalate";
    }
    if (value >= 0.4) {
      return "caution";
    }
    return "clear";
  }
  if (typeof value === "boolean") {
    return value ? "escalate" : "clear";
  }
  return null;
}

function unwrapEnvelope(candidate: unknown): EnvelopeCandidate | null {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  return candidate as EnvelopeCandidate;
}

function extractEnvelopeFromMetadata(metadata: Record<string, unknown> | null | undefined): SafetyBannerState | null {
  if (!metadata) {
    return null;
  }

  const directCandidate = unwrapEnvelope(metadata.guardrail ?? metadata.safety ?? metadata.safetyEnvelope ?? metadata);
  const level =
    coerceLevel(directCandidate?.level ?? metadata.safetyLevel ?? metadata.level ?? metadata.status) ??
    (coerceBoolean(directCandidate?.requiresEscalation ?? metadata.requiresEscalation) ? "escalate" : null) ??
    coerceLevel(directCandidate?.severity);

  if (!level) {
    return null;
  }

  const headline =
    coerceString(directCandidate?.bannerTitle ?? directCandidate?.title ?? metadata.bannerTitle ?? metadata.title) ||
    (level === "escalate" ? "의료 에스컬레이션 필요" : level === "caution" ? "의학적 주의가 필요한 내용" : "");

  const body =
    coerceString(directCandidate?.bannerBody ?? directCandidate?.body ?? directCandidate?.message ?? metadata.message) ||
    (level === "escalate"
      ? "이 질문은 의료 전문가의 직접적인 판단이 필요한 주제입니다."
      : level === "caution"
      ? "상담 시 근거를 공유하며 의료진 확인이 필요함을 함께 안내하세요."
      : "");

  const escalationCopy =
    coerceString(
      directCandidate?.escalationCopy ?? directCandidate?.escalationMessage ?? directCandidate?.guidance ?? metadata.guidance
    ) || `${ESCALATION_SENTENCE_KO} ${ESCALATION_SENTENCE_EN}`;

  return {
    level,
    headline,
    body,
    escalationCopy,
    shouldShow: level !== "clear"
  };
}

function detectFromTimeline(timeline: TransparencyItem[]): SafetyLevel | null {
  if (timeline.some((event) => event.detail.toLowerCase().includes("safety_escalation"))) {
    return "escalate";
  }
  if (
    timeline.some(
      (event) =>
        event.type === "Observation" &&
        (event.detail.includes("의사") || event.detail.toLowerCase().includes("escalation"))
    )
  ) {
    return "caution";
  }
  return null;
}

function detectFromDraft(draft: string): SafetyLevel | null {
  if (!draft) {
    return null;
  }
  const lower = draft.toLowerCase();
  if (/[0-9]{2,}\s?(mg|mmhg)/.test(lower) || lower.includes("약") || lower.includes("처방")) {
    return "escalate";
  }
  if (lower.includes("혈당") || lower.includes("수치") || lower.includes("위험")) {
    return "caution";
  }
  return null;
}

function detectFromContent(messages: RawMessage[]): SafetyLevel | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (typeof message.role === "string" && message.role !== "assistant") {
      continue;
    }
    const content = coerceString((message as { content?: string }).content);
    if (!content) {
      continue;
    }
    if (content.includes("담당 의사") || content.toLowerCase().includes("consult the attending physician")) {
      return "escalate";
    }
  }
  return null;
}

export function useSafetyEnvelope(
  transparencyEvents: TransparencyItem[],
  draftPrompt: string,
  override?: Partial<SafetyBannerState> | null
): SafetyBannerState {
  const { visibleMessages } = useCopilotChat();

  return useMemo(() => {
    if (override && override.level) {
      return normalizeBannerState({
        level: override.level,
        headline: override.headline ?? "",
        body: override.body ?? "",
        escalationCopy: override.escalationCopy ?? `${ESCALATION_SENTENCE_KO} ${ESCALATION_SENTENCE_EN}`,
        shouldShow: override.shouldShow ?? override.level !== "clear"
      });
    }

    const messages = Array.isArray(visibleMessages) ? (visibleMessages as RawMessage[]) : [];

    for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
      const candidate = extractEnvelopeFromMetadata(messages[idx].metadata);
      if (candidate) {
        return normalizeBannerState(candidate);
      }
    }

    const timelineLevel = detectFromTimeline(transparencyEvents);
    if (timelineLevel) {
      return normalizeBannerState({
        level: timelineLevel,
        headline: timelineLevel === "escalate" ? "의료 에스컬레이션 필요" : "의학적 주의가 필요한 내용",
        body:
          timelineLevel === "escalate"
            ? "이 질문은 의료 전문가의 판단이 필요합니다."
            : "의료진 확인을 함께 안내하세요.",
        escalationCopy: `${ESCALATION_SENTENCE_KO} ${ESCALATION_SENTENCE_EN}`,
        shouldShow: true
      });
    }

    const draftLevel = detectFromDraft(draftPrompt);
    if (draftLevel) {
      return normalizeBannerState({
        level: draftLevel,
        headline: draftLevel === "escalate" ? "의료 에스컬레이션 필요" : "의학적 주의가 필요한 내용",
        body:
          draftLevel === "escalate"
            ? "상담사는 즉시 의료진에게 상담을 연결해야 합니다."
            : "근거 자료와 함께 의료진 확인을 권장하세요.",
        escalationCopy: `${ESCALATION_SENTENCE_KO} ${ESCALATION_SENTENCE_EN}`,
        shouldShow: true
      });
    }

    const contentLevel = detectFromContent(messages);
    if (contentLevel) {
      return normalizeBannerState({
        level: contentLevel,
        headline: contentLevel === "escalate" ? "의료 에스컬레이션 필요" : "의학적 주의가 필요한 내용",
        body:
          contentLevel === "escalate"
            ? "답변에는 의료진 상담 권고가 포함되어 있습니다."
            : "의료진 확인을 함께 안내하세요.",
        escalationCopy: `${ESCALATION_SENTENCE_KO} ${ESCALATION_SENTENCE_EN}`,
        shouldShow: true
      });
    }

    return DEFAULT_CLEAR;
  }, [visibleMessages, transparencyEvents, draftPrompt, override]);
}
