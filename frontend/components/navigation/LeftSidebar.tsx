"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./LeftSidebar.module.css";

interface Patient {
  patient_id: string;
  name: string;
  risk_level?: "low" | "moderate" | "high";
}

interface Session {
  session_id: string;
  created_at: string;
  message_count: number;
}

interface LeftSidebarProps {
  patients: Patient[];
  sessions: Session[];
  currentPatientId?: string;
  collapsed: boolean;
  onToggle: () => void;
}

export function LeftSidebar({
  patients,
  sessions,
  currentPatientId,
  collapsed,
  onToggle,
}: LeftSidebarProps) {
  const router = useRouter();
  const [activeSection, setActiveSection] = useState<"patients" | "sessions">("patients");

  if (collapsed) {
    return (
      <aside className={`${styles.sidebar} ${styles.collapsed}`}>
        <button onClick={onToggle} className={styles.toggleBtn}>
          »
        </button>
        <div className={styles.iconBar}>
          <button onClick={() => setActiveSection("patients")} title="환자 목록">
            👤
          </button>
          <button onClick={() => setActiveSection("sessions")} title="대화 히스토리">
            💬
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className={styles.sidebar}>
      <header className={styles.header}>
        <h2>환자 목록</h2>
        <button onClick={onToggle} className={styles.toggleBtn}>
          «
        </button>
      </header>

      <nav className={styles.nav}>
        <button
          className={activeSection === "patients" ? styles.active : ""}
          onClick={() => setActiveSection("patients")}
        >
          환자 목록
        </button>
        <button
          className={activeSection === "sessions" ? styles.active : ""}
          onClick={() => setActiveSection("sessions")}
        >
          대화 히스토리
        </button>
      </nav>

      <div className={styles.body}>
        {activeSection === "patients" ? (
          <div className={styles.patientList}>
            {patients.map((patient) => (
              <div
                key={patient.patient_id}
                className={`${styles.patientCard} ${
                  currentPatientId === patient.patient_id ? styles.selected : ""
                }`}
                onClick={() => router.push(`/workspace?patient_id=${patient.patient_id}&autoStart=true`)}
              >
                <div className={styles.avatar}>
                  {patient.name.charAt(0)}
                </div>
                <div className={styles.info}>
                  <div className={styles.name}>{patient.name}</div>
                  {patient.risk_level && (
                    <div className={`${styles.risk} ${styles[patient.risk_level]}`}>
                      {patient.risk_level === "high" ? "높음" : patient.risk_level === "moderate" ? "중간" : "낮음"}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.sessionList}>
            {sessions.map((session) => (
              <div key={session.session_id} className={styles.sessionCard}>
                <div className={styles.date}>
                  {new Date(session.created_at).toLocaleDateString("ko-KR")}
                </div>
                <div className={styles.messageCount}>
                  {session.message_count}개 메시지
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
