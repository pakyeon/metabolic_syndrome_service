# Backend Deployment Checklist

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `METABOLIC_ENV` | Deployment environment label (`local`, `staging`, `prod`). | `local` |
| `METABOLIC_DATA_ROOT` | Path to document corpora. | `data` |
| `METABOLIC_CACHE_ROOT` | Cache directory for ingestion artifacts. | `.cache/metabolic_backend` |
| `CHROMA_PERSIST_DIR` | Directory for persisted Chroma collection. | `.cache/metabolic_backend/vector_store/chroma_db` |
| `CHROMA_COLLECTION` | Chroma collection name for document chunks. | `metabolic_chunks` |
| `METABOLIC_PG_HOST` / `PORT` / `USER` / `PASSWORD` / `DATABASE` | PostgreSQL connection for transactional data. | `localhost`, `5432`, `postgres`, `postgres`, `metabolic` |
| `METABOLIC_PG_USE_SSL` | Enable SSL for PostgreSQL. | `false` |
| `METABOLIC_NEO4J_URI` / `USER` / `PASSWORD` | Graph database credentials. | `bolt://localhost:7687`, `neo4j`, `neo4j` |
| `METABOLIC_EMBEDDING_MODEL` | Sentence embedding model identifier. | `sentence-transformers/all-MiniLM-L6-v2` |
| `METABOLIC_SAFETY_LATENCY_BUDGET` | Safety classifier latency budget (seconds). | `2.0` |
| `METABOLIC_LOG_FORMAT` | `json` for structured logs or `plain` for CLI. | `plain` |
| `METABOLIC_DISABLE_INGESTION` | Set to `1` to skip ingestion in constrained environments (tests). | unset |

## Run Commands

```bash
uv run uvicorn metabolic_backend.api.server:app --host 0.0.0.0 --port 8000
```

Ensure ingestion artifacts exist or mount pre-generated chunks; otherwise ingestion will run on startup.

## Observability

- `/metrics/latency`: JSON snapshot of recorded durations.
- Logs emit `latency_recorded` events; forward to your logging stack for alerts.
