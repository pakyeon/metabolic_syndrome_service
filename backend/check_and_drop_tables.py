#!/usr/bin/env python3
"""Check all tables and drop patient-related ones from Neon PostgreSQL"""
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

print("Connecting to Neon PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Check all existing tables
print("\n=== Checking existing tables ===")
cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename;
""")
tables = cursor.fetchall()
print(f"Found {len(tables)} tables:")
for table in tables:
    print(f"  - {table[0]}")

# Drop all tables to start fresh
print("\n=== Dropping ALL tables ===")
try:
    # Get all table names
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public';
    """)
    all_tables = [t[0] for t in cursor.fetchall()]

    if all_tables:
        # Drop all tables at once with CASCADE
        tables_list = ', '.join(all_tables)
        drop_sql = f"DROP TABLE IF EXISTS {tables_list} CASCADE;"
        print(f"Executing: {drop_sql}")
        cursor.execute(drop_sql)
        conn.commit()
        print("✅ All tables dropped successfully")
    else:
        print("No tables to drop")

except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
    exit(1)

# Verify tables are gone
print("\n=== Verifying tables ===")
cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public';
""")
remaining_tables = cursor.fetchall()
if remaining_tables:
    print(f"⚠️ Warning: {len(remaining_tables)} tables still exist:")
    for table in remaining_tables:
        print(f"  - {table[0]}")
else:
    print("✅ All tables successfully removed")

cursor.close()
conn.close()
print("\nDatabase cleanup complete!")
