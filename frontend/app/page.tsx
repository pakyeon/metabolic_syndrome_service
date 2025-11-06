"use client";

import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import styles from "./workspace.module.css";
import { PatientSummary } from "../components/patient/PatientSummary";
import { ChatWorkspace } from "../components/chat/ChatWorkspace";
import { PreparationSidebar } from "../components/preparation/PreparationSidebar";
import { ReferencesPanel, Citation } from "../components/references/ReferencesPanel";
import { QuickActions, QuickAction } from "../components/actions/QuickActions";
import { ModeSwitch } from "../components/actions/ModeSwitch";
import { TransparencyItem, useTransparencyStream } from "../hooks/useTransparencyStream";
import { SafetyBannerState, useSafetyEnvelope } from "../hooks/useSafetyEnvelope";
import { useStreamingRetrieval, AGUIMessage } from "../hooks/useStreamingRetrieval";
import { usePatientData } from "../hooks/usePatientData";
import { formatBiomarkers, formatLifestyle } from "../lib/formatters";

type WorkspaceMessage = {
  id: string;
  role: "counselor" | "assistant";
  content: string;
  timestamp: string;
};

// Preparation analysis result from backend
interface PreparationAnalysis {
  keyPoints: string[];  // 핵심 포인트 3-5개
  anticipatedQuestions: Array<{
    question: string;
    answer: string;
    source?: string;
  }>;
  deliveryExamples: Array<{
    topic: string;
    bad: string;
    good: string;
  }>;
  warnings: string[];  // 주의사항
}

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

// Demo data for preparation mode (kept for Phase 1, will be replaced with backend data in Week 2)
const demoPrepCards = [
  {
    title: "야간 근무 후 혈당 관리 질문 예상",
    body: "'야간 근무 끝나면 너무 피곤해서 바로 잠들고 싶은데 운동 대신 할 수 있는 게 있을까요?'",
    tag: "혈당"
  },
  {
    title: "골반 통증 관련 운동 허용 여부",
    body: "최근 물리치료 중이며, 허리 회전이 큰 운동을 피하라는 처방이 있었음. 완만한 스텝업을 대안으로 제안합니다.",
    tag: "운동"
  }
];

const demoObservations = [
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
  // Get patient ID from URL query parameter
  const searchParams = useSearchParams();
  const patientId = searchParams.get('patient_id');

  // Fetch patient data from backend
  const { data: patientData, loading: patientLoading, error: patientError } = usePatientData(patientId);

  const [mode, setMode] = useState<"preparation" | "live">("preparation");
  const [draftPrompt, setDraftPrompt] = useState("");
  const [lastActionId, setLastActionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<WorkspaceMessage[]>(demoConversation);
  const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  const lastStreamingStateRef = useRef({ isStreaming: false, answer: "", citations: [] as string[], error: null as string | null });

  // Preparation workflow state
  const [isPreparationRunning, setIsPreparationRunning] = useState(false);
  const [preparationStage, setPreparationStage] = useState<string | null>(null);
  const [preparationComplete, setPreparationComplete] = useState(false);
  const [preparationAnalysis, setPreparationAnalysis] = useState<PreparationAnalysis | null>(null);

  // Session management state
  const [sessionId, setSessionId] = useState<string | null>(null);

  // UI state for dynamic layout
  const [sidebarExpanded, setSidebarExpanded] = useState(true);

  // Citations state for References Panel
  const [citations, setCitations] = useState<Citation[]>([]);

  // Auto-save messages to database
  const saveMessage = async (role: "user" | "assistant", content: string) => {
    if (!sessionId) {
      console.warn("No session ID, skipping message save");
      return;
    }

    try {
      await fetch(`${backendBaseUrl}/v1/sessions/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          role: role,
          content: content,
          metadata: {
            timestamp: new Date().toISOString(),
            mode: mode,
          },
        }),
      });
    } catch (err) {
      console.error("Error saving message:", err);
      // Silent failure - don't block user experience
    }
  };

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

        // Save assistant message to database
        saveMessage("assistant", answerText);

        // Update citations for References Panel
        if (streamingCitations.length > 0) {
          const newCitations: Citation[] = streamingCitations.map((citation, idx) => ({
            id: `citation-${Date.now()}-${idx}`,
            title: citation,
            content: `참고 문서: ${citation}`,
            relevance_score: 0.85, // Default score (backend should provide this in future)
            source: citation,
          }));
          setCitations(newCitations);
        }
      } else if (streamingError) {
        const assistantMessage = createMessage(
          "assistant",
          `오류가 발생했습니다: ${streamingError}`
        );
        setMessages((prev) => [...prev, assistantMessage]);

        // Save error message to database
        saveMessage("assistant", `오류: ${streamingError}`);
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

  // Format patient data for display and CopilotKit
  const biomarkerHighlights = useMemo(
    () => formatBiomarkers(patientData?.latestExam || null, patientData?.patient.sex),
    [patientData]
  );

  const lifestyleHighlights = useMemo(
    () => formatLifestyle(patientData?.survey || null),
    [patientData]
  );

  const patientForDisplay = useMemo(() => {
    if (!patientData) return null;

    return {
      name: patientData.patient.name,
      age: patientData.patient.age,
      visitDate: patientData.latestExam?.exam_at
        ? new Date(patientData.latestExam.exam_at).toLocaleDateString('ko-KR')
        : '-',
      riskLevel: (patientData.latestExam?.risk_level as 'low' | 'moderate' | 'high') || 'low',
      biomarkerHighlights,
      lifestyleHighlights,
    };
  }, [patientData, biomarkerHighlights, lifestyleHighlights]);

  // Provide patient context to CopilotKit
  useCopilotReadable({
    description: "Current patient information for metabolic syndrome counseling",
    value: JSON.stringify({
      patientId: patientId,
      name: patientData?.patient.name,
      age: patientData?.patient.age,
      sex: patientData?.patient.sex,
      visitDate: patientData?.latestExam?.exam_at,
      riskLevel: patientData?.latestExam?.risk_level,
      riskFactors: patientData?.latestExam?.risk_factors,
      biomarkers: biomarkerHighlights,
      lifestyle: lifestyleHighlights,
      latestExam: patientData?.latestExam,
      survey: patientData?.survey,
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

    // Save user message to database
    await saveMessage("user", prompt);

    // Start streaming from backend
    // The answer will be automatically added to messages by the useEffect hook
    await streamQuestion(prompt);

    setDraftPrompt("");
  };

  // Preparation workflow handler with real backend integration
  const handlePreparationStart = async () => {
    if (!patientId || !patientData) {
      console.error("No patient data available for preparation");
      return;
    }

    setIsPreparationRunning(true);
    setPreparationComplete(false);
    setPreparationAnalysis(null);

    try {
      // Prepare context with full patient data
      const context = JSON.stringify({
        patient_id: patientId,
        patient: patientData.patient,
        latest_exam: patientData.latestExam,
        survey: patientData.survey,
      });

      const response = await fetch(`${backendBaseUrl}/v1/retrieve/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "이번 상담을 위한 준비 자료를 생성해줘. 핵심 포인트, 예상 질문과 권장 답변, 전달 방식 예시, 주의사항을 포함해서 작성해줘.",
          context: context,
          mode: "preparation",
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend error: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body reader available");
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let finalAnswer = "";

      // Node name to stage message mapping
      const stageMap: Record<string, string> = {
        "prep_analyze_patient": "환자 기록 검색 중...",
        "prep_analyze_history": "이전 상담 패턴 파악 중...",
        "prep_generate_questions": "예상 질문 생성 중...",
        "prep_prepare_answers": "권장 답변 준비 중...",
        "prep_delivery_examples": "전달 방식 예시 생성 중...",
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;

          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === "node_update") {
              // Update progress stage based on node name
              const stage = stageMap[data.node] || "분석 중...";
              setPreparationStage(stage);
              console.log(`Preparation stage: ${data.node} -> ${stage}`);
            }

            if (data.type === "complete") {
              // Extract final answer
              finalAnswer = data.output?.answer || "";
              console.log("Preparation complete, answer length:", finalAnswer.length);
            }
          } catch (parseError) {
            console.error("Error parsing SSE data:", parseError);
          }
        }
      }

      // Parse the answer into PreparationAnalysis structure
      const analysis = parsePreparationAnalysis(finalAnswer);
      setPreparationAnalysis(analysis);

      setPreparationStage(null);
      setIsPreparationRunning(false);
      setPreparationComplete(true);

      console.log("Preparation analysis:", analysis);
    } catch (error) {
      console.error("Preparation failed:", error);
      setPreparationStage(null);
      setIsPreparationRunning(false);

      // Show error to user
      alert(`상담 준비 중 오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
    }
  };

  // Helper function to parse LLM answer into structured PreparationAnalysis
  const parsePreparationAnalysis = (answer: string): PreparationAnalysis => {
    // Simple parser - looks for sections in the answer
    const keyPoints: string[] = [];
    const anticipatedQuestions: Array<{ question: string; answer: string; source?: string }> = [];
    const deliveryExamples: Array<{ topic: string; bad: string; good: string }> = [];
    const warnings: string[] = [];

    // Split by common section headers
    const sections = answer.split(/\n(?=##\s|###\s|\d+\.\s)/);

    for (const section of sections) {
      const lowerSection = section.toLowerCase();

      // Extract key points
      if (lowerSection.includes('핵심') || lowerSection.includes('포인트')) {
        const lines = section.split('\n').filter(l => l.trim().startsWith('-') || l.trim().match(/^\d+\./));
        keyPoints.push(...lines.map(l => l.replace(/^[-\d.]\s*/, '').trim()).filter(Boolean));
      }

      // Extract anticipated questions
      if (lowerSection.includes('예상 질문') || lowerSection.includes('질문') && lowerSection.includes('답변')) {
        const questionMatches = section.match(/질문[:\s]*(.+?)\n답변[:\s]*(.+?)(?=\n질문|\n\n|$)/gs);
        if (questionMatches) {
          for (const match of questionMatches) {
            const [, q, a] = match.match(/질문[:\s]*(.+?)\n답변[:\s]*(.+)/s) || [];
            if (q && a) {
              anticipatedQuestions.push({ question: q.trim(), answer: a.trim() });
            }
          }
        }
      }

      // Extract delivery examples
      if (lowerSection.includes('전달 방식') || lowerSection.includes('예시')) {
        const exampleMatches = section.match(/❌\s*(.+?)\n✅\s*(.+?)(?=\n❌|\n\n|$)/gs);
        if (exampleMatches) {
          for (const match of exampleMatches) {
            const [, bad, good] = match.match(/❌\s*(.+?)\n✅\s*(.+)/s) || [];
            if (bad && good) {
              deliveryExamples.push({ topic: "전달 방식", bad: bad.trim(), good: good.trim() });
            }
          }
        }
      }

      // Extract warnings
      if (lowerSection.includes('주의') || lowerSection.includes('경고')) {
        const lines = section.split('\n').filter(l => l.trim().startsWith('-') || l.trim().startsWith('⚠'));
        warnings.push(...lines.map(l => l.replace(/^[-⚠]\s*/, '').trim()).filter(Boolean));
      }
    }

    // Fallback: if parsing failed, create a simple structure
    if (keyPoints.length === 0 && anticipatedQuestions.length === 0) {
      return {
        keyPoints: [
          "환자의 대사증후군 위험인자 확인",
          "생활습관 개선 목표 설정",
          "운동 및 식단 계획 수립"
        ],
        anticipatedQuestions: [
          {
            question: "어떤 운동을 해야 하나요?",
            answer: answer.substring(0, 200) + "..." // Use part of the answer
          }
        ],
        deliveryExamples: [],
        warnings: ["의학적 판단이 필요한 질문은 의사에게 에스컬레이션하세요."]
      };
    }

    return {
      keyPoints: keyPoints.length > 0 ? keyPoints : ["상담 준비 자료가 생성되었습니다."],
      anticipatedQuestions,
      deliveryExamples,
      warnings: warnings.length > 0 ? warnings : ["환자의 개별 상황을 고려하여 조언하세요."]
    };
  };

  // Consultation start handler
  const handleConsultationStart = () => {
    setMode("live");
    setSidebarExpanded(false);  // Auto-collapse sidebar in live mode
    // Auto-scroll to chat input (optional)
    // Could add toast notification here in future
  };

  // Auto-expand sidebar in preparation mode
  useEffect(() => {
    if (mode === "preparation" && !sidebarExpanded) {
      setSidebarExpanded(true);
    }
  }, [mode, sidebarExpanded]);

  // Create session when patient is selected
  useEffect(() => {
    if (!patientId || !patientData) return;

    async function createSession() {
      try {
        const response = await fetch(`${backendBaseUrl}/v1/sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patient_id: patientId,
            user_id: "counselor_demo",  // Hardcoded as per user requirement
            metadata: {
              patient_name: patientData.patient.name,
              created_from: "workspace",
            },
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create session: ${response.statusText}`);
        }

        const data = await response.json();
        setSessionId(data.session_id);
        console.log("Session created:", data.session_id);
      } catch (err) {
        console.error("Error creating session:", err);
      }
    }

    // Only create session if we don't have one yet
    if (!sessionId) {
      createSession();
    }
  }, [patientId, patientData, sessionId, backendBaseUrl]);

  const lastAction = useMemo(
    () => quickActions.find((action) => action.id === lastActionId) ?? null,
    [lastActionId]
  );

  const slaSeconds = mode === "live" ? 10 : 20;

  // Handle loading and error states
  if (!patientId) {
    return (
      <div className={styles.page}>
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>환자를 선택해주세요</h2>
          <p>환자 목록에서 상담할 환자를 선택해주세요.</p>
          <a href="/patients" style={{ color: '#3541ff', textDecoration: 'underline' }}>
            환자 목록으로 이동
          </a>
        </div>
      </div>
    );
  }

  if (patientLoading) {
    return (
      <div className={styles.page}>
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <p>환자 데이터를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (patientError || !patientData) {
    return (
      <div className={styles.page}>
        <div style={{ padding: '2rem', textAlign: 'center', color: '#dc2626' }}>
          <h2>오류가 발생했습니다</h2>
          <p>{patientError?.message || '환자 데이터를 불러올 수 없습니다.'}</p>
          <a href="/patients" style={{ color: '#3541ff', textDecoration: 'underline' }}>
            환자 목록으로 돌아가기
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarGroup}>
          <ModeSwitch mode={mode} onModeChange={setMode} disabled={isPreparationRunning} />

          {/* Workflow Buttons */}
          <button
            onClick={handlePreparationStart}
            disabled={isPreparationRunning || !patientId}
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: isPreparationRunning ? "#9ca3af" : "#3541ff",
              color: "white",
              border: "none",
              borderRadius: "6px",
              fontWeight: 600,
              fontSize: "0.875rem",
              cursor: isPreparationRunning || !patientId ? "not-allowed" : "pointer",
              transition: "background-color 0.2s",
            }}
          >
            {isPreparationRunning ? "상담 준비 중..." : "상담 준비 시작"}
          </button>

          <button
            onClick={handleConsultationStart}
            disabled={!preparationComplete}
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: preparationComplete ? "#16a34a" : "#d1d5db",
              color: "white",
              border: "none",
              borderRadius: "6px",
              fontWeight: 600,
              fontSize: "0.875rem",
              cursor: preparationComplete ? "pointer" : "not-allowed",
              transition: "background-color 0.2s",
            }}
          >
            상담 시작
          </button>
        </div>
        <div className={styles.toolbarGroup}>
          {isPreparationRunning && preparationStage ? (
            <span style={{ fontSize: "0.85rem", color: "#3541ff", fontWeight: 600 }}>
              {preparationStage}
            </span>
          ) : (
            <>
              <span className={styles.slaIndicator}>
                {mode === "live" ? "실시간 모드 SLA: 답변 시작 10초 이내" : "준비 모드 SLA: 20초 내 요약 제공"}
              </span>
              {lastAction ? (
                <span style={{ fontSize: "0.85rem", color: "#3541ff", fontWeight: 600 }}>
                  최근 빠른 액션: {lastAction.label}
                </span>
              ) : null}
            </>
          )}
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
        {patientForDisplay && <PatientSummary {...patientForDisplay} />}
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
        <PreparationSidebar
          forecastedQuestions={demoPrepCards}
          coachingObservations={demoObservations}
          patient={patientData?.patient}
          exam={patientData?.latestExam}
          survey={patientData?.survey}
          expanded={sidebarExpanded}
          onToggle={() => setSidebarExpanded(!sidebarExpanded)}
          preparationAnalysis={preparationAnalysis}
        />
        {mode === "live" && citations.length > 0 && (
          <ReferencesPanel citations={citations} />
        )}
      </div>
    </div>
  );
}
