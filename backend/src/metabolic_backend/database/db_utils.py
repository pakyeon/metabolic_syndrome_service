"""
Database utilities for PostgreSQL connection and operations.

This module provides:
- Connection pooling with asyncpg
- Session and message management
- Document and chunk operations
- Vector and hybrid search wrappers
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from uuid import UUID
import logging

import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DatabasePool:
    """Manages PostgreSQL connection pool with asyncpg."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database pool.

        Args:
            database_url: PostgreSQL connection URL (defaults to DATABASE_URL env var)

        Raises:
            ValueError: If no database URL is provided
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL environment variable not set. "
                "Please configure your Neon PostgreSQL connection URL."
            )

        self.pool: Optional[Pool] = None
        self._min_size = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
        self._max_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
        self._max_inactive_lifetime = int(os.getenv("DB_POOL_MAX_INACTIVE_LIFETIME", "300"))
        self._command_timeout = int(os.getenv("DB_COMMAND_TIMEOUT", "60"))

    async def initialize(self):
        """
        Create connection pool.

        Should be called during application startup.
        """
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=self._min_size,
                    max_size=self._max_size,
                    max_inactive_connection_lifetime=self._max_inactive_lifetime,
                    command_timeout=self._command_timeout
                )
                logger.info(
                    f"Database connection pool initialized "
                    f"(min={self._min_size}, max={self._max_size})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise

    async def close(self):
        """
        Close connection pool.

        Should be called during application shutdown.
        """
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.

        Usage:
            async with db_pool.acquire() as conn:
                result = await conn.fetchrow("SELECT * FROM ...")

        Yields:
            asyncpg.Connection: Database connection
        """
        if not self.pool:
            await self.initialize()

        async with self.pool.acquire() as connection:
            yield connection


# Global database pool instance
db_pool = DatabasePool()


async def initialize_database():
    """
    Initialize database connection pool.

    Call this during application startup (e.g., in FastAPI lifespan).
    """
    await db_pool.initialize()


async def close_database():
    """
    Close database connection pool.

    Call this during application shutdown (e.g., in FastAPI lifespan).
    """
    await db_pool.close()


# ============================================================================
# Session Management Functions
# ============================================================================

async def create_session(
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timeout_minutes: int = 60
) -> str:
    """
    Create a new conversation session.

    Args:
        user_id: Optional user identifier
        metadata: Optional session metadata (e.g., {"source": "web", "language": "ko"})
        timeout_minutes: Session timeout in minutes (default: 60)

    Returns:
        Session ID (UUID string)

    Example:
        session_id = await create_session(
            user_id="user123",
            metadata={"language": "ko", "source": "chatbot"}
        )
    """
    async with db_pool.acquire() as conn:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)

        result = await conn.fetchrow(
            """
            INSERT INTO sessions (user_id, metadata, expires_at)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            user_id,
            json.dumps(metadata or {}),
            expires_at
        )

        return result["id"]


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get session by ID.

    Args:
        session_id: Session UUID

    Returns:
        Session data dict or None if not found/expired

    Example:
        session = await get_session("123e4567-e89b-12d3-a456-426614174000")
        if session:
            print(f"User: {session['user_id']}")
    """
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                id::text,
                user_id,
                metadata,
                created_at,
                updated_at,
                expires_at
            FROM sessions
            WHERE id = $1::uuid
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            session_id
        )

        if result:
            return {
                "id": result["id"],
                "user_id": result["user_id"],
                "metadata": json.loads(result["metadata"]),
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat(),
                "expires_at": result["expires_at"].isoformat() if result["expires_at"] else None
            }

        return None


async def update_session(session_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Update session metadata.

    Merges new metadata with existing metadata using JSONB || operator.

    Args:
        session_id: Session UUID
        metadata: New metadata to merge

    Returns:
        True if updated successfully, False if session not found

    Example:
        success = await update_session(
            session_id,
            {"messages_count": 5, "last_topic": "diabetes"}
        )
    """
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE sessions
            SET metadata = metadata || $2::jsonb
            WHERE id = $1::uuid
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            session_id,
            json.dumps(metadata)
        )

        # result is like "UPDATE 1" or "UPDATE 0"
        return result.split()[-1] != "0"


# ============================================================================
# Message Management Functions
# ============================================================================

async def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add a message to a conversation session.

    Args:
        session_id: Session UUID
        role: Message role ('user', 'assistant', or 'system')
        content: Message content
        metadata: Optional message metadata (e.g., {"tokens": 150, "model": "gpt-4"})

    Returns:
        Message ID (UUID string)

    Raises:
        ValueError: If role is not valid

    Example:
        msg_id = await add_message(
            session_id,
            "user",
            "대사증후군에 대해 알려주세요",
            metadata={"language": "ko"}
        )
    """
    if role not in ("user", "assistant", "system"):
        raise ValueError(f"Invalid role: {role}. Must be 'user', 'assistant', or 'system'")

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO messages (session_id, role, content, metadata)
            VALUES ($1::uuid, $2, $3, $4)
            RETURNING id::text
            """,
            session_id,
            role,
            content,
            json.dumps(metadata or {})
        )

        return result["id"]


async def get_session_messages(
    session_id: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get messages for a conversation session.

    Args:
        session_id: Session UUID
        limit: Maximum number of messages to return (None = all messages)

    Returns:
        List of message dicts ordered by creation time (oldest first)

    Example:
        # Get last 10 messages
        messages = await get_session_messages(session_id, limit=10)
        for msg in messages:
            print(f"{msg['role']}: {msg['content']}")
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT
                id::text,
                role,
                content,
                metadata,
                created_at
            FROM messages
            WHERE session_id = $1::uuid
            ORDER BY created_at
        """

        if limit:
            query += f" LIMIT {limit}"

        results = await conn.fetch(query, session_id)

        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"].isoformat()
            }
            for row in results
        ]


# ============================================================================
# Document Management Functions
# ============================================================================

async def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Get document by ID.

    Args:
        document_id: Document UUID

    Returns:
        Document data dict or None if not found

    Example:
        doc = await get_document("123e4567-e89b-12d3-a456-426614174000")
        if doc:
            print(f"Title: {doc['title']}")
    """
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT
                id::text,
                title,
                source,
                content,
                metadata,
                created_at,
                updated_at
            FROM documents
            WHERE id = $1::uuid
            """,
            document_id
        )

        if result:
            return {
                "id": result["id"],
                "title": result["title"],
                "source": result["source"],
                "content": result["content"],
                "metadata": json.loads(result["metadata"]),
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat()
            }

        return None


async def list_documents(
    limit: int = 100,
    offset: int = 0,
    metadata_filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    List documents with optional filtering.

    Args:
        limit: Maximum number of documents to return
        offset: Number of documents to skip (for pagination)
        metadata_filter: Optional JSONB metadata filter (e.g., {"type": "guideline"})

    Returns:
        List of document dicts with chunk counts

    Example:
        # Get guideline documents
        docs = await list_documents(
            limit=20,
            metadata_filter={"type": "clinical_guideline"}
        )
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT
                d.id::text,
                d.title,
                d.source,
                d.metadata,
                d.created_at,
                d.updated_at,
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
        """

        params = []
        conditions = []

        if metadata_filter:
            conditions.append(f"d.metadata @> ${len(params) + 1}::jsonb")
            params.append(json.dumps(metadata_filter))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            GROUP BY d.id, d.title, d.source, d.metadata, d.created_at, d.updated_at
            ORDER BY d.created_at DESC
            LIMIT $%d OFFSET $%d
        """ % (len(params) + 1, len(params) + 2)

        params.extend([limit, offset])

        results = await conn.fetch(query, *params)

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "source": row["source"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "chunk_count": row["chunk_count"]
            }
            for row in results
        ]


# ============================================================================
# Vector Search Functions
# ============================================================================

async def vector_search(
    embedding: List[float],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Perform vector similarity search using cosine distance.

    Uses the match_chunks() SQL function defined in schema.sql.

    Args:
        embedding: Query embedding vector (1536 dimensions for text-embedding-3-small)
        limit: Maximum number of results to return

    Returns:
        List of matching chunks ordered by similarity (highest first)
        Each dict contains: chunk_id, document_id, content, similarity,
                           metadata, document_title, document_source

    Example:
        from metabolic_backend.providers.llm import get_embedding

        query = "대사증후군의 진단 기준은?"
        embedding = await get_embedding(query)
        results = await vector_search(embedding, limit=5)

        for result in results:
            print(f"Similarity: {result['similarity']:.3f}")
            print(f"Content: {result['content'][:100]}...")
    """
    async with db_pool.acquire() as conn:
        # Convert embedding to PostgreSQL vector string format
        # PostgreSQL expects '[1.0,2.0,3.0]' (no spaces after commas)
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        results = await conn.fetch(
            "SELECT * FROM match_chunks($1::vector, $2)",
            embedding_str,
            limit
        )

        return [
            {
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "content": row["content"],
                "similarity": float(row["similarity"]),
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"]),
                "document_title": row["document_title"],
                "document_source": row["document_source"]
            }
            for row in results
        ]


async def hybrid_search(
    embedding: List[float],
    query_text: str,
    limit: int = 10,
    text_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search combining vector similarity and full-text search.

    Uses the hybrid_search() SQL function defined in schema.sql.
    Combines semantic similarity (vector) with keyword matching (full-text).

    Args:
        embedding: Query embedding vector (1536 dimensions)
        query_text: Query text for keyword search
        limit: Maximum number of results to return
        text_weight: Weight for text similarity (0-1, default 0.3)
                    Vector weight is automatically (1 - text_weight)

    Returns:
        List of matching chunks ordered by combined score (highest first)
        Each dict contains: chunk_id, document_id, content, combined_score,
                           vector_similarity, text_similarity, metadata,
                           document_title, document_source

    Example:
        from metabolic_backend.providers.llm import get_embedding

        query = "diabetes hypertension"
        embedding = await get_embedding(query)
        results = await hybrid_search(
            embedding,
            query,
            limit=10,
            text_weight=0.4  # 40% keyword, 60% semantic
        )

        for result in results:
            print(f"Combined: {result['combined_score']:.3f} "
                  f"(vector: {result['vector_similarity']:.3f}, "
                  f"text: {result['text_similarity']:.3f})")
    """
    async with db_pool.acquire() as conn:
        # Convert embedding to PostgreSQL vector string format
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        results = await conn.fetch(
            "SELECT * FROM hybrid_search($1::vector, $2, $3, $4)",
            embedding_str,
            query_text,
            limit,
            text_weight
        )

        return [
            {
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "content": row["content"],
                "combined_score": float(row["combined_score"]),
                "vector_similarity": float(row["vector_similarity"]),
                "text_similarity": float(row["text_similarity"]),
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"]),
                "document_title": row["document_title"],
                "document_source": row["document_source"]
            }
            for row in results
        ]


# ============================================================================
# Chunk Management Functions
# ============================================================================

async def get_document_chunks(document_id: str) -> List[Dict[str, Any]]:
    """
    Get all chunks for a document, ordered by position.

    Uses the get_document_chunks() SQL function defined in schema.sql.

    Args:
        document_id: Document UUID

    Returns:
        List of chunk dicts ordered by chunk_index
        Each dict contains: chunk_id, content, chunk_index, metadata

    Example:
        chunks = await get_document_chunks("123e4567-e89b-12d3-a456-426614174000")
        for chunk in chunks:
            print(f"Chunk {chunk['chunk_index']}: {chunk['content'][:50]}...")
    """
    async with db_pool.acquire() as conn:
        results = await conn.fetch(
            "SELECT * FROM get_document_chunks($1::uuid)",
            document_id
        )

        return [
            {
                "chunk_id": str(row["chunk_id"]),
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"])
            }
            for row in results
        ]


# ============================================================================
# Utility Functions
# ============================================================================

async def execute_query(query: str, *params) -> List[Dict[str, Any]]:
    """
    Execute a custom SQL query.

    Use with caution - prefer the specialized functions above.

    Args:
        query: SQL query string
        *params: Query parameters

    Returns:
        List of result dicts

    Example:
        results = await execute_query(
            "SELECT COUNT(*) as count FROM documents WHERE metadata->>'type' = $1",
            "guideline"
        )
        print(f"Guideline count: {results[0]['count']}")
    """
    async with db_pool.acquire() as conn:
        results = await conn.fetch(query, *params)
        return [dict(row) for row in results]


async def test_connection() -> bool:
    """
    Test database connection.

    Returns:
        True if connection is successful, False otherwise

    Example:
        if await test_connection():
            print("Database is ready!")
        else:
            print("Database connection failed")
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


# ============================================================================
# Health Check
# ============================================================================

async def get_database_stats() -> Dict[str, Any]:
    """
    Get database statistics for monitoring.

    Returns:
        Dict with document counts, chunk counts, etc.

    Example:
        stats = await get_database_stats()
        print(f"Documents: {stats['document_count']}")
        print(f"Chunks: {stats['chunk_count']}")
    """
    async with db_pool.acquire() as conn:
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
        chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
        session_count = await conn.fetchval("SELECT COUNT(*) FROM sessions")
        message_count = await conn.fetchval("SELECT COUNT(*) FROM messages")

        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "session_count": session_count,
            "message_count": message_count,
            "pool_size": db_pool.pool.get_size() if db_pool.pool else 0,
            "pool_free": db_pool.pool.get_idle_size() if db_pool.pool else 0
        }
