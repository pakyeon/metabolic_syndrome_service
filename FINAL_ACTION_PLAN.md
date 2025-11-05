# 최종 실행 계획서
## Final Action Plan - Metabolic Syndrome Counselor Assistant

**작성일**: 2025-11-06
**프로젝트 상태**: 76% 완성 (195/256 requirements)
**목표**: 100% 완성 (Production-Ready)

---

## 📊 현재 상태 Summary

### 완성된 영역 ✅
1. **백엔드 Adaptive RAG Pipeline** (100%)
   - Dynamic strategy selection (simple/medium/complex)
   - Top-k optimization (3/5/7)
   - Parallel execution for decompose strategy
   - Mode-aware routing (preparation vs live)

2. **안전 가드레일 시스템** (100%)
   - CLEAR/CAUTION/ESCALATE classification
   - Keyword-based medical domain detection
   - Boundary case handling

3. **데이터 통합** (100% - 이번 세션)
   - PostgreSQL schema with 8 tables
   - 5 API endpoints for patient data
   - Sample data (20 patients + 2 surveys)

4. **AG-UI 투명성 프로토콜** (100%)
   - Thought/Action/Observation visualization
   - Color coding (blue/orange/green)
   - Real-time streaming display

### 미완성 영역 ❌
1. **환자 목록 UI** (0%)
2. **워크플로우 버튼** (0% - 전용 버튼 없음)
3. **세션 관리** (0%)
4. **FAQ 캐싱** (0%)
5. **프론트엔드 데이터 통합** (20% - hardcoded data 사용 중)

---

## 🎯 3-Week Implementation Roadmap

### Week 1: Critical Features (P0) - 6시간

**목표**: Core user journey 완성

#### Task 1.1: 환자 목록 UI 구현 (2시간)

**파일 생성**:
1. `frontend/components/patient/PatientList.tsx`
2. `frontend/app/patients/page.tsx`
3. `frontend/hooks/usePatients.ts`

**구현 내용**:
```typescript
// usePatients.ts
export function usePatients() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPatients() {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/v1/patients?sort_by=latest_exam_at&order=desc`
      );
      const data = await response.json();
      setPatients(data);
      setLoading(false);
    }
    fetchPatients();
  }, []);

  return { patients, loading };
}

// PatientList.tsx
export default function PatientList() {
  const { patients, loading } = usePatients();
  const router = useRouter();

  const handlePatientClick = (patientId: string) => {
    router.push(`/workspace?patient_id=${patientId}`);
  };

  return (
    <table className={styles.patientTable}>
      <thead>
        <tr>
          <th>이름</th>
          <th>나이</th>
          <th>성별</th>
          <th>최근 검사일</th>
          <th>위험도</th>
          <th>BMI</th>
          <th>혈압</th>
          <th>혈당</th>
        </tr>
      </thead>
      <tbody>
        {patients.map(patient => (
          <tr
            key={patient.patient_id}
            onClick={() => handlePatientClick(patient.patient_id)}
            className={styles.clickableRow}
          >
            <td>{patient.name}</td>
            <td>{patient.age}세</td>
            <td>{patient.sex}</td>
            <td>{formatDate(patient.latest_exam_at)}</td>
            <td>
              <span className={styles[`risk-${patient.risk_level}`]}>
                {patient.risk_level}
              </span>
            </td>
            <td>{patient.bmi?.toFixed(1)}</td>
            <td>{patient.systolic_mmHg}/{patient.diastolic_mmHg}</td>
            <td>{patient.fbg_mg_dl}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**CSS 스타일링**:
```css
.patientTable {
  width: 100%;
  border-collapse: collapse;
}

.clickableRow {
  cursor: pointer;
  transition: background-color 0.2s;
}

.clickableRow:hover {
  background-color: #f5f5f5;
}

.risk-high {
  color: #dc2626;
  font-weight: bold;
}

.risk-moderate {
  color: #f59e0b;
  font-weight: bold;
}

.risk-low {
  color: #16a34a;
  font-weight: bold;
}
```

**체크리스트**:
- [ ] usePatients hook 생성 및 API 연동
- [ ] PatientList 컴포넌트 생성
- [ ] 테이블 정렬 기능 (이름, 검사일, 위험도)
- [ ] 환자 클릭 핸들러 → workspace 이동
- [ ] 위험도별 색상 코딩
- [ ] 로딩 상태 표시
- [ ] 에러 핸들링

---

#### Task 1.2: 프론트엔드-백엔드 데이터 연결 (3시간)

**파일 수정**:
1. `frontend/hooks/usePatientData.ts` (신규)
2. `frontend/app/page.tsx` (수정)
3. `frontend/components/preparation/PreparationSidebar.tsx` (수정)

**Step 1: usePatientData Hook 생성**

```typescript
// frontend/hooks/usePatientData.ts
import { useEffect, useState } from 'react';

interface PatientData {
  patient: PatientDetail;
  latestExam: HealthExam | null;
  survey: SurveyDetail | null;
  tests: HealthExam[];
}

export function usePatientData(patientId: string | null) {
  const [data, setData] = useState<PatientData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!patientId) return;

    async function fetchAllData() {
      setLoading(true);
      setError(null);

      try {
        const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

        // Parallel API calls
        const [patientRes, examRes, surveyRes, testsRes] = await Promise.all([
          fetch(`${baseUrl}/v1/patients/${patientId}`),
          fetch(`${baseUrl}/v1/patients/${patientId}/latest-exam`),
          fetch(`${baseUrl}/v1/patients/${patientId}/survey`),
          fetch(`${baseUrl}/v1/patients/${patientId}/tests?limit=5`),
        ]);

        const [patient, latestExam, survey, tests] = await Promise.all([
          patientRes.json(),
          examRes.json(),
          surveyRes.json(),
          testsRes.json(),
        ]);

        setData({ patient, latestExam, survey, tests });
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchAllData();
  }, [patientId]);

  return { data, loading, error };
}
```

**Step 2: page.tsx 수정 - Hardcoded Data 제거**

```typescript
// frontend/app/page.tsx
import { useSearchParams } from 'next/navigation';
import { usePatientData } from '../hooks/usePatientData';

export default function HomePage() {
  const searchParams = useSearchParams();
  const patientId = searchParams.get('patient_id');

  // ❌ 제거: Hardcoded patient data (Lines 15-50)
  // const patient = { name: "김하늘", ... };

  // ✅ 추가: Real patient data from API
  const { data, loading, error } = usePatientData(patientId);

  if (!patientId) {
    return <div>환자를 선택해주세요.</div>;
  }

  if (loading) {
    return <LoadingScreen />;
  }

  if (error || !data) {
    return <ErrorScreen error={error} />;
  }

  const { patient, latestExam, survey, tests } = data;

  // useCopilotReadable에 실제 데이터 전달
  useCopilotReadable({
    description: "Current patient information",
    value: JSON.stringify({
      name: patient.name,
      age: patient.age,
      sex: patient.sex,
      riskLevel: latestExam?.risk_level,
      riskFactors: latestExam?.risk_factors,
      biomarkers: formatBiomarkers(latestExam),
      lifestyle: formatLifestyle(survey),
    }),
  });

  // ...
}

function formatBiomarkers(exam: HealthExam | null) {
  if (!exam) return [];

  return [
    {
      label: "BMI",
      value: exam.bmi?.toFixed(1),
      status: exam.bmi > 25 ? "elevated" : "optimal",
    },
    {
      label: "혈압",
      value: `${exam.systolic_mmHg}/${exam.diastolic_mmHg}`,
      status: exam.systolic_mmHg >= 130 ? "critical" : "optimal",
    },
    {
      label: "공복혈당",
      value: exam.fbg_mg_dl,
      status: exam.fbg_mg_dl >= 100 ? "elevated" : "optimal",
    },
    // ...
  ];
}

function formatLifestyle(survey: SurveyDetail | null) {
  if (!survey) return [];

  return [
    {
      title: "운동 계획",
      detail: survey.physical_activity?.exercise_plan || "없음",
    },
    {
      title: "식습관 점수",
      detail: `${survey.diet_habit?.diet_total_score || 0}/10점`,
    },
    {
      title: "정신건강 (PHQ-9)",
      detail: `${survey.mental_health?.phq9_total_score || 0}점`,
    },
  ];
}
```

**Step 3: PreparationSidebar 완성 - 6개 섹션**

```typescript
// frontend/components/preparation/PreparationSidebar.tsx
interface PreparationSidebarProps {
  patient: PatientDetail;
  exam: HealthExam | null;
  survey: SurveyDetail | null;
  preparationAnalysis?: PreparationAnalysis;  // 백엔드 준비 분석 결과
}

export default function PreparationSidebar({
  patient,
  exam,
  survey,
  preparationAnalysis,
}: PreparationSidebarProps) {
  return (
    <div className={styles.preparationSidebar}>
      {/* ✅ Section 1: 환자 기초설문지 (주관적 정보) */}
      <section className={styles.section}>
        <h3>환자 기초설문지 내용</h3>
        {survey && (
          <div className={styles.surveyContent}>
            <div className={styles.surveyItem}>
              <strong>운동 계획:</strong>
              <span>{survey.physical_activity?.exercise_plan || "없음"}</span>
            </div>
            <div className={styles.surveyItem}>
              <strong>운동 미실천 이유:</strong>
              <span>{survey.physical_activity?.no_exercise_reason || "-"}</span>
            </div>
            <div className={styles.surveyItem}>
              <strong>좌식 시간:</strong>
              <span>
                {survey.physical_activity?.sedentary_hours}시간{" "}
                {survey.physical_activity?.sedentary_minutes}분
              </span>
            </div>
            <div className={styles.surveyItem}>
              <strong>식습관 점수:</strong>
              <span>{survey.diet_habit?.diet_total_score}/10점</span>
            </div>
            <div className={styles.surveyItem}>
              <strong>아침식사:</strong>
              <span>{survey.diet_habit?.breakfast_frequency}</span>
            </div>
            <div className={styles.surveyItem}>
              <strong>정신건강 (PHQ-9):</strong>
              <span>
                {survey.mental_health?.phq9_total_score}점
                {survey.mental_health?.phq9_total_score > 10 && " (주의 필요)"}
              </span>
            </div>
            <div className={styles.surveyItem}>
              <strong>수면 시간:</strong>
              <span>
                평일 {survey.mental_health?.sleep_hours_weekday}시간,
                주말 {survey.mental_health?.sleep_hours_weekend}시간
              </span>
            </div>
            {survey.obesity_management && (
              <>
                <div className={styles.surveyItem}>
                  <strong>체형 인식:</strong>
                  <span>{survey.obesity_management.body_shape_perception}</span>
                </div>
                <div className={styles.surveyItem}>
                  <strong>체중조절 노력:</strong>
                  <span>{survey.obesity_management.weight_control_effort}</span>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {/* ✅ Section 2: 환자 상태 (객관적 정보) */}
      <section className={styles.section}>
        <h3>환자 상태 (검사 결과)</h3>
        {exam && (
          <div className={styles.examResults}>
            <div className={styles.riskLevel}>
              <strong>위험도:</strong>
              <span className={styles[`risk-${exam.risk_level}`]}>
                {exam.risk_level} ({exam.risk_factors}/5 위험인자)
              </span>
            </div>
            <div className={styles.biomarkers}>
              <BiomarkerCard label="BMI" value={exam.bmi} threshold={25} />
              <BiomarkerCard label="허리둘레" value={exam.waist_cm} threshold={patient.sex === "남" ? 90 : 85} />
              <BiomarkerCard label="수축기혈압" value={exam.systolic_mmHg} threshold={130} />
              <BiomarkerCard label="이완기혈압" value={exam.diastolic_mmHg} threshold={85} />
              <BiomarkerCard label="공복혈당" value={exam.fbg_mg_dl} threshold={100} />
              <BiomarkerCard label="중성지방" value={exam.tg_mg_dl} threshold={150} />
              <BiomarkerCard label="HDL" value={exam.hdl_mg_dl} threshold={patient.sex === "남" ? 40 : 50} inverse />
            </div>
          </div>
        )}
      </section>

      {/* ✅ Section 3: 핵심 포인트 (LLM 생성) */}
      <section className={styles.section}>
        <h3>핵심 포인트</h3>
        {preparationAnalysis?.keyPoints ? (
          <ul className={styles.keyPoints}>
            {preparationAnalysis.keyPoints.map((point, idx) => (
              <li key={idx}>{point}</li>
            ))}
          </ul>
        ) : (
          <p className={styles.placeholder}>상담 준비 분석 중...</p>
        )}
      </section>

      {/* ✅ Section 4: 예상 질문 & 권장 답변 */}
      <section className={styles.section}>
        <h3>예상 질문 & 권장 답변</h3>
        {preparationAnalysis?.anticipatedQuestions ? (
          preparationAnalysis.anticipatedQuestions.map((qa, idx) => (
            <div key={idx} className={styles.qaCard}>
              <div className={styles.question}>{qa.question}</div>
              <div className={styles.answer}>{qa.answer}</div>
            </div>
          ))
        ) : (
          <p className={styles.placeholder}>예상 질문 생성 중...</p>
        )}
      </section>

      {/* ✅ Section 5: 전달 방식 예시 */}
      <section className={styles.section}>
        <h3>전달 방식 예시</h3>
        {preparationAnalysis?.deliveryExamples ? (
          <div className={styles.deliveryExamples}>
            {preparationAnalysis.deliveryExamples.map((example, idx) => (
              <div key={idx} className={styles.exampleCard}>
                <strong>{example.topic}:</strong>
                <p className={styles.badExample}>
                  ❌ {example.bad}
                </p>
                <p className={styles.goodExample}>
                  ✅ {example.good}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.placeholder}>전달 방식 분석 중...</p>
        )}
      </section>

      {/* ✅ Section 6: 주의사항 */}
      <section className={styles.section}>
        <h3>주의사항</h3>
        {preparationAnalysis?.warnings ? (
          <div className={styles.warnings}>
            {preparationAnalysis.warnings.map((warning, idx) => (
              <div key={idx} className={styles.warningCard}>
                <span className={styles.warningIcon}>⚠️</span>
                <p>{warning}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.placeholder}>주의사항 분석 중...</p>
        )}
      </section>
    </div>
  );
}
```

**체크리스트**:
- [ ] usePatientData hook 생성
- [ ] page.tsx에서 hardcoded data 제거
- [ ] 실제 API 데이터로 교체
- [ ] PreparationSidebar 6개 섹션 구현
- [ ] BiomarkerCard 컴포넌트 생성
- [ ] 로딩 상태 표시
- [ ] 에러 핸들링
- [ ] useCopilotReadable에 실제 데이터 전달

---

#### Task 1.3: 워크플로우 전용 버튼 (1시간)

**파일 수정**: `frontend/app/page.tsx`

```typescript
// 상담 준비 시작 버튼
<button
  className={styles.preparationStartButton}
  onClick={handlePreparationStart}
  disabled={!patientId || isPreparationRunning}
>
  {isPreparationRunning ? "상담 준비 중..." : "상담 준비 시작"}
</button>

async function handlePreparationStart() {
  setIsPreparationRunning(true);

  // 백엔드 준비 분석 실행
  const response = await fetch(`${backendUrl}/v1/retrieve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: "이번 상담을 위한 준비 자료를 생성해줘.",
      context: JSON.stringify({ patient_id: patientId }),
      mode: "preparation",
    }),
  });

  const result = await response.json();
  setPreparationAnalysis(result);
  setIsPreparationRunning(false);
}

// 상담 시작 버튼
<button
  className={styles.consultationStartButton}
  onClick={handleConsultationStart}
  disabled={!preparationAnalysis}
>
  상담 시작
</button>

function handleConsultationStart() {
  setMode("live");  // 자동으로 실시간 모드 전환
  // Optional: 알림 표시
  toast.success("실시간 상담 모드로 전환되었습니다.");
}
```

**진행 상태 표시기**:
```typescript
const [preparationStage, setPreparationStage] = useState<string | null>(null);

const stages = [
  "환자 기록 검색 중...",
  "관련 운동 가이드라인 찾는 중...",
  "식단 권장사항 분석 중...",
  "예상 질문 생성 중...",
  "전달 방식 예시 생성 중...",
];

// 단계별 진행 표시
{isPreparationRunning && (
  <div className={styles.progressIndicator}>
    <div className={styles.progressBar}>
      <div
        className={styles.progressFill}
        style={{ width: `${(currentStageIndex / stages.length) * 100}%` }}
      />
    </div>
    <p className={styles.stageName}>{preparationStage}</p>
  </div>
)}
```

**체크리스트**:
- [ ] "상담 준비 시작" 버튼 추가
- [ ] 준비 분석 실행 로직
- [ ] 단계별 진행 표시기
- [ ] "상담 시작" 버튼 추가
- [ ] 자동 모드 전환
- [ ] 버튼 disable 로직

---

### Week 2: High Priority (P1) - 5시간

**목표**: 성능 최적화 및 세션 관리

#### Task 2.1: FAQ 캐싱 시스템 (3시간)

**파일 생성**:
- `backend/src/metabolic_backend/cache/faq.py`

**구현**:
```python
# backend/src/metabolic_backend/cache/faq.py
from typing import Optional, Dict, List
import json
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from sentence_transformers import SentenceTransformer

class FAQCache:
    """자주 묻는 질문 캐싱 시스템 (목표: <0.1초 응답)"""

    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        self.embeddings: np.ndarray = None
        self.questions: List[str] = []
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        self._load_cache()

    def _load_cache(self):
        """캐시 파일 로드"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)

            # 질문 임베딩 생성
            self.questions = list(self.cache.keys())
            self.embeddings = self.model.encode(self.questions)

    def get(self, question: str, similarity_threshold: float = 0.85) -> Optional[str]:
        """
        FAQ 캐시에서 답변 조회

        Args:
            question: 사용자 질문
            similarity_threshold: 유사도 임계값 (0.85 이상이면 같은 질문으로 간주)

        Returns:
            캐시된 답변 (없으면 None)
        """
        if not self.questions:
            return None

        # 질문 임베딩
        query_embedding = self.model.encode([question])[0]

        # 코사인 유사도 계산
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # 가장 유사한 질문 찾기
        max_idx = np.argmax(similarities)
        max_similarity = similarities[max_idx]

        if max_similarity >= similarity_threshold:
            matched_question = self.questions[max_idx]
            cached_data = self.cache[matched_question]

            # TTL 확인
            cached_at = datetime.fromisoformat(cached_data["cached_at"])
            ttl = timedelta(days=cached_data.get("ttl_days", 30))

            if datetime.now() - cached_at < ttl:
                return cached_data["answer"]

        return None

    def set(self, question: str, answer: str, ttl_days: int = 30):
        """캐시에 FAQ 추가"""
        self.cache[question] = {
            "answer": answer,
            "cached_at": datetime.now().isoformat(),
            "ttl_days": ttl_days,
        }

        # 캐시 파일 저장
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

        # 임베딩 재생성
        self.questions = list(self.cache.keys())
        self.embeddings = self.model.encode(self.questions)


# 사전 정의된 FAQ
PREDEFINED_FAQ = {
    "운동은 얼마나 해야 하나요?": {
        "answer": "대한비만학회 가이드라인에 따르면, 주 150분 이상의 중강도 유산소 운동을 권장합니다. 이를 주 5일로 나누면 하루 30분씩 걷기나 자전거 타기를 하시면 좋습니다.",
        "source": "대한비만학회 가이드라인 2024",
        "ttl_days": 90,
    },
    "혈당 목표치는 얼마인가요?": {
        "answer": "공복혈당은 100mg/dL 미만이 정상입니다. 100-125mg/dL은 당뇨병 전단계, 126mg/dL 이상이면 당뇨병으로 진단됩니다. 개인별 목표는 담당 의사와 상담하세요.",
        "source": "대한당뇨병학회 진료지침",
        "ttl_days": 90,
    },
    "어떤 식단이 좋나요?": {
        "answer": "채소, 통곡물, 저지방 단백질을 중심으로 한 균형 잡힌 식단을 권장합니다. 하루 3끼 규칙적으로 드시고, 가공식품과 고염분 식품은 피하세요.",
        "source": "대사증후군 식이요법 가이드",
        "ttl_days": 90,
    },
}
```

**Pipeline 통합**:
```python
# backend/src/metabolic_backend/orchestrator/pipeline.py

def run(self, question: str, *, context: str | None = None, mode: str = "live"):
    # FAQ 캐시 확인 (live 모드에서만)
    if mode == "live":
        cached_answer = self.faq_cache.get(question)
        if cached_answer:
            logging.info(f"FAQ cache hit: {question[:50]}...")
            return RetrievalOutput(
                answer=cached_answer,
                timings={"total": 0.05},  # <0.1초
                analysis=...,
                chunks=[],
                citations=[],
            )

    # 캐시 미스 - 일반 파이프라인 실행
    return self._run_pipeline(question, context, mode)
```

**체크리스트**:
- [ ] FAQCache 클래스 구현
- [ ] Semantic similarity search
- [ ] TTL (Time-To-Live) 관리
- [ ] 사전 정의 FAQ 추가
- [ ] Pipeline 통합
- [ ] 성능 테스트 (<0.1초)

---

#### Task 2.2: 세션 관리 (2시간)

**파일 생성**:
- `backend/src/metabolic_backend/api/sessions.py`

**API 엔드포인트**:
```python
# backend/src/metabolic_backend/api/sessions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

class CreateSessionRequest(BaseModel):
    patient_id: str
    user_id: str  # 상담사 ID
    metadata: Optional[dict] = {}

class SaveMessageRequest(BaseModel):
    session_id: str
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Optional[dict] = {}

@router.post("")
def create_session(request: CreateSessionRequest):
    """새 상담 세션 생성"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        session_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO sessions (id, user_id, metadata, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, created_at
            """,
            (session_id, request.user_id, json.dumps({"patient_id": request.patient_id, **request.metadata})),
        )

        result = cursor.fetchone()
        conn.commit()

        return {"session_id": result["id"], "created_at": result["created_at"]}
    finally:
        conn.close()

@router.post("/messages")
def save_message(request: SaveMessageRequest):
    """메시지 저장"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (request.session_id, request.role, request.content, json.dumps(request.metadata)),
        )

        conn.commit()
        return {"status": "saved"}
    finally:
        conn.close()

@router.get("/{session_id}/messages")
def get_session_messages(session_id: str):
    """세션의 모든 메시지 조회"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT id, role, content, metadata, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )

        messages = cursor.fetchall()
        return {"messages": [dict(msg) for msg in messages]}
    finally:
        conn.close()

@router.post("/{session_id}/summary")
async def generate_session_summary(session_id: str):
    """상담 종료 시 요약 생성 (LLM 기반)"""
    # 메시지 조회
    messages_response = get_session_messages(session_id)
    messages = messages_response["messages"]

    # LLM으로 요약 생성
    conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

    summary_prompt = f"""
    다음 상담 대화를 요약해주세요:

    {conversation_text}

    다음 형식으로 작성:
    1. 주요 논의 주제 (3-5개)
    2. 제공된 권장사항
    3. 다음 상담 시 확인 사항
    """

    # LLM 호출 (예: OpenAI)
    # summary = await generate_summary(summary_prompt)

    # 요약을 세션 metadata에 저장
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET metadata = metadata || %s::jsonb
            WHERE id = %s
            """,
            (json.dumps({"summary": "summary_placeholder"}), session_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"summary": "summary_placeholder"}
```

**프론트엔드 통합**:
```typescript
// frontend/app/page.tsx

const [sessionId, setSessionId] = useState<string | null>(null);

// 환자 선택 시 세션 생성
useEffect(() => {
  if (patientId && !sessionId) {
    createSession();
  }
}, [patientId]);

async function createSession() {
  const response = await fetch(`${backendUrl}/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      patient_id: patientId,
      user_id: "counselor_123",  // 실제 로그인한 상담사 ID
      metadata: {},
    }),
  });

  const data = await response.json();
  setSessionId(data.session_id);
}

// 메시지 전송 시 자동 저장
async function sendMessage(content: string) {
  // 기존 로직...

  // 메시지 저장
  await fetch(`${backendUrl}/v1/sessions/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      role: "user",
      content: content,
      metadata: { timestamp: new Date().toISOString() },
    }),
  });
}

// 상담 종료 시 요약 생성
async function endConsultation() {
  const response = await fetch(`${backendUrl}/v1/sessions/${sessionId}/summary`, {
    method: "POST",
  });

  const { summary } = await response.json();

  // 요약 표시
  setSummaryModal(summary);
}
```

**체크리스트**:
- [ ] 세션 생성 API
- [ ] 메시지 저장 API
- [ ] 메시지 조회 API
- [ ] 요약 생성 API (LLM 통합)
- [ ] 프론트엔드 세션 관리 로직
- [ ] 자동 메시지 저장
- [ ] 상담 종료 버튼
- [ ] 요약 표시 모달

---

### Week 3: Polish (P2) - 4.5시간

**목표**: UI 개선 및 사용자 경험 향상

#### Task 3.1: UI 동적 레이아웃 (2시간)

**CSS 수정**:
```css
/* frontend/app/page.module.css */

.pageLayout {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 1rem;
  transition: grid-template-columns 0.3s ease;
}

.pageLayout.liveMode {
  grid-template-columns: 280px 1fr 60px;  /* 우측 사이드바 축소 */
}

.rightPanel {
  background: white;
  border-radius: 8px;
  padding: 1rem;
  overflow-y: auto;
  transition: all 0.3s ease;
}

.rightPanel.collapsed {
  width: 60px;
  padding: 0.5rem;
}

.rightPanel.collapsed .sectionContent {
  display: none;  /* 내용 숨김 */
}

.rightPanel.collapsed .sectionTitle {
  writing-mode: vertical-lr;  /* 제목을 세로로 */
  text-align: center;
}

/* 토글 버튼 */
.sidebarToggle {
  position: absolute;
  right: 10px;
  top: 10px;
  background: #3541ff;
  color: white;
  border: none;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  cursor: pointer;
  transition: transform 0.3s ease;
}

.sidebarToggle:hover {
  transform: scale(1.1);
}
```

**JSX**:
```typescript
<aside className={`${styles.rightPanel} ${mode === "live" ? styles.collapsed : ""}`}>
  <button
    className={styles.sidebarToggle}
    onClick={() => setSidebarExpanded(!sidebarExpanded)}
    title={sidebarExpanded ? "사이드바 접기" : "사이드바 펼치기"}
  >
    {sidebarExpanded ? "«" : "»"}
  </button>

  {sidebarExpanded && <PreparationSidebar ... />}
  {!sidebarExpanded && <CompactSidebarIcons ... />}
</aside>
```

**체크리스트**:
- [ ] CSS grid 동적 변경
- [ ] 사이드바 접기/펼치기 애니메이션
- [ ] 컴팩트 아이콘 뷰 생성
- [ ] 토글 버튼 추가
- [ ] 모드 전환 시 자동 축소

---

#### Task 3.2: 답변 카드 스타일링 (1시간)

**컴포넌트 생성**:
```typescript
// frontend/components/chat/AnswerCard.tsx

interface AnswerCardProps {
  answer: string;
  citations: Citation[];
}

export default function AnswerCard({ answer, citations }: AnswerCardProps) {
  // 답변에서 핵심 권장사항 추출 (첫 문단 또는 굵은 글씨)
  const keyPoints = extractKeyPoints(answer);
  const details = extractDetails(answer);

  return (
    <div className={styles.answerCard}>
      {/* 핵심 권장사항 */}
      <div className={styles.keyPoints}>
        <strong>핵심 권장사항</strong>
        <p>{keyPoints}</p>
      </div>

      {/* 상세 설명 */}
      {details && (
        <div className={styles.details}>
          <p>{details}</p>
        </div>
      )}

      {/* 출처 */}
      {citations.length > 0 && (
        <div className={styles.citations}>
          <small>
            <strong>출처:</strong>
            {citations.map((cit, idx) => (
              <span key={idx}>
                {cit.source}
                {idx < citations.length - 1 && ", "}
              </span>
            ))}
          </small>
        </div>
      )}
    </div>
  );
}

function extractKeyPoints(answer: string): string {
  // 첫 두 문장 추출
  const sentences = answer.split(/[.!?]\s+/);
  return sentences.slice(0, 2).join(". ") + ".";
}

function extractDetails(answer: string): string | null {
  const sentences = answer.split(/[.!?]\s+/);
  if (sentences.length <= 2) return null;
  return sentences.slice(2).join(". ");
}
```

**CSS**:
```css
.answerCard {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem;
  margin: 1rem 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.keyPoints {
  margin-bottom: 1rem;
}

.keyPoints strong {
  display: block;
  color: #1f2937;
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
}

.keyPoints p {
  font-size: 1.05rem;
  font-weight: 600;
  color: #374151;
  line-height: 1.6;
}

.details {
  margin-bottom: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #f3f4f6;
}

.details p {
  font-size: 0.95rem;
  color: #6b7280;
  line-height: 1.5;
}

.citations {
  padding-top: 0.75rem;
  border-top: 1px solid #f3f4f6;
}

.citations small {
  font-size: 0.85rem;
  color: #9ca3af;
}

.citations strong {
  color: #6b7280;
}
```

**체크리스트**:
- [ ] AnswerCard 컴포넌트 생성
- [ ] 핵심 권장사항 자동 추출
- [ ] 상세 설명 분리
- [ ] 출처 표시
- [ ] 카드 스타일링

---

#### Task 3.3: 참고 자료 패널 (1.5시간)

**컴포넌트 생성**:
```typescript
// frontend/components/references/ReferencesPanel.tsx

interface ReferencesPanelProps {
  citations: Citation[];
}

export default function ReferencesPanel({ citations }: ReferencesPanelProps) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  return (
    <aside className={styles.referencesPanel}>
      <h3>참고 문서</h3>

      {citations.length === 0 && (
        <p className={styles.empty}>참고 문서가 없습니다.</p>
      )}

      {citations.map((citation, idx) => (
        <div
          key={idx}
          className={styles.citationCard}
          onClick={() => setSelectedCitation(citation)}
        >
          <div className={styles.citationHeader}>
            <strong>{citation.title}</strong>
            <span className={styles.citationBadge}>출처</span>
          </div>

          <p className={styles.citationSection}>
            섹션: {citation.section}
          </p>

          {citation.relevance_score && (
            <div className={styles.relevanceBar}>
              <div
                className={styles.relevanceFill}
                style={{ width: `${citation.relevance_score * 100}%` }}
              />
            </div>
          )}
        </div>
      ))}

      {/* 문서 상세 모달 */}
      {selectedCitation && (
        <Modal onClose={() => setSelectedCitation(null)}>
          <h2>{selectedCitation.title}</h2>
          <p><strong>출처:</strong> {selectedCitation.source}</p>
          <p><strong>섹션:</strong> {selectedCitation.section}</p>

          <div className={styles.documentContent}>
            {selectedCitation.content}
          </div>
        </Modal>
      )}
    </aside>
  );
}
```

**CSS**:
```css
.referencesPanel {
  position: fixed;
  right: 0;
  top: 60px;
  bottom: 0;
  width: 300px;
  background: white;
  border-left: 1px solid #e5e7eb;
  padding: 1rem;
  overflow-y: auto;
  z-index: 10;
}

.citationCard {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.citationCard:hover {
  background: #f3f4f6;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.citationHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.citationBadge {
  background: #3541ff;
  color: white;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.citationSection {
  font-size: 0.85rem;
  color: #6b7280;
}

.relevanceBar {
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  margin-top: 0.5rem;
  overflow: hidden;
}

.relevanceFill {
  height: 100%;
  background: #3541ff;
  transition: width 0.3s;
}
```

**체크리스트**:
- [ ] ReferencesPanel 컴포넌트 생성
- [ ] Citation 카드 표시
- [ ] 관련도 점수 시각화
- [ ] 클릭 시 문서 상세 모달
- [ ] 스타일링

---

## 📋 Acceptance Criteria (완료 기준)

### Critical Features (Week 1)
- [ ] 환자 목록에서 20명의 환자를 볼 수 있다
- [ ] 환자를 클릭하면 상담 준비 페이지로 이동한다
- [ ] 환자 데이터가 백엔드 API에서 실시간으로 로드된다
- [ ] 준비 사이드바에 6개 섹션이 모두 표시된다
- [ ] "상담 준비 시작" 버튼을 누르면 단계별 진행 표시가 나온다
- [ ] "상담 시작" 버튼을 누르면 자동으로 실시간 모드로 전환된다

### High Priority (Week 2)
- [ ] 자주 묻는 질문에 대한 답변이 0.1초 이내에 반환된다
- [ ] 세션이 생성되고 모든 메시지가 자동 저장된다
- [ ] 상담 종료 시 요약이 자동 생성된다

### Polish (Week 3)
- [ ] 모드 전환 시 레이아웃이 부드럽게 애니메이션된다
- [ ] 답변이 카드 형태로 표시되고 핵심 권장사항이 강조된다
- [ ] 참고 문서 패널에서 출처를 클릭하여 원문을 볼 수 있다

---

## 🚀 Deployment Checklist

### Pre-Production
- [ ] 모든 환경 변수 설정 확인
  - `DATABASE_URL` (Neon PostgreSQL)
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - `OPENAI_API_KEY`
  - `NEXT_PUBLIC_BACKEND_URL`
- [ ] 데이터베이스 마이그레이션 실행
  ```bash
  psql "$DATABASE_URL" -f backend/sql/schema.sql
  psql "$DATABASE_URL" -f backend/sql/001_add_patient_tables.sql
  python backend/scripts/populate_patient_data.py
  ```
- [ ] 백엔드 테스트 실행
  ```bash
  cd backend
  uv run pytest tests/
  ```
- [ ] 프론트엔드 빌드 테스트
  ```bash
  cd frontend
  npm run build
  ```

### Production
- [ ] Vercel에 프론트엔드 배포
- [ ] Railway/Render에 백엔드 배포
- [ ] 환경 변수 프로덕션 설정
- [ ] Health check 엔드포인트 확인 (`/healthz`)
- [ ] E2E 테스트 실행 (Playwright)
- [ ] 성능 모니터링 설정

---

## 📞 Support & Next Steps

### 완료 후 검증
1. ✅ 모든 Acceptance Criteria 통과
2. ✅ Playwright E2E 테스트 통과
3. ✅ 성능 SLA 달성
   - Live mode: <5s (분석 <2s)
   - Preparation mode: <30s
   - FAQ cache: <0.1s
4. ✅ 보안 감사 통과
   - 의학적 판단 회피 100%
   - 환자 데이터 보호 (GDPR/HIPAA 준수)

### 추가 개선 사항 (Optional)
- [ ] 다국어 지원 (영어, 한국어)
- [ ] 모바일 반응형 디자인
- [ ] 음성 입력 지원
- [ ] 실시간 협업 (여러 상담사 동시 작업)
- [ ] AI 피드백 학습 시스템

---

**작성자**: Claude Code
**최종 업데이트**: 2025-11-06
**다음 검토**: Week 1 완료 후 (2025-11-13)
