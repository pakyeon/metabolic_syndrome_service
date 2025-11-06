# 프론트엔드 UI 대규모 리팩토링 가이드

## 완료된 백엔드 작업 ✅

1. **langchain-openai 설치 완료**
   - `uv add langchain-openai` 실행 완료
   - 버전: 1.0.2

2. **LLMClient 완전 재작성**
   - 파일: `backend/src/metabolic_backend/providers/llm.py`
   - ChatOpenAI + HumanMessage 사용
   - gpt-5-nano, gpt-5-mini 모델명 적용
   - reasoning_effort=minimal 파라미터 추가

3. **Vector DB 적재 가이드 작성**
   - 파일: `VECTOR_DB_SETUP_GUIDE.md`
   - 스키마 적용 → 파이프라인 실행 순서 명시

## 남은 프론트엔드 작업 📋

### Phase 1: CSS 그리드 시스템 재설계

**파일**: `frontend/app/workspace.module.css`

**변경 내용**:
```css
/* 기존 3-컬럼 구조 */
.workspace {
  grid-template-columns: 22rem minmax(0, 1fr) 25rem;
}

/* 신규 2-컬럼 + 옵션 사이드바 구조 */
.workspace {
  display: grid;
  grid-template-columns: 16rem minmax(0, 1fr) 28rem;
  gap: 1.5rem;
  padding: 0 2rem 2rem;
  min-height: 100vh;
}

/* 왼쪽 사이드바 접힘 */
.workspace[data-left-collapsed="true"] {
  grid-template-columns: 3rem minmax(0, 1fr) 28rem;
}

/* 오른쪽 사이드바 접힘 */
.workspace[data-right-collapsed="true"] {
  grid-template-columns: 16rem minmax(0, 1fr) 0;
}

/* 양쪽 모두 접힘 */
.workspace[data-left-collapsed="true"][data-right-collapsed="true"] {
  grid-template-columns: 3rem minmax(0, 1fr) 0;
}
```

**새로운 클래스 추가**:
```css
/* 왼쪽 사이드바 */
.leftSidebar {
  background: #ffffffee;
  border-radius: 1rem;
  box-shadow: 0 12px 24px rgba(28, 35, 51, 0.08);
  border: 1px solid rgba(28, 35, 51, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 1.5rem;
  max-height: calc(100vh - 3rem);
  align-self: flex-start;
  transition: width 0.3s ease;
}

.leftSidebar.collapsed {
  width: 3rem;
}

/* 오른쪽 사이드바 탭 구조 */
.rightSidebar {
  background: #ffffffee;
  border-radius: 1rem;
  box-shadow: 0 12px 24px rgba(28, 35, 51, 0.08);
  border: 1px solid rgba(28, 35, 51, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 1.5rem;
  max-height: calc(100vh - 3rem);
  align-self: flex-start;
}

.rightSidebarTabs {
  display: flex;
  border-bottom: 1px solid rgba(28, 35, 51, 0.08);
  padding: 0.5rem 1rem;
  gap: 0.5rem;
}

.tabButton {
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  border-radius: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.tabButton.active {
  background: #3541ff;
  color: white;
}

.tabButton:hover:not(.active) {
  background: rgba(53, 65, 255, 0.1);
}
```

### Phase 2: LeftSidebar 컴포넌트 생성

**파일**: `frontend/components/navigation/LeftSidebar.tsx` (신규)

```typescript
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
```

**CSS**: `frontend/components/navigation/LeftSidebar.module.css` (신규)

```css
.sidebar {
  background: #ffffffee;
  border-radius: 1rem;
  box-shadow: 0 12px 24px rgba(28, 35, 51, 0.08);
  border: 1px solid rgba(28, 35, 51, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.sidebar.collapsed {
  width: 3rem;
}

.header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(28, 35, 51, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h2 {
  margin: 0;
  font-size: 1.125rem;
}

.toggleBtn {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  color: #6b7280;
  transition: color 0.2s;
}

.toggleBtn:hover {
  color: #3541ff;
}

.nav {
  display: flex;
  padding: 0.5rem;
  gap: 0.25rem;
  border-bottom: 1px solid rgba(28, 35, 51, 0.08);
}

.nav button {
  flex: 1;
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  border-radius: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.nav button.active {
  background: #3541ff;
  color: white;
}

.nav button:hover:not(.active) {
  background: rgba(53, 65, 255, 0.1);
}

.body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.patientCard {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 0.5rem;
}

.patientCard:hover {
  background: rgba(53, 65, 255, 0.05);
}

.patientCard.selected {
  background: rgba(53, 65, 255, 0.1);
  border: 1px solid #3541ff;
}

.avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  background: #3541ff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 1rem;
}

.info {
  flex: 1;
}

.name {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
}

.risk {
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  display: inline-block;
}

.risk.low {
  background: rgba(26, 147, 111, 0.1);
  color: #1a936f;
}

.risk.moderate {
  background: rgba(255, 140, 66, 0.1);
  color: #ff8c42;
}

.risk.high {
  background: rgba(215, 38, 61, 0.1);
  color: #d7263d;
}

/* Collapsed state */
.iconBar {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem 0.5rem;
}

.iconBar button {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 0.5rem;
  transition: background 0.2s;
}

.iconBar button:hover {
  background: rgba(53, 65, 255, 0.1);
}
```

### Phase 3: RightSidebar 컴포넌트 생성

**파일**: `frontend/components/sidebar/RightSidebar.tsx` (신규)

```typescript
"use client";

import { useState } from "react";
import styles from "./RightSidebar.module.css";
import { InsightsTab } from "./InsightsTab";
import { ReferencesPanel, Citation } from "../references/ReferencesPanel";

type TabType = "insights" | "references";

interface RightSidebarProps {
  // Insights 탭용 props
  patient: any;
  exam: any;
  survey: any;
  preparationAnalysis: any;
  highlightedQuestion?: string | null;

  // References 탭용 props
  citations: Citation[];

  // 상태 제어
  activeTab?: TabType;
  collapsed: boolean;
  onToggle: () => void;
}

export function RightSidebar({
  patient,
  exam,
  survey,
  preparationAnalysis,
  highlightedQuestion,
  citations,
  activeTab: controlledTab,
  collapsed,
  onToggle,
}: RightSidebarProps) {
  const [internalTab, setInternalTab] = useState<TabType>("insights");
  const activeTab = controlledTab || internalTab;

  if (collapsed) {
    return (
      <aside className={`${styles.sidebar} ${styles.collapsed}`}>
        <button onClick={onToggle} className={styles.toggleBtn}>
          »
        </button>
      </aside>
    );
  }

  return (
    <aside className={styles.sidebar}>
      <header className={styles.header}>
        <div className={styles.tabs}>
          <button
            className={`${styles.tabButton} ${activeTab === "insights" ? styles.active : ""}`}
            onClick={() => setInternalTab("insights")}
          >
            환자 & 인사이트
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === "references" ? styles.active : ""}`}
            onClick={() => setInternalTab("references")}
          >
            참고 문서
          </button>
        </div>
        <button onClick={onToggle} className={styles.toggleBtn}>
          «
        </button>
      </header>

      <div className={styles.body}>
        {activeTab === "insights" ? (
          <InsightsTab
            patient={patient}
            exam={exam}
            survey={survey}
            preparationAnalysis={preparationAnalysis}
            highlightedQuestion={highlightedQuestion}
          />
        ) : (
          <div className={styles.referencesWrapper}>
            <ReferencesPanel citations={citations} title="참고 문서" />
          </div>
        )}
      </div>
    </aside>
  );
}
```

**CSS**: `frontend/components/sidebar/RightSidebar.module.css` (신규)

```css
.sidebar {
  background: #ffffffee;
  border-radius: 1rem;
  box-shadow: 0 12px 24px rgba(28, 35, 51, 0.08);
  border: 1px solid rgba(28, 35, 51, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.sidebar.collapsed {
  width: 3rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(28, 35, 51, 0.08);
}

.tabs {
  display: flex;
  gap: 0.5rem;
}

.tabButton {
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  border-radius: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.tabButton.active {
  background: #3541ff;
  color: white;
}

.tabButton:hover:not(.active) {
  background: rgba(53, 65, 255, 0.1);
}

.toggleBtn {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  color: #6b7280;
  transition: color 0.2s;
}

.toggleBtn:hover {
  color: #3541ff;
}

.body {
  flex: 1;
  overflow-y: auto;
}

.referencesWrapper {
  padding: 1.5rem;
}
```

### Phase 4: InsightsTab 컴포넌트 생성

**파일**: `frontend/components/sidebar/InsightsTab.tsx` (신규)

**내용**: 기존 PatientSummary + PreparationSidebar의 내용을 통합
- 환자 한눈에 보기 섹션
- 설문지 요약
- 검사 결과
- 핵심 포인트
- 예상 질문 & 권장 답변
- Coaching observations
- 전달 방식 예시
- 주의사항

(코드는 PreparationSidebar.tsx의 내용을 기반으로 작성하되, PatientSummary 정보도 상단에 추가)

### Phase 5: workspace/page.tsx 수정

**주요 변경사항**:
1. LeftSidebar import 및 추가
2. PreparationSidebar 제거
3. PatientSummary 제거
4. RightSidebar 추가
5. 레이아웃 상태 관리 (leftCollapsed, rightCollapsed)
6. data-left-collapsed, data-right-collapsed 속성 추가

```typescript
const [leftSidebarCollapsed, setLeftSidebarCollapsed] = useState(false);
const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false);

<div
  className={styles.workspace}
  data-left-collapsed={leftSidebarCollapsed}
  data-right-collapsed={rightSidebarCollapsed}
>
  <LeftSidebar
    patients={patients}
    sessions={sessions}
    currentPatientId={patientId}
    collapsed={leftSidebarCollapsed}
    onToggle={() => setLeftSidebarCollapsed(!leftSidebarCollapsed)}
  />

  <ChatWorkspace ... />

  <RightSidebar
    patient={patientData?.patient}
    exam={patientData?.latestExam}
    survey={patientData?.survey}
    preparationAnalysis={preparationAnalysis}
    highlightedQuestion={lastQuestion}
    citations={citations}
    collapsed={rightSidebarCollapsed}
    onToggle={() => setRightSidebarCollapsed(!rightSidebarCollapsed)}
  />
</div>
```

### Phase 6: Citations 형식 통일 (백엔드)

**파일**: `backend/src/metabolic_backend/orchestrator/pipeline.py`

**변경**:
```python
# L294-310 부근
citations = []
if output.evidence:
    for idx, chunk in enumerate(output.evidence[:self.max_evidence]):
        citation = {
            "id": f"cite-{idx+1}",
            "title": chunk.metadata.get("document_title", "Unknown"),
            "content": chunk.text,
            "relevance_score": getattr(chunk, "score", 0.8),
            "source": chunk.source or "Unknown",
            "page": chunk.metadata.get("page"),
            "metadata": {
                "section_path": list(chunk.section_path) if chunk.section_path else [],
                "chunk_id": chunk.chunk_id,
            }
        }
        citations.append(citation)
```

### Phase 7: Citations 타입 (프론트엔드)

**파일**: `frontend/hooks/useStreamingRetrieval.ts`

**추가**:
```typescript
// SSE 파싱 시 citations 배열 처리
if (data.type === 'complete' && data.output?.citations) {
  setCitations(data.output.citations); // 이제 Citation[] 형식
}
```

## 구현 체크리스트

- [x] CSS 그리드 시스템 재설계
- [x] LeftSidebar 컴포넌트 생성
- [x] LeftSidebar CSS 작성
- [x] RightSidebar 컴포넌트 생성
- [x] RightSidebar CSS 작성
- [x] InsightsTab 컴포넌트 생성
- [x] workspace/page.tsx 레이아웃 수정
- [x] Citations 형식 통일 (백엔드)
- [x] Citations 타입 업데이트 (프론트엔드)
- [ ] Playwright 테스트 업데이트 (선택사항)

## 테스트 방법

```bash
# 프론트엔드 실행
cd frontend
npm run dev

# 백엔드 실행 (별도 터미널)
cd backend
uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000 --reload
```

브라우저에서 `http://localhost:3000` 접속 후:
1. 환자 선택 → 왼쪽 사이드바 동작 확인
2. 상담 준비 자동 시작 확인
3. 오른쪽 사이드바 탭 전환 (인사이트 ↔ 참고 문서)
4. 사이드바 접기/펼치기 동작 확인

---

**작성일**: 2025-11-06
**상태**: 백엔드 완료, 프론트엔드 가이드 제공
