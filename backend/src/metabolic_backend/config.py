"""Simple configuration loader for backend services."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    """Runtime configuration derived from environment variables."""

    def __init__(self) -> None:
        self.env: str = os.getenv("METABOLIC_ENV", "local")

        # Storage paths (local development defaults)
        self.data_root: Path = Path(os.getenv("METABOLIC_DATA_ROOT", "data"))
        self.cache_root: Path = Path(os.getenv("METABOLIC_CACHE_ROOT", ".cache/metabolic_backend"))

        # Connection URIs
        self.database_url: str | None = os.getenv("DATABASE_URL")

        # Vector store configuration (pgvector + PostgreSQL)
        self.pg_host: str = os.getenv("METABOLIC_PG_HOST", "localhost")
        self.pg_port: int = int(os.getenv("METABOLIC_PG_PORT", "5432"))
        self.pg_user: str = os.getenv("METABOLIC_PG_USER", "postgres")
        self.pg_password: str = os.getenv("METABOLIC_PG_PASSWORD", "postgres")
        self.pg_database: str = os.getenv("METABOLIC_PG_DATABASE", "metabolic")
        self.pg_use_ssl: bool = os.getenv("METABOLIC_PG_USE_SSL", "false").lower() == "true"
        self.vector_index_threshold: int = int(os.getenv("METABOLIC_VECTOR_INDEX_THRESHOLD", "1000"))

        # Graph store configuration (Neo4j)
        self.neo4j_uri: str = os.getenv("NEO4J_URL", os.getenv("METABOLIC_NEO4J_URI", "bolt://localhost:7687"))
        self.neo4j_user: str = os.getenv("NEO4J_USER", os.getenv("METABOLIC_NEO4J_USER", "neo4j"))
        self.neo4j_password: str = os.getenv("NEO4J_PASSWORD", os.getenv("METABOLIC_NEO4J_PASSWORD", "neo4j"))

        # Embedding model (aligned with OpenAI backend default)
        self.embedding_model: str = os.getenv(
            "EMBEDDING_MODEL", os.getenv("METABOLIC_EMBEDDING_MODEL", "text-embedding-3-small")
        )
        self.embedding_backend: str = os.getenv("METABOLIC_EMBEDDING_BACKEND", "openai")
        self.embedding_dim: int = int(os.getenv("METABOLIC_EMBEDDING_DIM", "1536"))

        # Safety classifier thresholds
        self.safety_latency_budget: float = float(
            os.getenv("METABOLIC_SAFETY_LATENCY_BUDGET", "2.0")
        )

    def dict(self) -> dict[str, object]:
        return self.__dict__.copy()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


__all__ = ["Settings", "get_settings"]
