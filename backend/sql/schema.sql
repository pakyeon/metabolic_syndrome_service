-- Metabolic Syndrome RAG System Database Schema
-- Adapted from agentic-rag-knowledge-graph reference implementation
--
-- This schema creates the database structure for storing documents, embeddings,
-- and conversation history for the metabolic syndrome research system.
--
-- SETUP INSTRUCTIONS:
-- 1. Ensure you have a Neon PostgreSQL database created
-- 2. Get your DATABASE_URL from Neon dashboard
-- 3. Execute this schema: psql "$DATABASE_URL" -f backend/sql/schema.sql
-- 4. Verify setup: python backend/scripts/verify_schema.py

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector for embedding storage
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID generation
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- Trigram text search

-- Clean up existing objects (for re-initialization)
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP INDEX IF EXISTS idx_chunks_embedding;
DROP INDEX IF EXISTS idx_chunks_document_id;
DROP INDEX IF EXISTS idx_documents_metadata;
DROP INDEX IF EXISTS idx_chunks_content_trgm;

-- ============================================================================
-- DOCUMENTS TABLE
-- Stores metadata and content for research documents (papers, guidelines, etc.)
-- ============================================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,                           -- Document title
    source TEXT NOT NULL,                          -- File path or URL
    content TEXT NOT NULL,                         -- Full document text
    metadata JSONB DEFAULT '{}',                   -- Custom metadata (authors, date, tags, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);
CREATE INDEX idx_documents_created_at ON documents (created_at DESC);
CREATE INDEX idx_documents_source ON documents (source);

-- ============================================================================
-- CHUNKS TABLE
-- Stores document chunks with embeddings for semantic search
-- ============================================================================
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,                         -- Chunk text content
    embedding vector(1536),                        -- OpenAI text-embedding-3-small (1536 dimensions)
    chunk_index INTEGER NOT NULL,                  -- Position in document
    metadata JSONB DEFAULT '{}',                   -- Chunk-specific metadata
    token_count INTEGER,                           -- Token count for the chunk
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity search index (IVFFlat for fast approximate search)
-- Note: lists=1 is for small datasets. Increase for production (rule of thumb: rows/1000)
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Standard indexes
CREATE INDEX idx_chunks_document_id ON chunks (document_id);
CREATE INDEX idx_chunks_chunk_index ON chunks (document_id, chunk_index);

-- Trigram index for full-text search
CREATE INDEX idx_chunks_content_trgm ON chunks USING GIN (content gin_trgm_ops);

-- ============================================================================
-- SESSIONS TABLE
-- Tracks user conversation sessions
-- ============================================================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT,                                  -- User identifier
    metadata JSONB DEFAULT '{}',                   -- Session metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE            -- Optional expiration
);

CREATE INDEX idx_sessions_user_id ON sessions (user_id);
CREATE INDEX idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX idx_sessions_created_at ON sessions (created_at DESC);

-- ============================================================================
-- MESSAGES TABLE
-- Stores conversation messages within sessions
-- ============================================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',                   -- Message metadata (tokens, model, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_session_id ON messages (session_id, created_at);

-- ============================================================================
-- CUSTOM FUNCTIONS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- match_chunks: Vector similarity search
--
-- Finds chunks most similar to the query embedding using cosine similarity.
-- Returns chunks with document metadata joined.
--
-- Parameters:
--   query_embedding: The embedding vector to search for (1536 dimensions)
--   match_count: Maximum number of results to return
--
-- Returns:
--   chunk_id: UUID of the chunk
--   document_id: UUID of the parent document
--   content: Chunk text
--   similarity: Cosine similarity score (0-1, higher is better)
--   metadata: Chunk metadata
--   document_title: Title of parent document
--   document_source: Source of parent document
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1536),
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    similarity FLOAT,
    metadata JSONB,
    document_title TEXT,
    document_source TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.document_id,
        c.content,
        1 - (c.embedding <=> query_embedding) AS similarity,
        c.metadata,
        d.title AS document_title,
        d.source AS document_source
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- hybrid_search: Combined vector and full-text search
--
-- Combines semantic similarity (vector) and keyword matching (full-text)
-- for improved relevance. Uses configurable weighting.
--
-- Parameters:
--   query_embedding: The embedding vector (1536 dimensions)
--   query_text: Text query for keyword search
--   match_count: Maximum number of results
--   text_weight: Weight for text score (0-1, default 0.3)
--                Vector weight is (1 - text_weight)
--
-- Returns:
--   chunk_id: UUID of the chunk
--   document_id: UUID of the parent document
--   content: Chunk text
--   combined_score: Weighted combination of similarity scores
--   vector_similarity: Cosine similarity score
--   text_similarity: Full-text search rank
--   metadata: Chunk metadata
--   document_title: Title of parent document
--   document_source: Source of parent document
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    text_weight FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    combined_score FLOAT,
    vector_similarity FLOAT,
    text_similarity FLOAT,
    metadata JSONB,
    document_title TEXT,
    document_source TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) AS vector_sim,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
    ),
    text_results AS (
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', query_text)) AS text_sim,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
    )
    SELECT
        COALESCE(v.chunk_id, t.chunk_id) AS chunk_id,
        COALESCE(v.document_id, t.document_id) AS document_id,
        COALESCE(v.content, t.content) AS content,
        (COALESCE(v.vector_sim, 0) * (1 - text_weight) + COALESCE(t.text_sim, 0) * text_weight) AS combined_score,
        COALESCE(v.vector_sim, 0) AS vector_similarity,
        COALESCE(t.text_sim, 0) AS text_similarity,
        COALESCE(v.metadata, t.metadata) AS metadata,
        COALESCE(v.doc_title, t.doc_title) AS document_title,
        COALESCE(v.doc_source, t.doc_source) AS document_source
    FROM vector_results v
    FULL OUTER JOIN text_results t ON v.chunk_id = t.chunk_id
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- get_document_chunks: Retrieve all chunks for a document
--
-- Gets all chunks belonging to a specific document, ordered by position.
-- Useful for displaying full document structure or debugging.
--
-- Parameters:
--   doc_id: UUID of the document
--
-- Returns:
--   chunk_id: UUID of the chunk
--   content: Chunk text
--   chunk_index: Position in document
--   metadata: Chunk metadata
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_document_chunks(doc_id UUID)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    chunk_index INTEGER,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        id AS chunk_id,
        chunks.content,
        chunks.chunk_index,
        chunks.metadata
    FROM chunks
    WHERE document_id = doc_id
    ORDER BY chunk_index;
END;
$$;

-- ----------------------------------------------------------------------------
-- update_updated_at_column: Trigger function for automatic timestamps
--
-- Automatically updates the updated_at column when a row is modified.
-- Used by triggers on documents and sessions tables.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update timestamps on modification
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- document_summaries: Aggregated document statistics
--
-- Provides an overview of each document with chunk counts and token statistics.
-- Useful for monitoring and analytics.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW document_summaries AS
SELECT
    d.id,
    d.title,
    d.source,
    d.created_at,
    d.updated_at,
    d.metadata,
    COUNT(c.id) AS chunk_count,
    AVG(c.token_count) AS avg_tokens_per_chunk,
    SUM(c.token_count) AS total_tokens
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
GROUP BY d.id, d.title, d.source, d.created_at, d.updated_at, d.metadata;

-- ============================================================================
-- VERIFICATION QUERIES
-- Run these to verify the schema was created successfully:
--
-- List extensions:
--   SELECT * FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp', 'pg_trgm');
--
-- List tables:
--   \dt
--
-- List functions:
--   \df match_chunks
--   \df hybrid_search
--   \df get_document_chunks
--
-- List indexes:
--   \di
--
-- Or run: python backend/scripts/verify_schema.py
-- ============================================================================
