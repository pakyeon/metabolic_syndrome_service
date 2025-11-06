# Vector DB (Neon PostgreSQL) 데이터 적재 가이드

## 환경 설정

### 1. 환경 변수 확인

`.env` 파일에 다음 변수들이 설정되어 있는지 확인:

```bash
# OpenAI API Key (임베딩 생성용)
OPENAI_API_KEY=sk-...

# LLM 모델 설정
SLLM_CHOICE=gpt-5-nano
LLM_CHOICE=gpt-5-mini

# Vector DB 활성화
USE_VECTOR_DB=1
METABOLIC_USE_VECTOR_DB=1

# Database URL (Neon)
DATABASE_URL=postgresql://

# Vector Table 이름
METABOLIC_VECTOR_TABLE=document_chunks

# 데이터 루트 경로
METABOLIC_DATA_ROOT='/home/gram/metabolic_syndrome_project/data'
```

## 적재 순서

### Step 1: 스키마 적용

```bash
cd backend

# Neon DB에 스키마 적용
DATABASE_URL="postgresql://" uv run python apply_schema.py
```

**예상 출력**:
```
✓ documents 테이블 생성
✓ chunks 테이블 생성 (embedding vector(1536))
✓ sessions 테이블 생성
✓ messages 테이블 생성
✓ match_chunks() 함수 생성
✓ hybrid_search() 함수 생성
```

### Step 2: 기존 데이터 확인 (선택사항)

```bash
# 테이블 상태 확인
DATABASE_URL="postgresql://..." uv run python check_and_drop_tables.py
```

기존 데이터가 있다면:
- **유지**: 아무 작업 안 함
- **삭제 후 재적재**: 테이블 DROP 후 Step 1부터 재시작

### Step 3: 데이터 파이프라인 실행

```bash
cd backend

# 환경 변수 설정
export METABOLIC_DATA_ROOT='/home/gram/metabolic_syndrome_project/data'
export USE_VECTOR_DB=1
export METABOLIC_USE_VECTOR_DB=1

# 파이프라인 실행 (5-10분 소요)
DATABASE_URL="postgresql://" uv run python -m metabolic_backend.ingestion.pipeline
```

**진행 과정**:
```
[INFO] Scanning documents from: /data/documents/parsed
[INFO] Found 3 directories
[INFO] Processing: 20240503_2023년 서울시 대사증후군 관리사업 상담 FAQ 사례집
  → Chunking markdown files...
  → Generating embeddings (OpenAI text-embedding-3-small)...
  → Writing to vector DB...
[INFO] Processing: 20240503_2023년 서울시 대사증후군 관리사업 상담가이드북
  ...
[INFO] Processing: 20250307_2025 서울특별시 대사증후군 관리사업 안내서
  ...
[INFO] Total chunks: 847
[INFO] Vector records upserted: 847
[INFO] Building HNSW index... (if chunks > 1000)
[SUCCESS] Ingestion complete!
```

## 검증

### 데이터 적재 확인

```bash
# psql 접속
psql "$DATABASE_URL"

# 테이블 확인
SELECT COUNT(*) FROM document_chunks;
-- 예상: 500-1000개

# 샘플 데이터 확인
SELECT chunk_id, document_id, LEFT(text, 50) AS preview
FROM document_chunks
LIMIT 5;

# 임베딩 차원 확인
SELECT pg_typeof(embedding) FROM document_chunks LIMIT 1;
-- 예상: vector(1536)
```

### 유사도 검색 테스트

```sql
-- 테스트 쿼리 (더미 임베딩)
SELECT chunk_id, text, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM document_chunks
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 3;
```

실제 검색은 백엔드 API를 통해:
```bash
curl -X POST http://localhost:8000/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "question": "혈당이 높을 때 어떤 운동을 권장하나요?",
    "mode": "live"
  }'
```

## 트러블슈팅

### 문제 1: `psycopg` 모듈 없음
```bash
cd backend
uv add psycopg[binary]
```

### 문제 2: OpenAI API Key 에러
```
Error: Invalid API key
```
→ `.env` 파일에 `OPENAI_API_KEY` 확인

### 문제 3: 연결 타임아웃
```
Error: could not connect to server
```
→ Neon DB URL 확인 (인증 정보, sslmode 등)

### 문제 4: pgvector 확장 없음
```
Error: type "vector" does not exist
```
→ Neon DB 콘솔에서 `CREATE EXTENSION vector;` 실행

## 재적재 방법

기존 데이터 삭제 후 재적재:

```bash
cd backend

# 1. 테이블 삭제
DATABASE_URL="..." uv run python -c "
import psycopg
conn = psycopg.connect('YOUR_DATABASE_URL')
cur = conn.cursor()
cur.execute('DROP TABLE IF EXISTS document_chunks CASCADE;')
cur.execute('DROP TABLE IF EXISTS documents CASCADE;')
conn.commit()
print('Tables dropped')
"

# 2. 스키마 재적용
DATABASE_URL="..." uv run python apply_schema.py

# 3. 파이프라인 재실행
export USE_VECTOR_DB=1
DATABASE_URL="..." uv run python -m metabolic_backend.ingestion.pipeline
```

### 인덱스 효과 확인

```sql
EXPLAIN ANALYZE
SELECT * FROM document_chunks
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

`Index Scan using ...` 표시되면 인덱스 사용 중 ✅

---

**작성일**: 2025-11-06
**적용 버전**: PostgreSQL 16 + pgvector 0.5+
