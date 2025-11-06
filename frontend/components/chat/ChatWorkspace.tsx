"use client";

import styles from "../../app/workspace.module.css";
import { SafetyBannerState } from "../../hooks/useSafetyEnvelope";
import { SafetyBanner } from "../safety/SafetyBanner";
import { TransparencyTimeline } from "./TransparencyTimeline";

type Message = {
  id: string;
  role: "counselor" | "assistant";
  content: string;
  timestamp: string;
};

type ChatWorkspaceProps = {
  messages: Message[];
  mode: "preparation" | "live";
  draftPrompt: string;
  onPromptChange: (value: string) => void;
  slaSeconds: number;
  safetyEnvelope: SafetyBannerState;
  isSubmitting: boolean;
  onSubmitPrompt: () => void;
  transparencyEvents: {
    type: "Thought" | "Action" | "Observation";
    title: string;
    detail: string;
  }[];
  activeTransparencyIndex: number;
  currentStage?: string | null; // ChatGPT-style progress indicator
};

export function ChatWorkspace({
  messages,
  mode,
  draftPrompt,
  onPromptChange,
  slaSeconds,
  safetyEnvelope,
  isSubmitting,
  onSubmitPrompt,
  transparencyEvents,
  activeTransparencyIndex,
  currentStage
}: ChatWorkspaceProps) {
  const modeLabel = mode === "live" ? "Live counseling" : "Preparation";
  const modeColor = mode === "live" ? "#3541ff" : "#1a936f";

  return (
    <section className={`${styles.panel} ${styles.mainPanel}`} aria-labelledby="live-chat">
      <header className={styles.panelHeader}>
        <h2 id="live-chat">Live counseling workspace</h2>
        <div
          style={{
            marginTop: "0.75rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem"
          }}
        >
          <span className={styles.modeBadge} style={{ borderColor: modeColor + "33", color: modeColor }}>
            <span
              aria-hidden
              style={{
                width: "0.45rem",
                height: "0.45rem",
                borderRadius: "999px",
                background: modeColor
              }}
            />
            {modeLabel}
          </span>
          <span className={styles.slaIndicator}>
            SLA: start answer within {slaSeconds}초 ({mode === "live" ? "실시간 모드" : "준비 모드"})
          </span>
        </div>
      </header>
      <div className={styles.panelBody}>
        <SafetyBanner envelope={safetyEnvelope} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            marginBottom: "1.5rem"
          }}
          aria-live="polite"
        >
          {messages.map((message) => (
            <article
              key={message.id}
              style={{
                alignSelf: message.role === "assistant" ? "flex-start" : "flex-end",
                maxWidth: "80%",
                background: message.role === "assistant" ? "rgba(53, 97, 255, 0.08)" : "#1c2333",
                color: message.role === "assistant" ? "#1c2333" : "#ffffff",
                padding: "0.9rem 1.1rem",
                borderRadius: message.role === "assistant" ? "1rem 1rem 1rem 0.5rem" : "1rem 1rem 0.5rem 1rem"
              }}
            >
              <p style={{ margin: 0, fontSize: "0.95rem", lineHeight: 1.5 }}>{message.content}</p>
              <time
                style={{
                  display: "block",
                  marginTop: "0.5rem",
                  fontSize: "0.75rem",
                  opacity: 0.7
                }}
              >
                {message.timestamp}
              </time>
            </article>
          ))}
          {/* ChatGPT-style progress indicator */}
          {isSubmitting && currentStage && (
            <div
              style={{
                alignSelf: "flex-start",
                maxWidth: "80%",
                padding: "0.9rem 1.1rem",
                borderRadius: "1rem 1rem 1rem 0.5rem",
                background: "rgba(53, 97, 255, 0.04)",
                border: "1px solid rgba(53, 97, 255, 0.1)",
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
              }}
            >
              <div
                style={{
                  width: "1rem",
                  height: "1rem",
                  border: "2px solid #3541ff",
                  borderTopColor: "transparent",
                  borderRadius: "50%",
                  animation: "spin 0.8s linear infinite",
                }}
              />
              <span style={{ fontSize: "0.875rem", color: "#5b6478", fontWeight: 500 }}>
                {currentStage}
              </span>
              <style jsx>{`
                @keyframes spin {
                  to {
                    transform: rotate(360deg);
                  }
                }
              `}</style>
            </div>
          )}
        </div>
        <form
          style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}
          onSubmit={(event) => {
            event.preventDefault();
            onSubmitPrompt();
          }}
        >
          <label style={{ display: "block", fontWeight: 600 }} htmlFor="prompt">
            Counselor prompt
          </label>
          <textarea
            id="prompt"
            ref={(textarea) => {
              // Store ref for keyboard shortcut
              if (textarea) {
                (window as any).__promptTextarea = textarea;
              }
            }}
            rows={4}
            placeholder="예: 식후 혈당이 160mg/dL인데 오늘 상담에서 무엇을 강조해야 할까요?"
            style={{
              width: "100%",
              borderRadius: "0.75rem",
              border: "1px solid rgba(28, 35, 51, 0.16)",
              padding: "0.85rem 1rem",
              fontFamily: "inherit"
            }}
            value={draftPrompt}
            onChange={(event) => onPromptChange(event.target.value)}
            onKeyDown={(event) => {
              // Ctrl+Space shortcut to focus input
              if (event.ctrlKey && event.key === ' ') {
                event.preventDefault();
                event.currentTarget.focus();
              }
            }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              type="submit"
              disabled={isSubmitting || draftPrompt.trim().length === 0}
              style={{
                padding: "0.65rem 1.4rem",
                borderRadius: "0.75rem",
                border: "none",
                background: isSubmitting || draftPrompt.trim().length === 0 ? "#c5c8d4" : "#3541ff",
                color: "#ffffff",
                fontWeight: 600,
                cursor: isSubmitting || draftPrompt.trim().length === 0 ? "not-allowed" : "pointer",
                transition: "background 0.2s ease"
              }}
            >
              {isSubmitting ? "생성 중..." : "답변 요청"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
