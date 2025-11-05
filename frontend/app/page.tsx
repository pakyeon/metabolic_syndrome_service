"use client";

import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./workspace.module.css";
import { PatientSummary } from "../components/patient/PatientSummary";
import { ChatWorkspace } from "../components/chat/ChatWorkspace";
import { PreparationSidebar } from "../components/preparation/PreparationSidebar";
import { QuickActions, QuickAction } from "../components/actions/QuickActions";
import { ModeSwitch } from "../components/actions/ModeSwitch";
import { TransparencyItem, useTransparencyStream } from "../hooks/useTransparencyStream";
import { SafetyBannerState, useSafetyEnvelope } from "../hooks/useSafetyEnvelope";
import { useStreamingRetrieval, AGUIMessage } from "../hooks/useStreamingRetrieval";

const patient = {
  name: "김하늘",
  age: 52,
  visitDate: "2025-10-28",
  riskLevel: "moderate" as const,
  biomarkerHighlights: [
    {
      label: "공복 혈당",
      value: "124 mg/dL",
      status: "elevated" as const,
      guidance: "아침 조깅 전 간단한 간식과 주 3회 근력운동을 권장하세요."
    },
    {
      label: "허리둘레",
      value: "90 cm",
      status: "critical" as const,
      guidance: "생활습관 카드에 있는 스트레칭과 업무 중 2시간마다 5분 걷기를 강조하세요."
    },
    {
      label: "HDL 콜레스테롤",
      value: "46 mg/dL",
      status: "optimal" as const,
      guidance: "최근 상승 추세이므로 긍정적 피드백을 제공하고 지속을 격려하세요."
    }
  ],
  lifestyleHighlights: [
    {
      title: "활동 패턴",
      detail: "평일 만보 걷기 달성률 78%. 야간 근무 이후 회복이 늦어지는 경향."
    },
    {
      title: "식습관",
      detail: "야식 빈도 주 3회 → 주 1회로 감소. 단백질 위주의 간식 아이디어 제공 필요."
    }
  ]
};

type WorkspaceMessage = {
  id: string;
  role: "counselor" | "assistant";
  content: string;
  timestamp: string;
};

const demoConversation: WorkspaceMessage[] = [
  {
    id: "msg-1",
    role: "assistant" as const,
    content:
      "지난 상담에서 합의한 30분 걷기 목표를 2주 연속 달성했습니다. 유지 요인을 묻고 칭찬으로 시작해 보세요.",
    timestamp: "09:58"
  },
  {
    id: "msg-2",
    role: "counselor" as const,
    content: "오늘은 허리둘레 변화와 야간 근무 시 식사 전략을 집중 점검하고 싶어요.",
    timestamp: "09:59"
  },
  {
    id: "msg-3",
    role: "assistant" as const,
    content: "허리둘레 증가는 수면 패턴과도 연관될 수 있습니다. 야간 근무 직후 스트레칭 루틴을 제안해 보세요.",
    timestamp: "10:00"
  }
];

const prepCards = [
  {
    title: "야간 근무 후 혈당 관리 질문 예상",
    body: "‘야간 근무 끝나면 너무 피곤해서 바로 잠들고 싶은데 운동 대신 할 수 있는 게 있을까요?’",
    tag: "혈당"
  },
  {
    title: "골반 통증 관련 운동 허용 여부",
    body: "최근 물리치료 중이며, 허리 회전이 큰 운동을 피하라는 처방이 있었음. 완만한 스텝업을 대안으로 제안합니다.",
    tag: "운동"
  }
];

const observations = [
  {
    label: "스트레스 신호",
    detail: "설문에서 직장 스트레스 8/10 → 심호흡 루틴 및 짧은 명상 카드 리마인드",
    status: "warning" as const
  },
  {
    label: "복약 순응",
    detail: "메트포르민 복약률 96%로 안정. 긍정 피드백 제공",
    status: "ok" as const
  },
  {
    label: "의료 에스컬레이션",
    detail: "최근 가슴 두근거림 호소. 의사 상담 필요 여부 확인 질문 준비",
    status: "critical" as const
  }
];

const quickActions: QuickAction[] = [
  {
    id: "action-prep-overview",
    label: "상담 준비 요약",
    description: "주요 위험요인과 생활 습관 포인트 정리",
    prompt: "이번 상담에서 강조해야 할 핵심 위험요인과 생활 습관 포인트를 3가지로 요약해줘."
  },
  {
    id: "action-exercise-plan",
    label: "주간 운동 플랜",
    description: "근력·유산소 분배 제안",
    prompt: "허리둘레 감소와 야간 근무를 고려한 1주 운동 계획을 만들어줘."
  },
  {
    id: "action-safety-check",
    label: "의료 에스컬레이션",
    description: "의사 상담 필요 문장 생성",
    prompt: "가슴 두근거림이 반복될 때 상담사가 안내해야 할 의사 에스컬레이션 멘트를 작성해줘."
  },
  {
    id: "action-nutrition",
    label: "야식 대체",
    description: "저당 단백질 간식 제안",
    prompt: "야간 근무 후 쉽게 준비할 수 있는 저당 단백질 간식 3가지를 추천해줘."
  }
];

function formatTimestamp(value: unknown): string {
  if (value instanceof Date) {
    return value.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  if (typeof value === "number" || typeof value === "string") {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
    }
  }

  return "";
}

function composeAnswer(answer: string, citations?: string[]): string {
  const trimmed = answer.trim();
  if (!citations || citations.length === 0) {
    return trimmed;
  }
  return `${trimmed}\n\n참고: ${citations.join(", ")}`;
}

function createMessage(role: WorkspaceMessage["role"], content: string): WorkspaceMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    timestamp: formatTimestamp(new Date())
  };
}

export default function HomePage() {
  const [mode, setMode] = useState<"preparation" | "live">("preparation");
  const [draftPrompt, setDraftPrompt] = useState("");
  const [lastActionId, setLastActionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<WorkspaceMessage[]>(demoConversation);
  const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  const lastStreamingStateRef = useRef({ isStreaming: false, answer: "", citations: [] as string[], error: null as string | null });

  // Use streaming retrieval hook
  const {
    isStreaming,
    messages: streamingMessages,
    answer: streamingAnswer,
    citations: streamingCitations,
    safety: streamingSafety,
    error: streamingError,
    streamQuestion,
  } = useStreamingRetrieval(backendBaseUrl);

  // Convert streaming AG-UI messages to TransparencyItems
  const transparencyFromStreaming: TransparencyItem[] = useMemo(() => {
    return streamingMessages.map((msg: AGUIMessage) => ({
      type: msg.role === "reasoning" ? "Thought" : msg.role === "action" ? "Action" : "Observation",
      title: msg.title,
      detail: msg.content,
    }));
  }, [streamingMessages]);

  const { events: transparencyEvents, activeIndex, reset: resetTransparency } = useTransparencyStream(
    mode,
    transparencyFromStreaming.length > 0 ? transparencyFromStreaming : null
  );

  const safetyEnvelope = useSafetyEnvelope(transparencyEvents, draftPrompt, streamingSafety);

  const conversation = messages;

  // Effect to add answer to messages when streaming completes
  useEffect(() => {
    const wasStreaming = lastStreamingStateRef.current.isStreaming;
    const nowStreaming = isStreaming;

    // Detect transition from streaming to not streaming (streaming just completed)
    if (wasStreaming && !nowStreaming) {
      if (streamingAnswer) {
        const answerText = streamingCitations.length > 0
          ? composeAnswer(streamingAnswer, streamingCitations)
          : streamingAnswer;
        const assistantMessage = createMessage("assistant", answerText);
        setMessages((prev) => [...prev, assistantMessage]);
      } else if (streamingError) {
        const assistantMessage = createMessage(
          "assistant",
          `오류가 발생했습니다: ${streamingError}`
        );
        setMessages((prev) => [...prev, assistantMessage]);
      }
    }

    // Update ref
    lastStreamingStateRef.current = {
      isStreaming,
      answer: streamingAnswer,
      citations: streamingCitations,
      error: streamingError,
    };
  }, [isStreaming, streamingAnswer, streamingCitations, streamingError]);

  // Provide patient context to CopilotKit
  useCopilotReadable({
    description: "Current patient information for metabolic syndrome counseling",
    value: JSON.stringify({
      name: patient.name,
      age: patient.age,
      visitDate: patient.visitDate,
      riskLevel: patient.riskLevel,
      biomarkers: patient.biomarkerHighlights,
      lifestyle: patient.lifestyleHighlights,
    }),
  });

  // Register quick actions as CopilotActions
  useCopilotAction({
    name: "prepareConsultation",
    description: "상담 준비: 주요 위험요인과 생활 습관 포인트 정리",
    parameters: [],
    handler: async () => {
      const prompt = "이번 상담에서 강조해야 할 핵심 위험요인과 생활 습관 포인트를 3가지로 요약해줘.";
      setDraftPrompt(prompt);
      setLastActionId("action-prep-overview");
      setMode("live");
      resetTransparency();
      await streamQuestion(prompt);
      return "상담 준비 요약을 생성했습니다.";
    },
  });

  useCopilotAction({
    name: "createExercisePlan",
    description: "주간 운동 플랜: 근력·유산소 분배 제안",
    parameters: [],
    handler: async () => {
      const prompt = "허리둘레 감소와 야간 근무를 고려한 1주 운동 계획을 만들어줘.";
      setDraftPrompt(prompt);
      setLastActionId("action-exercise-plan");
      setMode("live");
      resetTransparency();
      await streamQuestion(prompt);
      return "주간 운동 플랜을 생성했습니다.";
    },
  });

  useCopilotAction({
    name: "checkMedicalEscalation",
    description: "의료 에스컬레이션: 의사 상담 필요 문장 생성",
    parameters: [],
    handler: async () => {
      const prompt = "가슴 두근거림이 반복될 때 상담사가 안내해야 할 의사 에스컬레이션 멘트를 작성해줘.";
      setDraftPrompt(prompt);
      setLastActionId("action-safety-check");
      setMode("live");
      resetTransparency();
      await streamQuestion(prompt);
      return "의료 에스컬레이션 안내를 생성했습니다.";
    },
  });

  useCopilotAction({
    name: "suggestNightSnacks",
    description: "야식 대체: 저당 단백질 간식 제안",
    parameters: [],
    handler: async () => {
      const prompt = "야간 근무 후 쉽게 준비할 수 있는 저당 단백질 간식 3가지를 추천해줘.";
      setDraftPrompt(prompt);
      setLastActionId("action-nutrition");
      setMode("live");
      resetTransparency();
      await streamQuestion(prompt);
      return "야식 대체 간식을 추천했습니다.";
    },
  });

  const handleSubmit = async () => {
    if (isStreaming) {
      return;
    }
    const prompt = draftPrompt.trim();
    if (!prompt) {
      return;
    }

    setMode("live");
    resetTransparency();

    const counselorMessage = createMessage("counselor", prompt);
    setMessages((prev) => [...prev, counselorMessage]);

    // Start streaming from backend
    // The answer will be automatically added to messages by the useEffect hook
    await streamQuestion(prompt);

    setDraftPrompt("");
  };

  const lastAction = useMemo(
    () => quickActions.find((action) => action.id === lastActionId) ?? null,
    [lastActionId]
  );

  const slaSeconds = mode === "live" ? 10 : 20;

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarGroup}>
          <ModeSwitch mode={mode} onModeChange={setMode} />
        </div>
        <div className={styles.toolbarGroup}>
          <span className={styles.slaIndicator}>
            {mode === "live" ? "실시간 모드 SLA: 답변 시작 10초 이내" : "준비 모드 SLA: 20초 내 요약 제공"}
          </span>
          {lastAction ? (
            <span style={{ fontSize: "0.85rem", color: "#3541ff", fontWeight: 600 }}>
              최근 빠른 액션: {lastAction.label}
            </span>
          ) : null}
        </div>
      </div>
      <section className={styles.quickActions} aria-label="빠른 액션">
        <div className={styles.quickActionsInner}>
          <QuickActions
            actions={quickActions}
            onSelect={(action) => {
              setDraftPrompt(action.prompt);
              setLastActionId(action.id);
              if (mode === "preparation") {
                setMode("live");
              }
              resetTransparency();
            }}
          />
        </div>
      </section>
      <div className={styles.workspace}>
        <PatientSummary {...patient} />
        <ChatWorkspace
          messages={conversation}
          mode={mode}
          draftPrompt={draftPrompt}
          onPromptChange={setDraftPrompt}
          slaSeconds={slaSeconds}
          safetyEnvelope={safetyEnvelope}
          isSubmitting={isStreaming}
          onSubmitPrompt={handleSubmit}
          transparencyEvents={transparencyEvents}
          activeTransparencyIndex={activeIndex}
        />
        <PreparationSidebar forecastedQuestions={prepCards} coachingObservations={observations} />
      </div>
    </div>
  );
}
