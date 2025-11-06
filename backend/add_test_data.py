#!/usr/bin/env python3
"""Add test patient data to database"""
import os
import psycopg2
from datetime import datetime, timedelta

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Test patient: 김하늘 (P0001)
print("Adding test patient: 김하늘 (P0001)...")

try:
    # Insert patient
    cursor.execute("""
        INSERT INTO patients (patient_id, name, sex, age, birth_date, contact, registered_at)
        VALUES ('P0001', '김하늘', '남', 55, '1970-01-15', '010-1234-5678', CURRENT_TIMESTAMP)
        ON CONFLICT (patient_id) DO UPDATE SET
            name = EXCLUDED.name,
            sex = EXCLUDED.sex,
            age = EXCLUDED.age,
            birth_date = EXCLUDED.birth_date,
            contact = EXCLUDED.contact;
    """)

    # Insert health exam
    exam_date = datetime.now() - timedelta(days=7)
    cursor.execute("""
        INSERT INTO health_exams (
            patient_id, exam_at, facility_name,
            height_cm, weight_kg, bmi, waist_cm,
            systolic_mmHg, diastolic_mmHg,
            fbg_mg_dl, ldl_mg_dl, hdl_mg_dl, tg_mg_dl
        ) VALUES (
            'P0001', %s, '서울대학교병원',
            172.0, 85.0, 28.5, 98.0,
            140, 90,
            180.0, 145.0, 38.0, 210.0
        );
    """, (exam_date,))

    conn.commit()
    print("✅ Test patient data added successfully!")

    # Verify
    cursor.execute("SELECT name, age FROM patients WHERE patient_id = 'P0001'")
    result = cursor.fetchone()
    if result:
        print(f"   Patient: {result[0]}, Age: {result[1]}")

except Exception as e:
    print(f"❌ Error adding test data: {e}")
    conn.rollback()
    exit(1)
finally:
    cursor.close()
    conn.close()

print("Database test data setup complete!")
