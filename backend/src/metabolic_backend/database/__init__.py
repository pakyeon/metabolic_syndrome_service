"""
Database utilities for metabolic syndrome RAG system.

This module provides connection pooling, session management, and
convenient wrapper functions for database operations.
"""

from .db_utils import (
    DatabasePool,
    db_pool,
    initialize_database,
    close_database,
    # Session management
    create_session,
    get_session,
    update_session,
    # Message management
    add_message,
    get_session_messages,
    # Document management
    get_document,
    list_documents,
    # Vector search
    vector_search,
    hybrid_search,
    # Chunk management
    get_document_chunks,
    # Utilities
    execute_query,
    test_connection,
)

__all__ = [
    "DatabasePool",
    "db_pool",
    "initialize_database",
    "close_database",
    "create_session",
    "get_session",
    "update_session",
    "add_message",
    "get_session_messages",
    "get_document",
    "list_documents",
    "vector_search",
    "hybrid_search",
    "get_document_chunks",
    "execute_query",
    "test_connection",
]
