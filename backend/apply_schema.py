#!/usr/bin/env python3
"""Apply database schema to Neon PostgreSQL"""
import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

print(f"Connecting to database...")
conn = psycopg.connect(DATABASE_URL)
cursor = conn.cursor()

# Read and execute VectorDB schema only (for documents and embeddings)
vectordb_schema_file = "sql/schema.sql"
print(f"Reading VectorDB schema from {vectordb_schema_file}...")

with open(vectordb_schema_file, 'r') as f:
    vectordb_schema_sql = f.read()

print("Executing VectorDB schema...")
try:
    cursor.execute(vectordb_schema_sql)
    conn.commit()
    print("✅ VectorDB schema applied successfully!")
    print("   Tables: documents, chunks, sessions, messages")
except Exception as e:
    print(f"❌ Error applying schema: {e}")
    conn.rollback()
    exit(1)
finally:
    cursor.close()
    conn.close()

print("Database setup complete!")
