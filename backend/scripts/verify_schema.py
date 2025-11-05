#!/usr/bin/env python3
"""
Database schema verification script.

This script verifies that the Neon PostgreSQL database has been properly
set up with the required schema from backend/sql/schema.sql.

Usage:
    python backend/scripts/verify_schema.py

The script checks for:
- Required PostgreSQL extensions (vector, uuid-ossp, pg_trgm)
- Required tables (documents, chunks, sessions, messages)
- Required custom functions (match_chunks, hybrid_search, get_document_chunks)
- Required indexes
- Table structure and columns

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text: str):
    """Print an info message."""
    print(f"  {text}")


async def check_extensions(conn: asyncpg.Connection) -> bool:
    """
    Check if required PostgreSQL extensions are installed.

    Args:
        conn: Database connection

    Returns:
        True if all extensions are installed
    """
    print_header("Checking PostgreSQL Extensions")

    required_extensions = ['vector', 'uuid-ossp', 'pg_trgm']
    all_ok = True

    for ext in required_extensions:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = $1",
            ext
        )

        if result > 0:
            print_success(f"Extension '{ext}' is installed")
        else:
            print_error(f"Extension '{ext}' is NOT installed")
            all_ok = False

    if not all_ok:
        print_warning("\nTo fix: Run the schema.sql file:")
        print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")

    return all_ok


async def check_tables(conn: asyncpg.Connection) -> bool:
    """
    Check if required tables exist.

    Args:
        conn: Database connection

    Returns:
        True if all tables exist
    """
    print_header("Checking Required Tables")

    required_tables = ['documents', 'chunks', 'sessions', 'messages']
    all_ok = True

    for table in required_tables:
        result = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = $1
            """,
            table
        )

        if result > 0:
            # Get row count
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print_success(f"Table '{table}' exists ({count} rows)")
            except Exception as e:
                print_success(f"Table '{table}' exists (unable to count rows: {e})")
        else:
            print_error(f"Table '{table}' does NOT exist")
            all_ok = False

    if not all_ok:
        print_warning("\nTo fix: Run the schema.sql file:")
        print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")

    return all_ok


async def check_functions(conn: asyncpg.Connection) -> bool:
    """
    Check if required custom functions exist.

    Args:
        conn: Database connection

    Returns:
        True if all functions exist
    """
    print_header("Checking Custom Functions")

    required_functions = [
        ('match_chunks', 'Vector similarity search'),
        ('hybrid_search', 'Hybrid vector + text search'),
        ('get_document_chunks', 'Retrieve document chunks'),
        ('update_updated_at_column', 'Auto-update timestamps')
    ]
    all_ok = True

    for func_name, description in required_functions:
        result = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_proc
            WHERE proname = $1
            """,
            func_name
        )

        if result > 0:
            print_success(f"Function '{func_name}' exists ({description})")
        else:
            print_error(f"Function '{func_name}' does NOT exist ({description})")
            all_ok = False

    if not all_ok:
        print_warning("\nTo fix: Run the schema.sql file:")
        print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")

    return all_ok


async def check_indexes(conn: asyncpg.Connection) -> bool:
    """
    Check if important indexes exist.

    Args:
        conn: Database connection

    Returns:
        True if key indexes exist
    """
    print_header("Checking Important Indexes")

    # Key indexes to check
    important_indexes = [
        ('idx_chunks_embedding', 'chunks', 'Vector similarity index (IVFFlat)'),
        ('idx_documents_metadata', 'documents', 'Document metadata (GIN)'),
        ('idx_chunks_content_trgm', 'chunks', 'Full-text search (trigram)'),
    ]

    all_ok = True

    for idx_name, table_name, description in important_indexes:
        result = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE indexname = $1
            AND tablename = $2
            """,
            idx_name,
            table_name
        )

        if result > 0:
            print_success(f"Index '{idx_name}' exists ({description})")
        else:
            print_error(f"Index '{idx_name}' does NOT exist ({description})")
            all_ok = False

    if not all_ok:
        print_warning("\nTo fix: Run the schema.sql file:")
        print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")

    return all_ok


async def check_table_structure(conn: asyncpg.Connection) -> bool:
    """
    Check table structure and key columns.

    Args:
        conn: Database connection

    Returns:
        True if table structures are correct
    """
    print_header("Checking Table Structure")

    # Key columns to verify
    table_checks = {
        'documents': ['id', 'title', 'source', 'content', 'metadata', 'created_at', 'updated_at'],
        'chunks': ['id', 'document_id', 'content', 'embedding', 'chunk_index', 'metadata', 'token_count'],
        'sessions': ['id', 'user_id', 'metadata', 'created_at', 'updated_at', 'expires_at'],
        'messages': ['id', 'session_id', 'role', 'content', 'metadata', 'created_at']
    }

    all_ok = True

    for table, required_columns in table_checks.items():
        # Get actual columns
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = $1
            ORDER BY ordinal_position
            """,
            table
        )

        actual_columns = {col['column_name']: col['data_type'] for col in columns}

        # Check required columns exist
        missing = []
        for col in required_columns:
            if col not in actual_columns:
                missing.append(col)

        if missing:
            print_error(f"Table '{table}' is missing columns: {', '.join(missing)}")
            all_ok = False
        else:
            print_success(f"Table '{table}' has all required columns")

    # Special check: Verify embedding column is vector type
    if 'chunks' in [t for t, _ in table_checks.items()]:
        result = await conn.fetchval(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'chunks'
            AND column_name = 'embedding'
            """
        )

        if result and 'USER-DEFINED' in str(result).upper():
            # Check if it's actually a vector type
            vector_check = await conn.fetchval(
                """
                SELECT typname
                FROM pg_type
                JOIN pg_attribute ON pg_type.oid = pg_attribute.atttypid
                JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                WHERE pg_class.relname = 'chunks'
                AND pg_attribute.attname = 'embedding'
                """
            )

            if vector_check == 'vector':
                print_success("Embedding column is correctly typed as vector(1536)")
            else:
                print_warning(f"Embedding column type: {vector_check}")
        else:
            print_error("Embedding column is not vector type")
            all_ok = False

    if not all_ok:
        print_warning("\nTo fix: Run the schema.sql file:")
        print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")

    return all_ok


async def test_vector_search(conn: asyncpg.Connection) -> bool:
    """
    Test vector search functionality.

    Args:
        conn: Database connection

    Returns:
        True if vector search works
    """
    print_header("Testing Vector Search Functionality")

    try:
        # Create a dummy vector (1536 dimensions)
        dummy_vector = '[' + ','.join(['0.1'] * 1536) + ']'

        # Test match_chunks function
        result = await conn.fetch(
            "SELECT * FROM match_chunks($1::vector, 5)",
            dummy_vector
        )

        print_success(f"Vector search (match_chunks) works (returned {len(result)} results)")

        # Test hybrid_search function
        result = await conn.fetch(
            "SELECT * FROM hybrid_search($1::vector, $2, 5, 0.3)",
            dummy_vector,
            "test query"
        )

        print_success(f"Hybrid search works (returned {len(result)} results)")

        return True

    except Exception as e:
        print_error(f"Vector search test failed: {e}")
        print_warning("\nTo fix: Run the schema.sql file:")
        print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")
        return False


async def print_database_info(conn: asyncpg.Connection):
    """
    Print useful database information.

    Args:
        conn: Database connection
    """
    print_header("Database Information")

    # PostgreSQL version
    version = await conn.fetchval("SELECT version()")
    print_info(f"PostgreSQL version: {version.split(',')[0]}")

    # Database name
    db_name = await conn.fetchval("SELECT current_database()")
    print_info(f"Database name: {db_name}")

    # Get statistics
    doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents") if await conn.fetchval(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'documents'"
    ) else 0

    chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks") if await conn.fetchval(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'chunks'"
    ) else 0

    print_info(f"Documents: {doc_count}")
    print_info(f"Chunks: {chunk_count}")


async def main():
    """Main verification function."""
    # Get database URL
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print_error("DATABASE_URL environment variable not set")
        print_info("Please set your Neon PostgreSQL connection URL in .env file")
        return 1

    print(f"{Colors.BOLD}Metabolic Syndrome RAG Database Schema Verification{Colors.END}")
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else '***'}\n")

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print_success("Connected to database")

        # Run all checks
        results = []

        results.append(await check_extensions(conn))
        results.append(await check_tables(conn))
        results.append(await check_table_structure(conn))
        results.append(await check_functions(conn))
        results.append(await check_indexes(conn))
        results.append(await test_vector_search(conn))

        # Print database info
        await print_database_info(conn)

        # Close connection
        await conn.close()

        # Summary
        print_header("Verification Summary")

        if all(results):
            print_success("All checks passed! Your database is properly configured.")
            print_info("\nYou can now run the ingestion pipeline:")
            print_info("python -m metabolic_backend.ingestion.pipeline")
            return 0
        else:
            failed_count = sum(1 for r in results if not r)
            print_error(f"{failed_count} check(s) failed")
            print_warning("\nPlease run the schema.sql file to set up your database:")
            print_info("psql \"$DATABASE_URL\" -f backend/sql/schema.sql")
            print_info("\nSchema file location: backend/sql/schema.sql")
            return 1

    except asyncpg.InvalidCatalogNameError:
        print_error("Database does not exist")
        print_info("Please create the database first in Neon dashboard")
        return 1

    except asyncpg.InvalidPasswordError:
        print_error("Authentication failed")
        print_info("Please check your DATABASE_URL credentials")
        return 1

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        print_info(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
