# 대사증후군 상담사 어시스턴트
## Metabolic Syndrome Counselor Assistant

적응형 RAG 시스템을 활용한 대사증후군 상담사 지원 도구입니다.

---

## 빠른 시작

### 모든 서버 한 번에 실행하기

#### Linux/Mac/WSL
```bash
./start.sh
```

#### Windows
```cmd
start.bat
```

#### npm 사용 (모든 플랫폼)
```bash
npm install  # 루트 디렉토리에서
npm run dev
```

### 개별 실행

#### 백엔드만 실행
```bash
cd backend
uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000 --reload
```

#### 프론트엔드만 실행
```bash
cd frontend
npm run dev
```

---

## 기술 스택

- **Frontend**: Next.js 16 + CopilotKit + AG-UI 프로토콜
- **Backend**: Python FastAPI + LangGraph (Adaptive RAG)
- **데이터베이스**: PostgreSQL (pgvector) + Neo4j (Graphiti)

---

## 주요 기능

- ✅ 상담 준비 모드 (Pre-consultation preparation)
- ✅ 실시간 상담 모드 (Live counseling)
- ✅ Adaptive RAG (질문 복잡도에 따른 동적 전략 선택)
- ✅ 안전 가드레일 시스템 (의학적 판단 회피)

---

## 더 자세한 정보

- 개발 가이드: [CLAUDE.md](CLAUDE.md)
- 구현 전략: [구현전략.md](구현전략.md)
- 구현 현황: [구현전략_준수도_분석_보고서.md](구현전략_준수도_분석_보고서.md)

