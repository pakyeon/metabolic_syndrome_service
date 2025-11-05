"use client";

import { useCopilotChat } from "@copilotkit/react-core";
import { useEffect, useMemo, useRef, useState } from "react";

export type TransparencyItem = {
  type: "Thought" | "Action" | "Observation";
  title: string;
  detail: string;
};

type Mode = "preparation" | "live";

type RawCopilotMessage = {
  id?: string | number;
  role?: unknown;
  content?: unknown;
  metadata?: Record<string, unknown> | null;
  title?: unknown;
  name?: unknown;
};

const fallbackScript: TransparencyItem[] = [
  {
    type: "Thought",
    title: "질문 분석 중...",
    detail: "도메인: 운동 · 복잡도: 중간"
  },
  {
    type: "Action",
    title: "Vector + Graph 검색 실행",
    detail: "운동 가이드라인 3건, 야간 근무 케이스 2건 수집"
  },
  {
    type: "Observation",
    title: "잠정 근거 확보",
    detail: "허리둘레 증가 ↔ 수면 패턴 연관 문서를 강조"
  },
  {
    type: "Action",
    title: "안전 키워드 감지",
    detail: "가슴 두근거림 → 의사 상담 권고 문구 포함"
  },
  {
    type: "Observation",
    title: "답변 생성",
    detail: "긍정 프레이밍 + 에스컬레이션 배너 준비"
  }
];

const FALLBACK_THOUGHT_LABEL = "사고 단계";
const FALLBACK_ACTION_LABEL = "도구 실행";
const FALLBACK_OBSERVATION_LABEL = "중간 결과";

const metadataTitleCandidates = ["title", "label", "name", "stage", "summary"];

function coerceText(content: unknown): string {
  if (typeof content === "string") {
    return content.trim();
  }

  if (Array.isArray(content)) {
    return content
      .map((chunk) => coerceText(chunk))
      .filter(Boolean)
      .join(" ")
      .trim();
  }

  if (content && typeof content === "object") {
    const candidate = (content as { text?: unknown; value?: unknown; content?: unknown }).text
      ?? (content as { text?: unknown; value?: unknown; content?: unknown }).value
      ?? (content as { text?: unknown; value?: unknown; content?: unknown }).content;
    if (typeof candidate === "string") {
      return candidate.trim();
    }
  }

  return "";
}

function pickMetadataLabel(
  metadata: Record<string, unknown> | null | undefined,
  fallbackValue: unknown,
  defaultLabel: string
): string {
  if (typeof fallbackValue === "string" && fallbackValue.trim().length > 0) {
    return fallbackValue.trim();
  }

  if (!metadata) {
    return defaultLabel;
  }

  for (const key of metadataTitleCandidates) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }

  const activity = metadata["activity"];
  if (activity && typeof activity === "object") {
    for (const key of metadataTitleCandidates) {
      const nestedValue = (activity as Record<string, unknown>)[key];
      if (typeof nestedValue === "string" && nestedValue.trim().length > 0) {
        return nestedValue.trim();
      }
    }
  }

  return defaultLabel;
}

function normalizeRole(role: unknown): string {
  return typeof role === "string" ? role.toLowerCase() : "";
}

function mapAguiMessages(messages: RawCopilotMessage[]): TransparencyItem[] {
  const timeline: TransparencyItem[] = [];
  const seen = new Set<string>();

  messages.forEach((message, index) => {
    const role = normalizeRole(message.role);
    if (!role) {
      return;
    }

    const metadata = message.metadata ?? null;
    const detail = coerceText(message.content);
    if (!detail) {
      return;
    }

    const baseKey = typeof message.id === "string" || typeof message.id === "number"
      ? `${role}:${String(message.id)}`
      : `${role}:${index}`;

    if (seen.has(baseKey)) {
      return;
    }
    seen.add(baseKey);

    if (role === "reasoning") {
      timeline.push({
        type: "Thought",
        title: pickMetadataLabel(metadata, message.title ?? message.name, FALLBACK_THOUGHT_LABEL),
        detail
      });
      return;
    }

    if (role === "tool" || role === "action") {
      timeline.push({
        type: "Action",
        title: pickMetadataLabel(metadata, message.title ?? message.name, FALLBACK_ACTION_LABEL),
        detail
      });
      return;
    }

    if (role === "assistant" || role === "observation") {
      timeline.push({
        type: "Observation",
        title: pickMetadataLabel(metadata, message.title ?? message.name, FALLBACK_OBSERVATION_LABEL),
        detail
      });
    }
  });

  return timeline;
}

/**
 * Hook to expose the CopilotKit transparency stream (Thought/Action/Observation).
 * Maps AG-UI reasoning/action messages when available and falls back to a scripted
 * sequence for local prototypes.
 */
export function useTransparencyStream(mode: Mode, override?: TransparencyItem[] | null) {
  const copilot = useCopilotChat();

  const aguiTimeline = useMemo<TransparencyItem[]>(() => {
    if (override && override.length > 0) {
      return override;
    }
    const rawMessages = Array.isArray(copilot.visibleMessages) ? (copilot.visibleMessages as RawCopilotMessage[]) : [];
    return mapAguiMessages(rawMessages);
  }, [copilot.visibleMessages, override]);

  const hasAguiTimeline = aguiTimeline.length > 0;
  const events = hasAguiTimeline ? aguiTimeline : fallbackScript;

  const [activeIndex, setActiveIndex] = useState(0);
  const [resetToken, setResetToken] = useState(0);
  const previousLengthRef = useRef(0);

  useEffect(() => {
    if (mode !== "live") {
      setActiveIndex(hasAguiTimeline ? Math.max(aguiTimeline.length - 1, 0) : 0);
      previousLengthRef.current = events.length;
      return;
    }

    if (!hasAguiTimeline) {
      setActiveIndex(0);
      let step = 0;
      const timer = setInterval(() => {
        step = Math.min(step + 1, events.length - 1);
        setActiveIndex(step);
        if (step === events.length - 1) {
          clearInterval(timer);
        }
      }, 2200);

      return () => clearInterval(timer);
    }

    const currentLength = aguiTimeline.length;
    const hasNewEvent = currentLength !== previousLengthRef.current;
    if (hasNewEvent) {
      setActiveIndex(Math.max(currentLength - 1, 0));
      previousLengthRef.current = currentLength;
    }
  }, [mode, events, hasAguiTimeline, aguiTimeline.length, resetToken]);

  useEffect(() => {
    previousLengthRef.current = events.length;
  }, [events.length]);

  const reset = () => {
    setActiveIndex(0);
    setResetToken((token) => token + 1);
    previousLengthRef.current = hasAguiTimeline ? aguiTimeline.length : events.length;
  };

  return { events, activeIndex, reset };
}
