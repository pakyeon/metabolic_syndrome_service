"use client";

import styles from "../../app/workspace.module.css";

type PreparationCard = {
  title: string;
  body: string;
  tag: string;
};

type Observation = {
  label: string;
  detail: string;
  status?: "ok" | "warning" | "critical";
};

type PreparationSidebarProps = {
  forecastedQuestions: PreparationCard[];
  coachingObservations: Observation[];
};

const statusBadgeColor: Record<NonNullable<Observation["status"]>, string> = {
  ok: "#1a936f",
  warning: "#ff8c42",
  critical: "#d7263d"
};

export function PreparationSidebar({
  forecastedQuestions,
  coachingObservations
}: PreparationSidebarProps) {
  return (
    <aside className={`${styles.panel} ${styles.prepPanel}`} aria-labelledby="prep-notes">
      <header className={styles.panelHeader}>
        <h2 id="prep-notes">Preparation insights</h2>
        <p style={{ margin: "0.25rem 0 0", color: "#5b6478" }}>
          Generated before the session to keep you one step ahead during live counseling.
        </p>
      </header>
      <div className={styles.panelBody}>
        <section style={{ marginBottom: "1.75rem" }} aria-labelledby="anticipated-questions">
          <h3 id="anticipated-questions" style={{ margin: 0, fontSize: "1rem" }}>
            Anticipated questions
          </h3>
          <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "1rem" }}>
            {forecastedQuestions.map((card) => (
              <li
                key={card.title}
                style={{
                  border: "1px solid rgba(28, 35, 51, 0.1)",
                  borderRadius: "0.9rem",
                  padding: "1rem"
                }}
              >
                <span
                  style={{
                    display: "inline-flex",
                    background: "rgba(53, 97, 255, 0.12)",
                    color: "#3541ff",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    padding: "0.25rem 0.65rem",
                    borderRadius: "999px",
                    marginBottom: "0.75rem"
                  }}
                >
                  {card.tag}
                </span>
                <h4 style={{ margin: "0 0 0.5rem" }}>{card.title}</h4>
                <p style={{ margin: 0, color: "#5b6478", fontSize: "0.9rem" }}>{card.body}</p>
              </li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="coaching-observations">
          <h3 id="coaching-observations" style={{ margin: 0, fontSize: "1rem" }}>
            Coaching observations
          </h3>
          <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "0.75rem" }}>
            {coachingObservations.map((item) => (
              <li
                key={item.label}
                style={{
                  padding: "0.75rem 0.5rem",
                  borderBottom: "1px solid rgba(28, 35, 51, 0.08)"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <strong>{item.label}</strong>
                  {item.status ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.25rem",
                        background: `${statusBadgeColor[item.status]}1a`,
                        color: statusBadgeColor[item.status],
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        padding: "0.15rem 0.5rem",
                        borderRadius: "999px"
                      }}
                    >
                      ● {item.status === "ok" ? "On track" : item.status === "warning" ? "Watch" : "Escalate"}
                    </span>
                  ) : null}
                </div>
                <p style={{ margin: "0.3rem 0 0", color: "#5b6478", fontSize: "0.9rem" }}>{item.detail}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </aside>
  );
}
