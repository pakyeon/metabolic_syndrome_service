"use client";

import styles from "../../app/workspace.module.css";

type TransparencyEvent = {
  type: "Thought" | "Action" | "Observation";
  title: string;
  detail: string;
};

type TransparencyTimelineProps = {
  events: TransparencyEvent[];
  activeIndex: number;
};

const typeColor: Record<TransparencyEvent["type"], string> = {
  Thought: "#3541ff",
  Action: "#ff8c42",
  Observation: "#1a936f"
};

export function TransparencyTimeline({ events, activeIndex }: TransparencyTimelineProps) {
  return (
    <section aria-label="Copilot progress" style={{ marginTop: "1.5rem" }}>
      <header style={{ marginBottom: "0.75rem", display: "flex", justifyContent: "space-between" }}>
        <h3 style={{ margin: 0, fontSize: "1rem" }}>Thought/Action/Observation</h3>
        <small style={{ color: "#5b6478" }}>실시간 파이프라인 상태</small>
      </header>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.9rem" }}>
        {events.map((event, index) => {
          const isActive = index === activeIndex;
          const isCompleted = index < activeIndex;
          return (
            <li
              key={`${event.type}-${index}`}
              style={{
                background: isActive ? "rgba(53, 65, 255, 0.12)" : "rgba(28, 35, 51, 0.04)",
                border: `1px solid ${isCompleted ? "rgba(53, 65, 255, 0.4)" : "rgba(28, 35, 51, 0.1)"}`,
                borderRadius: "0.85rem",
                padding: "0.85rem 1rem"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span
                  style={{
                    width: "0.6rem",
                    height: "0.6rem",
                    borderRadius: "999px",
                    background: typeColor[event.type]
                  }}
                  aria-hidden
                />
                <strong>{event.type}</strong>
                {isActive ? (
                  <span style={{ fontSize: "0.75rem", color: "#3541ff", fontWeight: 600 }}>진행 중</span>
                ) : isCompleted ? (
                  <span style={{ fontSize: "0.75rem", color: "#1a936f", fontWeight: 600 }}>완료</span>
                ) : null}
              </div>
              <p style={{ margin: "0.35rem 0 0", fontWeight: 600 }}>{event.title}</p>
              <p style={{ margin: "0.2rem 0 0", color: "#5b6478", fontSize: "0.9rem" }}>{event.detail}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
