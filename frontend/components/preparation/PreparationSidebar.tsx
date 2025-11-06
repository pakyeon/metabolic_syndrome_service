"use client";

import styles from "../../app/workspace.module.css";
import { PatientDetail, HealthExam, SurveyDetail } from "../../hooks/usePatientData";
import { BiomarkerCard } from "./BiomarkerCard";

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

// Preparation analysis from backend
interface PreparationAnalysis {
  keyPoints: string[];
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
  warnings: string[];
}

type PreparationSidebarProps = {
  forecastedQuestions: PreparationCard[];
  coachingObservations: Observation[];
  patient?: PatientDetail;
  exam?: HealthExam | null;
  survey?: SurveyDetail | null;
  expanded?: boolean;
  onToggle?: () => void;
  preparationAnalysis?: PreparationAnalysis | null;
};

const statusBadgeColor: Record<NonNullable<Observation["status"]>, string> = {
  ok: "#1a936f",
  warning: "#ff8c42",
  critical: "#d7263d"
};

export function PreparationSidebar({
  forecastedQuestions,
  coachingObservations,
  patient,
  exam,
  survey,
  expanded = true,
  onToggle,
  preparationAnalysis
}: PreparationSidebarProps) {
  const getRiskLevelColor = (level?: string) => {
    switch (level?.toLowerCase()) {
      case 'high': return '#dc2626';
      case 'moderate': return '#f59e0b';
      case 'low': return '#16a34a';
      default: return '#6b7280';
    }
  };

  if (!expanded) {
    // Collapsed view - show just icons
    return (
      <aside
        className={`${styles.panel} ${styles.prepPanel}`}
        style={{
          width: '60px',
          padding: '0.5rem',
          transition: 'all 0.3s ease',
        }}
        aria-labelledby="prep-notes"
      >
        <button
          onClick={onToggle}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '0.5rem',
            fontSize: '1.25rem',
          }}
          title="사이드바 펼치기"
        >
          »
        </button>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          marginTop: '1rem',
          alignItems: 'center',
        }}>
          <span title="설문지" style={{ fontSize: '1.5rem' }}>📋</span>
          <span title="검사 결과" style={{ fontSize: '1.5rem' }}>🏥</span>
          <span title="핵심 포인트" style={{ fontSize: '1.5rem' }}>💡</span>
          <span title="예상 질문" style={{ fontSize: '1.5rem' }}>❓</span>
          <span title="관찰 사항" style={{ fontSize: '1.5rem' }}>👁️</span>
          <span title="주의사항" style={{ fontSize: '1.5rem' }}>⚠️</span>
        </div>
      </aside>
    );
  }

  return (
    <aside
      className={`${styles.panel} ${styles.prepPanel}`}
      style={{ transition: 'all 0.3s ease' }}
      aria-labelledby="prep-notes"
    >
      <header className={styles.panelHeader} style={{ position: 'relative' }}>
        <h2 id="prep-notes">Preparation insights</h2>
        <p style={{ margin: "0.25rem 0 0", color: "#5b6478" }}>
          Generated before the session to keep you one step ahead during live counseling.
        </p>
        {onToggle && (
          <button
            onClick={onToggle}
            style={{
              position: 'absolute',
              right: '0.5rem',
              top: '0.5rem',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0.25rem 0.5rem',
              fontSize: '1.125rem',
              color: '#6b7280',
            }}
            title="사이드바 접기"
          >
            «
          </button>
        )}
      </header>
      <div className={styles.panelBody}>
        {/* Section 1: Patient Survey Data (Subjective) */}
        {survey && (
          <section style={{ marginBottom: "1.75rem" }} aria-labelledby="patient-survey">
            <h3 id="patient-survey" style={{ margin: 0, fontSize: "1rem" }}>
              환자 기초설문지
            </h3>
            <div style={{ marginTop: "1rem", display: "grid", gap: "0.75rem" }}>
              {survey.physical_activity && (
                <>
                  <div style={{ fontSize: "0.9rem" }}>
                    <strong style={{ color: "#374151" }}>운동 계획:</strong>
                    <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                      {survey.physical_activity.exercise_plan || '없음'}
                    </span>
                  </div>
                  {survey.physical_activity.no_exercise_reason && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>운동 미실천 이유:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        {survey.physical_activity.no_exercise_reason}
                      </span>
                    </div>
                  )}
                  {survey.physical_activity.sedentary_hours !== undefined && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>좌식 시간:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        하루 {survey.physical_activity.sedentary_hours}시간 {survey.physical_activity.sedentary_minutes || 0}분
                      </span>
                    </div>
                  )}
                </>
              )}
              {survey.diet_habit && (
                <>
                  {survey.diet_habit.diet_total_score !== undefined && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>식습관 점수:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        {survey.diet_habit.diet_total_score}/10점
                      </span>
                    </div>
                  )}
                  {survey.diet_habit.breakfast_frequency && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>아침식사:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        {survey.diet_habit.breakfast_frequency}
                      </span>
                    </div>
                  )}
                </>
              )}
              {survey.mental_health && (
                <>
                  {survey.mental_health.phq9_total_score !== undefined && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>정신건강 (PHQ-9):</strong>
                      <span style={{ color: survey.mental_health.phq9_total_score > 10 ? '#dc2626' : '#5b6478', marginLeft: "0.5rem" }}>
                        {survey.mental_health.phq9_total_score}점
                        {survey.mental_health.phq9_total_score > 10 && ' (주의 필요)'}
                      </span>
                    </div>
                  )}
                  {survey.mental_health.sleep_hours_weekday !== undefined && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>수면 시간:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        평일 {survey.mental_health.sleep_hours_weekday}시간
                        {survey.mental_health.sleep_hours_weekend !== undefined && `, 주말 ${survey.mental_health.sleep_hours_weekend}시간`}
                      </span>
                    </div>
                  )}
                </>
              )}
              {survey.obesity_management && (
                <>
                  {survey.obesity_management.body_shape_perception && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>체형 인식:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        {survey.obesity_management.body_shape_perception}
                      </span>
                    </div>
                  )}
                  {survey.obesity_management.weight_control_effort && (
                    <div style={{ fontSize: "0.9rem" }}>
                      <strong style={{ color: "#374151" }}>체중조절 노력:</strong>
                      <span style={{ color: "#5b6478", marginLeft: "0.5rem" }}>
                        {survey.obesity_management.weight_control_effort}
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </section>
        )}

        {/* Section 2: Patient Health Exam (Objective) */}
        {exam && (
          <section style={{ marginBottom: "1.75rem" }} aria-labelledby="patient-health">
            <h3 id="patient-health" style={{ margin: 0, fontSize: "1rem" }}>
              환자 상태 (검사 결과)
            </h3>
            <div style={{ marginTop: "1rem" }}>
              {/* Risk Level Badge */}
              <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#f9fafb", borderRadius: "8px" }}>
                <div style={{ fontSize: "0.9rem", color: "#374151", marginBottom: "0.5rem" }}>
                  <strong>위험도:</strong>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{
                    padding: "0.25rem 0.75rem",
                    borderRadius: "999px",
                    fontSize: "0.875rem",
                    fontWeight: 600,
                    color: getRiskLevelColor(exam.risk_level),
                    background: `${getRiskLevelColor(exam.risk_level)}15`
                  }}>
                    {exam.risk_level?.toUpperCase() || 'UNKNOWN'}
                  </span>
                  <span style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                    ({exam.risk_factors || 0}/5 위험인자)
                  </span>
                </div>
              </div>

              {/* Biomarker Cards Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                {exam.bmi !== undefined && <BiomarkerCard label="BMI" value={exam.bmi} threshold={25} unit=" kg/m²" />}
                {exam.waist_cm !== undefined && (
                  <BiomarkerCard
                    label="허리둘레"
                    value={exam.waist_cm}
                    threshold={patient?.sex === '남' || patient?.sex === 'M' ? 90 : 85}
                    unit=" cm"
                  />
                )}
                {exam.systolic_mmHg !== undefined && (
                  <BiomarkerCard label="수축기혈압" value={exam.systolic_mmHg} threshold={130} unit=" mmHg" />
                )}
                {exam.diastolic_mmHg !== undefined && (
                  <BiomarkerCard label="이완기혈압" value={exam.diastolic_mmHg} threshold={85} unit=" mmHg" />
                )}
                {exam.fbg_mg_dl !== undefined && (
                  <BiomarkerCard label="공복혈당" value={exam.fbg_mg_dl} threshold={100} unit=" mg/dL" />
                )}
                {exam.tg_mg_dl !== undefined && (
                  <BiomarkerCard label="중성지방" value={exam.tg_mg_dl} threshold={150} unit=" mg/dL" />
                )}
                {exam.hdl_mg_dl !== undefined && (
                  <BiomarkerCard
                    label="HDL"
                    value={exam.hdl_mg_dl}
                    threshold={patient?.sex === '남' || patient?.sex === 'M' ? 40 : 50}
                    unit=" mg/dL"
                    inverse
                  />
                )}
              </div>
            </div>
          </section>
        )}

        {/* Section 3: Key Points (LLM-generated) */}
        <section style={{ marginBottom: "1.75rem" }} aria-labelledby="key-points">
          <h3 id="key-points" style={{ margin: 0, fontSize: "1rem" }}>
            핵심 포인트
          </h3>
          {preparationAnalysis && preparationAnalysis.keyPoints.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "0.75rem" }}>
              {preparationAnalysis.keyPoints.map((point, index) => (
                <li
                  key={index}
                  style={{
                    display: "flex",
                    alignItems: "start",
                    gap: "0.5rem",
                    padding: "0.75rem",
                    background: "linear-gradient(135deg, rgba(53, 97, 255, 0.05), rgba(26, 147, 111, 0.05))",
                    borderRadius: "0.5rem",
                    border: "1px solid rgba(53, 97, 255, 0.1)",
                  }}
                >
                  <span style={{ color: "#3541ff", fontWeight: "bold", fontSize: "1.1rem" }}>
                    {index + 1}.
                  </span>
                  <span style={{ color: "#374151", fontSize: "0.9rem", lineHeight: "1.5" }}>
                    {point}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: "1rem 0 0", color: "#9ca3af", fontSize: "0.9rem", fontStyle: "italic" }}>
              상담 준비 버튼을 눌러 핵심 포인트를 생성하세요.
            </p>
          )}
        </section>

        {/* Section 4: Anticipated questions (LLM-generated or demo) */}
        <section style={{ marginBottom: "1.75rem" }} aria-labelledby="anticipated-questions">
          <h3 id="anticipated-questions" style={{ margin: 0, fontSize: "1rem" }}>
            예상 질문 & 권장 답변
          </h3>
          {preparationAnalysis && preparationAnalysis.anticipatedQuestions.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "1rem" }}>
              {preparationAnalysis.anticipatedQuestions.map((qa, index) => (
                <li
                  key={index}
                  style={{
                    border: "1px solid rgba(28, 35, 51, 0.1)",
                    borderRadius: "0.9rem",
                    padding: "1rem",
                    background: "#fff"
                  }}
                >
                  <div style={{ marginBottom: "0.75rem" }}>
                    <strong style={{ color: "#3541ff", fontSize: "0.95rem" }}>❓ 질문:</strong>
                    <p style={{ margin: "0.25rem 0 0", color: "#374151", fontSize: "0.9rem" }}>
                      {qa.question}
                    </p>
                  </div>
                  <div>
                    <strong style={{ color: "#1a936f", fontSize: "0.95rem" }}>✅ 권장 답변:</strong>
                    <p style={{ margin: "0.25rem 0 0", color: "#5b6478", fontSize: "0.9rem", lineHeight: "1.5" }}>
                      {qa.answer}
                    </p>
                  </div>
                  {qa.source && (
                    <div style={{ marginTop: "0.5rem", paddingTop: "0.5rem", borderTop: "1px solid rgba(28, 35, 51, 0.08)" }}>
                      <small style={{ color: "#9ca3af", fontSize: "0.75rem" }}>
                        출처: {qa.source}
                      </small>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ) : (
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
          )}
        </section>

        {/* Section 5: Coaching observations (existing demo data) */}
        <section style={{ marginBottom: "1.75rem" }} aria-labelledby="coaching-observations">
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

        {/* Section 6: Delivery Examples (LLM-generated) */}
        {preparationAnalysis && preparationAnalysis.deliveryExamples.length > 0 && (
          <section style={{ marginBottom: "1.75rem" }} aria-labelledby="delivery-examples">
            <h3 id="delivery-examples" style={{ margin: 0, fontSize: "1rem" }}>
              전달 방식 예시
            </h3>
            <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "1rem" }}>
              {preparationAnalysis.deliveryExamples.map((example, index) => (
                <li
                  key={index}
                  style={{
                    border: "1px solid rgba(28, 35, 51, 0.1)",
                    borderRadius: "0.9rem",
                    padding: "1rem",
                    background: "#f9fafb"
                  }}
                >
                  <div style={{ marginBottom: "0.75rem" }}>
                    <strong style={{ color: "#374151", fontSize: "0.9rem" }}>{example.topic}</strong>
                  </div>
                  <div style={{ marginBottom: "0.5rem", padding: "0.5rem", background: "#fee2e2", borderLeft: "3px solid #dc2626", borderRadius: "4px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                      <span style={{ color: "#dc2626", fontWeight: "bold" }}>❌</span>
                      <strong style={{ color: "#991b1b", fontSize: "0.85rem" }}>피해야 할 표현:</strong>
                    </div>
                    <p style={{ margin: 0, color: "#7f1d1d", fontSize: "0.85rem", lineHeight: "1.4" }}>
                      {example.bad}
                    </p>
                  </div>
                  <div style={{ padding: "0.5rem", background: "#d1fae5", borderLeft: "3px solid #10b981", borderRadius: "4px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                      <span style={{ color: "#10b981", fontWeight: "bold" }}>✅</span>
                      <strong style={{ color: "#065f46", fontSize: "0.85rem" }}>권장 표현:</strong>
                    </div>
                    <p style={{ margin: 0, color: "#064e3b", fontSize: "0.85rem", lineHeight: "1.4" }}>
                      {example.good}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Section 7: Warnings (LLM-generated or default) */}
        <section aria-labelledby="warnings">
          <h3 id="warnings" style={{ margin: 0, fontSize: "1rem" }}>
            주의사항
          </h3>
          {preparationAnalysis && preparationAnalysis.warnings.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "0.75rem" }}>
              {preparationAnalysis.warnings.map((warning, index) => (
                <li
                  key={index}
                  style={{
                    padding: "0.75rem",
                    background: "#fef3c7",
                    border: "1px solid #f59e0b",
                    borderRadius: "8px",
                    display: "flex",
                    alignItems: "start",
                    gap: "0.5rem"
                  }}
                >
                  <span style={{ fontSize: "1.25rem", flexShrink: 0 }}>⚠️</span>
                  <p style={{ margin: 0, fontSize: "0.9rem", color: "#78350f", lineHeight: "1.5" }}>
                    {warning}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <div style={{ marginTop: "1rem", padding: "0.75rem", background: "#fef3c7", border: "1px solid #f59e0b", borderRadius: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "1.25rem" }}>⚠️</span>
                <strong style={{ color: "#92400e" }}>상담 시 주의</strong>
              </div>
              <p style={{ margin: 0, fontSize: "0.9rem", color: "#78350f" }}>
                의학적 판단이 필요한 질문(진단, 약물, 증상 해석)은 담당 의사와 상담하도록 안내하세요.
              </p>
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}
