"use client";

import styles from "../../app/workspace.module.css";

type Biomarker = {
  label: string;
  value: string;
  status: "optimal" | "elevated" | "critical";
  guidance: string;
};

type LifestyleNote = {
  title: string;
  detail: string;
};

type PatientSummaryProps = {
  name: string;
  age: number;
  visitDate: string;
  riskLevel: "low" | "moderate" | "high";
  biomarkerHighlights: Biomarker[];
  lifestyleHighlights: LifestyleNote[];
};

const statusColorMap: Record<Biomarker["status"], string> = {
  optimal: "#1a936f",
  elevated: "#ff8c42",
  critical: "#d7263d"
};

export function PatientSummary({
  name,
  age,
  visitDate,
  riskLevel,
  biomarkerHighlights,
  lifestyleHighlights
}: PatientSummaryProps) {
  return (
    <section className={`${styles.panel} ${styles.patientPanel}`} aria-labelledby="patient-summary">
      <header className={styles.panelHeader}>
        <h2 id="patient-summary">환자 한눈에 보기</h2>
        <p style={{ margin: "0.25rem 0 0", color: "#5b6478" }}>
          {name} · {age}세 · 최근 방문 {visitDate}
        </p>
        <span
          style={{
            marginTop: "0.75rem",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            fontWeight: 600,
            color: riskLevel === "high" ? "#d7263d" : riskLevel === "moderate" ? "#ff8c42" : "#1a936f"
          }}
        >
          <span
            aria-hidden
            style={{
              width: "0.5rem",
              height: "0.5rem",
              borderRadius: "50%",
              background:
                riskLevel === "high" ? "#d7263d" : riskLevel === "moderate" ? "#ff8c42" : "#1a936f"
            }}
          />
          위험도: {riskLevel === "high" ? "높음" : riskLevel === "moderate" ? "중간" : "낮음"}
        </span>
      </header>
      <div className={styles.panelBody}>
        <div style={{ marginBottom: "1.75rem" }}>
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>주요 바이오마커</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.75rem" }}>
            {biomarkerHighlights.map((marker) => (
              <li
                key={marker.label}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.35rem",
                  padding: "0.75rem",
                  borderRadius: "0.75rem",
                  background: "rgba(28, 35, 51, 0.04)"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ fontWeight: 600 }}>{marker.label}</span>
                  <span style={{ color: statusColorMap[marker.status], fontWeight: 600 }}>{marker.value}</span>
                </div>
                <p style={{ margin: 0, color: "#5b6478", fontSize: "0.9rem" }}>{marker.guidance}</p>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>생활 습관 신호</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.75rem" }}>
            {lifestyleHighlights.map((note) => (
              <li key={note.title}>
                <p style={{ margin: 0, fontWeight: 600 }}>{note.title}</p>
                <p style={{ margin: "0.25rem 0 0", color: "#5b6478", fontSize: "0.9rem" }}>{note.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
