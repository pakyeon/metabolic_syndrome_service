# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Metabolic Syndrome Counselor Assistant** - An adaptive RAG system that helps counselors assist patients with metabolic syndrome through evidence-based lifestyle recommendations (exercise, diet, lifestyle). The system explicitly avoids medical diagnosis, drug prescriptions, and treatment decisions.

- **Frontend**: Next.js 16 + CopilotKit, implements dual-mode counseling (preparation vs. live)
- **Backend**: Python FastAPI + LangGraph, adaptive RAG with vector (pgvector) and graph (Neo4j/Graphiti) retrieval
- **Data**: PostgreSQL (Neon) for vector embeddings, Neo4j for knowledge graphs

## Development Commands

### Backend (Python 3.11)

Located in `/backend`. Uses `uv` for package management.

```bash
# Install dependencies
cd backend
uv sync

# Run development server
uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000 --reload

# Run tests
uv run pytest tests/

# Run specific test
uv run pytest tests/test_api.py::test_healthcheck -v

# Run ingestion pipeline manually
uv run python -m metabolic_backend.ingestion.pipeline

# Verify database schema
uv run python scripts/verify_schema.py

# Code formatting (if configured)
uv run black src/ --line-length 100
uv run isort src/
```

### Frontend (Next.js 16)

Located in `/frontend`. Uses npm.

```bash
# Install dependencies
cd frontend
npm install

# Development server
npm run dev          # Runs on http://localhost:3000

# Production build
npm run build
npm run start

# Linting
npm run lint

# E2E tests (Playwright)
npm run test:e2e
npx playwright test --project=chromium
npx playwright show-report  # View test report
```

## Architecture Overview

### Backend: Adaptive RAG Pipeline

The core orchestration happens in `backend/src/metabolic_backend/orchestrator/pipeline.py` using LangGraph state graphs with two operational modes:

**Live Mode** (real-time counseling, <5s latency target):
1. **Analysis** → Question classification (domain, complexity, safety)
2. **Safety** → Guardrails check (clear/caution/escalate)
3. **Rewrite** → Query optimization
4. **Routing** → Dynamic strategy selection:
   - `vector`: Simple questions, top-3 vector search
   - `graph`: Relationship queries, top-5 graph search
   - `decompose`: Complex questions, parallel sub-query execution
5. **Retrieval** → Vector and/or Graph retrieval
6. **Merge** → Evidence deduplication and ranking
7. **Synthesize** → Answer generation with citations

**Preparation Mode** (pre-consultation, 20-30s budget):
1. **Patient Analysis** → Parse patient state from survey/test data
2. **History Analysis** → Review previous consultation patterns
3. **Question Generation** → Predict 5 likely patient questions
4. **Answer Preparation** → Pre-compute recommended responses (parallel execution)
5. **Delivery Examples** → Generate patient-friendly communication templates

### Strategy Selection Logic

Located in `pipeline.py:_select_strategy()`:
- **Relationship keywords** (`관계`, `영향`, `비교`, etc.) → Graph search
- **Multiple connectors** (`그리고`, `및`, `또`) or compound questions → Decompose
- **Simple queries** → Vector search
- **Mode affects top-k**: Live uses smaller k (3-5), Preparation uses larger k (5-7)

### Safety Classification

`backend/src/metabolic_backend/analysis/classifier.py`:
- **ESCALATE**: Drug-related (`약`, `처방`, `복용량`), emergency (`응급`, `심장`)
- **CAUTION**: Medical context (`진단`, `질환`, `위험`, `검사`)
- **CLEAR**: Exercise/diet/lifestyle questions

System **never** provides:
- Drug recommendations or dosage adjustments
- Medical diagnoses or prognoses
- Treatment decisions
- Symptom interpretations requiring medical judgment

### Frontend: Dual-Mode UX

**Key Components**:
- `app/page.tsx` - Main workspace with mode switching
- `components/chat/ChatWorkspace.tsx` - Chat interface
- `components/preparation/PreparationSidebar.tsx` - Pre-consultation analysis display
- `components/chat/TransparencyTimeline.tsx` - AG-UI protocol visualization (reasoning/action/observation)
- `hooks/useStreamingRetrieval.ts` - Server-Sent Events (SSE) streaming hook

**Critical Bug Fixed**: `useStreamingRetrieval.ts:103` was overwriting messages instead of accumulating them. Now uses `[...prev.messages, ...newMessages]`.

## Database Schema

PostgreSQL schema at `backend/sql/schema.sql`:

**Core Tables**:
- `documents` - Source documents with full text
- `chunks` - Document fragments with `vector(1536)` embeddings (OpenAI text-embedding-3-small)
- `sessions` - Conversation sessions
- `messages` - Chat history

**Key Functions**:
- `match_chunks(query_embedding, match_count)` - Vector similarity search
- `hybrid_search(query_embedding, query_text, match_count, text_weight)` - Combined vector + full-text

**Setup**: `psql "$DATABASE_URL" -f backend/sql/schema.sql`

## Configuration & Environment

### Backend `.env` (required)

```bash
# Database
DATABASE_URL=postgresql://user:pass@host/dbname
METABOLIC_VECTOR_TABLE=document_chunks

# Neo4j (optional, for graph retrieval)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# LLM Providers
OPENAI_API_KEY=sk-...

# Feature Flags
METABOLIC_USE_VECTOR_DB=1       # Enable vector DB
METABOLIC_USE_GRAPH_DB=1        # Enable graph DB
METABOLIC_DISABLE_INGESTION=1   # Skip document ingestion (tests)

# Performance
METABOLIC_VECTOR_TOP_K=3        # Default vector results
METABOLIC_GRAPH_TOP_K=5         # Default graph results
METABOLIC_SAFETY_LATENCY_BUDGET=2.0  # Max seconds for safety check
```

### Frontend `.env.local`

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_COPILOTKIT_API_KEY=dummy_key_for_testing
```

## Data Pipeline

**Document Structure**: `data/documents/parsed/` contains markdown files from parsed PDFs
**Pipeline**: `backend/src/metabolic_backend/ingestion/pipeline.py`

1. **Chunking** (`ingestion/chunking.py`) - Semantic chunking with heading-aware hierarchy
2. **Embedding** (`ingestion/embedding.py`) - Batch embedding with caching
3. **Storage** (`ingestion/stores.py`) - Writes to both PostgreSQL (vector) and Neo4j (graph)

**Output**: `backend/.cache/metabolic_backend/vector_store/chunks.jsonl`

## API Endpoints

**Base URL**: `http://localhost:8000`

### POST `/v1/retrieve`
Synchronous retrieval (returns complete response)
```json
{
  "question": "혈당이 높은데 어떤 운동을 권장하면 좋을까요?",
  "context": "환자 정보...",
  "mode": "live"  // or "preparation"
}
```

### POST `/v1/retrieve/stream`
Streaming retrieval (Server-Sent Events)
- Returns LangGraph node updates in real-time
- Event types: `node_update`, `complete`, `error`
- Each node includes `observations` with AG-UI protocol messages

### GET `/metrics/latency`
Performance metrics (analysis, retrieval, synthesis timings)

### GET `/healthz`
Health check

## Testing Strategy

### Backend Tests
Located in `backend/tests/`:
- `test_api.py` - FastAPI endpoint tests
- `test_guardrails.py` - Safety classification tests

### Frontend E2E Tests
Located in `frontend/tests/e2e/` using Playwright:
- `dual-mode.spec.ts` - Mode switching workflow
- `quick-actions.spec.ts` - Quick action buttons
- `safety-system.spec.ts` - Safety level visualization

**Run**: `npm run test:e2e` (requires backend on port 8000)

**Known Issue**: Backend JSON serialization error with `QuestionAnalysisResult` - tests use mocked responses.

## Key Implementation Details

### Parallel Execution
`pipeline.py:_node_decompose()` uses `asyncio.gather()` to retrieve sub-questions concurrently, reducing decompose strategy latency from ~15s to ~7s.

### Preparation Mode Optimization
`pipeline.py:_node_prep_prepare_answers()` prepares all expected question answers in parallel rather than sequentially.

### AG-UI Protocol
Frontend displays pipeline reasoning transparently:
- **reasoning**: Question analysis results
- **action**: Retrieval strategy selection
- **observation**: Retrieved evidence counts

### Streaming Implementation
Backend uses `pipeline.stream()` which yields `{node_name: node_output}` dictionaries. Frontend parses SSE format in `useStreamingRetrieval.ts`.

## Common Pitfalls

1. **Don't skip ingestion without fallback**: Set `METABOLIC_DISABLE_INGESTION=1` only with pre-generated chunks or mock data
2. **Vector dimension mismatch**: Schema uses `vector(1536)` for OpenAI text-embedding-3-small; changing models requires schema migration
3. **Mode-specific SLA**: Live mode must respond in <5s (analysis <2s), preparation allows 20-30s
4. **Safety escalation**: When in doubt, classify as ESCALATE - system errs on side of caution
5. **Graph DB optional**: System falls back to vector-only if Neo4j unavailable

## Document Conventions

Korean language is used throughout the codebase (comments, variable names in user-facing features, prompts). LLM prompts are in Korean to optimize for the target domain.

The implementation philosophy (from `구현전략.md`): **Adaptive RAG** - "Understand the question first, dynamically select the optimal strategy for the situation" rather than applying the same pipeline to every question.
