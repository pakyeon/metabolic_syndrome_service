"use client";

import styles from "./InsightsTab.module.css";
import { PatientDetail, HealthExam, SurveyDetail } from "../../hooks/usePatientData";
import { BiomarkerCard } from "../preparation/BiomarkerCard";

type Observation = {
  label: string;
  detail: string;
  status?: "ok" | "warning" | "critical";
};

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

interface InsightsTabProps {
  patient: PatientDetail | undefined;
  exam: HealthExam | null | undefined;
  survey: SurveyDetail | null | undefined;
  preparationAnalysis: PreparationAnalysis | null | undefined;
  highlightedQuestion?: string | null;
}

const statusBadgeColor: Record<NonNullable<Observation["status"]>, string> = {
  ok: "#1a936f",
  warning: "#ff8c42",
  critical: "#d7263d"
};

// Demo coaching observations - same as before
const demoCoachingObservations: Observation[] = [
  {
    label: "운동 습관",
    detail: "주 2회 30분 걷기 실천 중. 강도와 빈도를 점진적으로 높일 준비가 되어 있음.",
    status: "ok"
  },
  {
    label: "식단 관리",
    detail: "아침 거르는 패턴. 혈당 관리 위해 규칙적 식사 중요성 강조 필요.",
    status: "warning"
  }
];

export function InsightsTab({
  patient,
  exam,
  survey,
  preparationAnalysis,
  highlightedQuestion
}: InsightsTabProps) {
  const getRiskLevelColor = (level?: string) => {
    switch (level?.toLowerCase()) {
      case 'high': return '#dc2626';
      case 'moderate': return '#f59e0b';
      case 'low': return '#16a34a';
      default: return '#6b7280';
    }
  };

  return (
    <div className={styles.insightsTab}>
      {/* Section 0: Patient Summary */}
      {patient && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>환자 한눈에 보기</h3>
          <div className={styles.patientInfo}>
            <p className={styles.patientMeta}>
              {patient.name} · {patient.age}세 · 최근 방문{" "}
              {exam?.exam_at ? new Date(exam.exam_at).toLocaleDateString("ko-KR") : "N/A"}
            </p>
            {exam?.risk_level && (
              <div className={styles.riskBadgeWrapper}>
                <span
                  className={styles.riskDot}
                  style={{ background: getRiskLevelColor(exam.risk_level) }}
                />
                <span style={{ color: getRiskLevelColor(exam.risk_level), fontWeight: 600 }}>
                  위험도: {exam.risk_level === "high" ? "높음" : exam.risk_level === "moderate" ? "중간" : "낮음"}
                </span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Section 1: Patient Survey Data (Subjective) */}
      {survey && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>내담자 기초설문지</h3>
          <div className={styles.surveyGrid}>
            {survey.physical_activity && (
              <>
                {survey.physical_activity.exercise_plan && (
                  <div className={styles.surveyItem}>
                    <strong>운동 계획:</strong>
                    <span>{survey.physical_activity.exercise_plan}</span>
                  </div>
                )}
                {survey.physical_activity.no_exercise_reason && (
                  <div className={styles.surveyItem}>
                    <strong>운동 미실천 이유:</strong>
                    <span>{survey.physical_activity.no_exercise_reason}</span>
                  </div>
                )}
                {survey.physical_activity.sedentary_hours !== undefined && (
                  <div className={styles.surveyItem}>
                    <strong>좌식 시간:</strong>
                    <span>
                      하루 {survey.physical_activity.sedentary_hours}시간{" "}
                      {survey.physical_activity.sedentary_minutes || 0}분
                    </span>
                  </div>
                )}
              </>
            )}
            {survey.diet_habit && (
              <>
                {survey.diet_habit.diet_total_score !== undefined && (
                  <div className={styles.surveyItem}>
                    <strong>식습관 점수:</strong>
                    <span>{survey.diet_habit.diet_total_score}/10점</span>
                  </div>
                )}
                {survey.diet_habit.breakfast_frequency && (
                  <div className={styles.surveyItem}>
                    <strong>아침식사:</strong>
                    <span>{survey.diet_habit.breakfast_frequency}</span>
                  </div>
                )}
              </>
            )}
            {survey.mental_health && (
              <>
                {survey.mental_health.phq9_total_score !== undefined && (
                  <div className={styles.surveyItem}>
                    <strong>정신건강 (PHQ-9):</strong>
                    <span
                      style={{
                        color: survey.mental_health.phq9_total_score > 10 ? "#dc2626" : "inherit"
                      }}
                    >
                      {survey.mental_health.phq9_total_score}점
                      {survey.mental_health.phq9_total_score > 10 && " (주의 필요)"}
                    </span>
                  </div>
                )}
                {survey.mental_health.sleep_hours_weekday !== undefined && (
                  <div className={styles.surveyItem}>
                    <strong>수면 시간:</strong>
                    <span>
                      평일 {survey.mental_health.sleep_hours_weekday}시간
                      {survey.mental_health.sleep_hours_weekend !== undefined &&
                        `, 주말 ${survey.mental_health.sleep_hours_weekend}시간`}
                    </span>
                  </div>
                )}
              </>
            )}
            {survey.obesity_management && (
              <>
                {survey.obesity_management.body_shape_perception && (
                  <div className={styles.surveyItem}>
                    <strong>체형 인식:</strong>
                    <span>{survey.obesity_management.body_shape_perception}</span>
                  </div>
                )}
                {survey.obesity_management.weight_control_effort && (
                  <div className={styles.surveyItem}>
                    <strong>체중조절 노력:</strong>
                    <span>{survey.obesity_management.weight_control_effort}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      )}

      {/* Section 2: Patient Health Exam (Objective) */}
      {exam && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>내담자 상태 (검사 결과)</h3>
          <div className={styles.examWrapper}>
            {/* Risk Level Badge */}
            <div className={styles.riskLevelCard}>
              <div className={styles.riskLevelLabel}>위험도:</div>
              <div className={styles.riskLevelBadge}>
                <span
                  className={styles.riskBadge}
                  style={{
                    color: getRiskLevelColor(exam.risk_level),
                    background: `${getRiskLevelColor(exam.risk_level)}15`
                  }}
                >
                  {exam.risk_level?.toUpperCase() || "UNKNOWN"}
                </span>
                <span className={styles.riskFactorsText}>
                  ({exam.risk_factors || 0}/5 위험인자)
                </span>
              </div>
            </div>

            {/* Biomarker Cards Grid */}
            <div className={styles.biomarkerGrid}>
              {exam.bmi !== undefined && (
                <BiomarkerCard label="BMI" value={exam.bmi} threshold={25} unit=" kg/m²" />
              )}
              {exam.waist_cm !== undefined && (
                <BiomarkerCard
                  label="허리둘레"
                  value={exam.waist_cm}
                  threshold={patient?.sex === "남" || patient?.sex === "M" ? 90 : 85}
                  unit=" cm"
                />
              )}
              {exam.systolic_mmHg !== undefined && (
                <BiomarkerCard
                  label="수축기혈압"
                  value={exam.systolic_mmHg}
                  threshold={130}
                  unit=" mmHg"
                />
              )}
              {exam.diastolic_mmHg !== undefined && (
                <BiomarkerCard
                  label="이완기혈압"
                  value={exam.diastolic_mmHg}
                  threshold={85}
                  unit=" mmHg"
                />
              )}
              {exam.fbg_mg_dl !== undefined && (
                <BiomarkerCard
                  label="공복혈당"
                  value={exam.fbg_mg_dl}
                  threshold={100}
                  unit=" mg/dL"
                />
              )}
              {exam.tg_mg_dl !== undefined && (
                <BiomarkerCard
                  label="중성지방"
                  value={exam.tg_mg_dl}
                  threshold={150}
                  unit=" mg/dL"
                />
              )}
              {exam.hdl_mg_dl !== undefined && (
                <BiomarkerCard
                  label="HDL"
                  value={exam.hdl_mg_dl}
                  threshold={patient?.sex === "남" || patient?.sex === "M" ? 40 : 50}
                  unit=" mg/dL"
                  inverse
                />
              )}
            </div>
          </div>
        </section>
      )}

      {/* Section 3: Key Points (LLM-generated) */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>핵심 포인트</h3>
        {preparationAnalysis && preparationAnalysis.keyPoints.length > 0 ? (
          <ul className={styles.keyPointsList}>
            {preparationAnalysis.keyPoints.map((point, index) => (
              <li key={index} className={styles.keyPointItem}>
                <span className={styles.keyPointNumber}>{index + 1}.</span>
                <span className={styles.keyPointText}>{point}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.emptyState}>상담 준비 버튼을 눌러 핵심 포인트를 생성하세요.</p>
        )}
      </section>

      {/* Section 4: Anticipated questions (LLM-generated) */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>예상 질문 & 권장 답변</h3>
        {preparationAnalysis && preparationAnalysis.anticipatedQuestions.length > 0 ? (
          <ul className={styles.questionsList}>
            {preparationAnalysis.anticipatedQuestions.map((qa, index) => {
              const isHighlighted =
                highlightedQuestion &&
                (qa.question.toLowerCase().includes(highlightedQuestion.toLowerCase()) ||
                  highlightedQuestion.toLowerCase().includes(qa.question.toLowerCase()));

              return (
                <li key={index} className={`${styles.questionItem} ${isHighlighted ? styles.highlighted : ""}`}>
                  <div className={styles.questionBlock}>
                    <strong className={styles.questionLabel}>❓ 질문:</strong>
                    <p className={styles.questionText}>{qa.question}</p>
                  </div>
                  <div className={styles.answerBlock}>
                    <strong className={styles.answerLabel}>✅ 권장 답변:</strong>
                    <p className={styles.answerText}>{qa.answer}</p>
                  </div>
                  {qa.source && (
                    <div className={styles.sourceBlock}>
                      <small className={styles.sourceText}>출처: {qa.source}</small>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className={styles.emptyState}>상담 준비를 실행하여 예상 질문을 생성하세요.</p>
        )}
      </section>

      {/* Section 5: Coaching observations (demo data) */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Coaching observations</h3>
        <ul className={styles.observationsList}>
          {demoCoachingObservations.map((item) => (
            <li key={item.label} className={styles.observationItem}>
              <div className={styles.observationHeader}>
                <strong>{item.label}</strong>
                {item.status && (
                  <span
                    className={styles.statusBadge}
                    style={{
                      background: `${statusBadgeColor[item.status]}1a`,
                      color: statusBadgeColor[item.status]
                    }}
                  >
                    ●{" "}
                    {item.status === "ok"
                      ? "On track"
                      : item.status === "warning"
                      ? "Watch"
                      : "Escalate"}
                  </span>
                )}
              </div>
              <p className={styles.observationDetail}>{item.detail}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* Section 6: Delivery Examples (LLM-generated) */}
      {preparationAnalysis && preparationAnalysis.deliveryExamples.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>전달 방식 예시</h3>
          <ul className={styles.deliveryList}>
            {preparationAnalysis.deliveryExamples.map((example, index) => (
              <li key={index} className={styles.deliveryItem}>
                <div className={styles.deliveryTopic}>{example.topic}</div>
                <div className={styles.badExample}>
                  <div className={styles.exampleHeader}>
                    <span className={styles.badIcon}>❌</span>
                    <strong>피해야 할 표현:</strong>
                  </div>
                  <p className={styles.exampleText}>{example.bad}</p>
                </div>
                <div className={styles.goodExample}>
                  <div className={styles.exampleHeader}>
                    <span className={styles.goodIcon}>✅</span>
                    <strong>권장 표현:</strong>
                  </div>
                  <p className={styles.exampleText}>{example.good}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Section 7: Warnings (LLM-generated or default) */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>주의사항</h3>
        {preparationAnalysis && preparationAnalysis.warnings.length > 0 ? (
          <ul className={styles.warningsList}>
            {preparationAnalysis.warnings.map((warning, index) => (
              <li key={index} className={styles.warningItem}>
                <span className={styles.warningIcon}>⚠️</span>
                <p className={styles.warningText}>{warning}</p>
              </li>
            ))}
          </ul>
        ) : (
          <div className={styles.defaultWarning}>
            <div className={styles.warningHeader}>
              <span className={styles.warningIcon}>⚠️</span>
              <strong>상담 시 주의</strong>
            </div>
            <p className={styles.warningText}>
              의학적 판단이 필요한 질문(진단, 약물, 증상 해석)은 담당 의사와 상담하도록 안내하세요.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
