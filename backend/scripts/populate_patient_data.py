#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate patient data from JSON files into PostgreSQL database.

This script reads test_data.json and survey_data.json files and inserts them
into the PostgreSQL database.

Usage:
    python scripts/populate_patient_data.py
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Add backend src to path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
SRC_DIR = BACKEND_DIR / "src"
DATA_DIR = BACKEND_DIR.parent / "data"

sys.path.insert(0, str(SRC_DIR))

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)


def get_database_url():
    """Get DATABASE_URL from environment"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    return db_url


def load_test_data():
    """Load test data from JSON file"""
    test_json_path = DATA_DIR / "tests" / "test_data.json"
    if not test_json_path.exists():
        print(f"❌ Test data file not found: {test_json_path}")
        sys.exit(1)

    with open(test_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"✅ Loaded {len(data)} test records from {test_json_path}")
    return data


def load_survey_data():
    """Load survey data from JSON file"""
    survey_json_path = DATA_DIR / "surveys" / "survey_data.json"
    if not survey_json_path.exists():
        print(f"⚠️  Survey data file not found: {survey_json_path}")
        return []

    with open(survey_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"✅ Loaded {len(data)} survey records from {survey_json_path}")
    return data


def insert_patients_and_exams(conn, test_data):
    """Insert patient and health exam data"""
    cursor = conn.cursor()

    print("\n📊 Inserting patient data...")

    for i, case in enumerate(test_data, 1):
        # Generate patient_id from index
        patient_id = f"P{i:04d}"

        # Normalize sex
        sex = case["sex"]

        # Parse dates
        registered_at = datetime.fromisoformat(case["reg"])
        exam_at = datetime.fromisoformat(case["exam_at"])
        doc_registered_on = date.fromisoformat(case["doc_reg"])

        # Calculate birth date from age (approximate)
        current_year = datetime.now().year
        birth_year = current_year - case["age"]
        birth_date = date(birth_year, 1, 1)  # Simplified

        # Calculate BMI
        height_m = case["height"] / 100
        bmi = round(case["weight"] / (height_m ** 2), 2)

        # Insert patient
        cursor.execute(
            """
            INSERT INTO patients (
                patient_id, name, sex, age, birth_date, rrn_masked, registered_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (patient_id) DO UPDATE SET
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                patient_id,
                case["name"],
                sex,
                case["age"],
                birth_date,
                case["rrn"],
                registered_at,
            ),
        )

        # Insert health exam
        cursor.execute(
            """
            INSERT INTO health_exams (
                patient_id, exam_at, facility_name, doc_registered_on,
                height_cm, weight_kg, bmi, waist_cm,
                systolic_mmHg, diastolic_mmHg,
                fbg_mg_dl, tg_mg_dl, hdl_mg_dl, tc_mg_dl, ldl_mg_dl
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s
            )
            """,
            (
                patient_id,
                exam_at,
                case["facility"],
                doc_registered_on,
                case["height"],
                case["weight"],
                bmi,
                case["waist"],
                case["sys"],
                case["dia"],
                case["fbg"],
                case["tg"],
                case["hdl"],
                case["tc"],
                case["ldl"],
            ),
        )

        if i % 5 == 0:
            print(f"  ✓ {i}/{len(test_data)} patients inserted")

    conn.commit()
    print(f"✅ Inserted {len(test_data)} patients and health exams")


def insert_surveys(conn, survey_data):
    """Insert survey data"""
    if not survey_data:
        print("\n⚠️  No survey data to insert")
        return

    cursor = conn.cursor()

    print("\n📊 Inserting survey data...")

    for i, record in enumerate(survey_data, 1):
        survey = record["survey"]

        # Parse dates
        birth_date = (
            date.fromisoformat(survey["birth_date"])
            if survey.get("birth_date")
            else None
        )
        survey_date = datetime.fromisoformat(survey["survey_date"])
        recent_checkup_date = (
            date.fromisoformat(survey["recent_checkup_date"])
            if survey.get("recent_checkup_date")
            else None
        )
        created_at = (
            datetime.fromisoformat(survey["created_at"])
            if survey.get("created_at")
            else datetime.now()
        )

        # Insert survey
        cursor.execute(
            """
            INSERT INTO surveys (
                survey_id, patient_id, patient_name, sex, birth_date,
                contact, address, visit_type, survey_date, facility,
                recent_checkup, recent_checkup_date, created_at, created_by
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (survey_id) DO NOTHING
            """,
            (
                survey["survey_id"],
                survey["patient_id"],
                survey.get("patient_name"),
                survey.get("sex"),
                birth_date,
                survey.get("contact"),
                survey.get("address"),
                survey["visit_type"],
                survey_date,
                survey.get("facility"),
                survey.get("recent_checkup"),
                recent_checkup_date,
                created_at,
                survey.get("created_by"),
            ),
        )

        # Insert disease history
        for disease in record.get("diseases", []):
            cursor.execute(
                """
                INSERT INTO disease_history (
                    survey_id, disease_code, disease_name,
                    diagnosed, prescribed, taking_medication,
                    regular_medication, duration_years
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    disease["survey_id"],
                    disease["disease_code"],
                    disease.get("disease_name"),
                    disease.get("diagnosed", False),
                    disease.get("prescribed", False),
                    disease.get("taking_medication", False),
                    disease.get("regular_medication"),
                    disease.get("duration_years"),
                ),
            )

        # Insert physical activity
        if "physical_activity" in record:
            pa = record["physical_activity"]
            cursor.execute(
                """
                INSERT INTO physical_activity (
                    survey_id, sedentary_hours, sedentary_minutes,
                    work_moderate_days, work_moderate_hours, work_moderate_minutes,
                    transport_days, transport_minutes,
                    leisure_moderate_days, leisure_moderate_hours, leisure_moderate_minutes,
                    exercise_plan, no_exercise_reason, no_exercise_reason_text
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (survey_id) DO NOTHING
                """,
                (
                    pa["survey_id"],
                    pa.get("sedentary_hours"),
                    pa.get("sedentary_minutes"),
                    pa.get("work_moderate_days"),
                    pa.get("work_moderate_hours"),
                    pa.get("work_moderate_minutes"),
                    pa.get("transport_days"),
                    pa.get("transport_minutes"),
                    pa.get("leisure_moderate_days"),
                    pa.get("leisure_moderate_hours"),
                    pa.get("leisure_moderate_minutes"),
                    pa.get("exercise_plan"),
                    pa.get("no_exercise_reason"),
                    pa.get("no_exercise_reason_text"),
                ),
            )

        # Insert diet habit
        if "diet" in record:
            diet = record["diet"]
            cursor.execute(
                """
                INSERT INTO diet_habit (
                    survey_id, breakfast_frequency,
                    diet_q1_whole_grains, diet_q2_vegetables, diet_q3_fruits,
                    diet_q4_dairy, diet_q5_regular_meals, diet_q6_balanced_diet,
                    diet_q7_low_salt, diet_q8_no_extra_salt, diet_q9_trim_fat,
                    diet_q10_avoid_fried, diet_total_score,
                    poor_diet_reason, poor_diet_reason_text
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (survey_id) DO NOTHING
                """,
                (
                    diet["survey_id"],
                    diet.get("breakfast_frequency"),
                    diet.get("diet_q1_whole_grains"),
                    diet.get("diet_q2_vegetables"),
                    diet.get("diet_q3_fruits"),
                    diet.get("diet_q4_dairy"),
                    diet.get("diet_q5_regular_meals"),
                    diet.get("diet_q6_balanced_diet"),
                    diet.get("diet_q7_low_salt"),
                    diet.get("diet_q8_no_extra_salt"),
                    diet.get("diet_q9_trim_fat"),
                    diet.get("diet_q10_avoid_fried"),
                    diet.get("diet_total_score"),
                    diet.get("poor_diet_reason"),
                    diet.get("poor_diet_reason_text"),
                ),
            )

        # Insert obesity management
        if "obesity" in record:
            obesity = record["obesity"]
            cursor.execute(
                """
                INSERT INTO obesity_management (
                    survey_id, weight_change, weight_change_kg,
                    body_shape_perception, weight_control_effort
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (survey_id) DO NOTHING
                """,
                (
                    obesity["survey_id"],
                    obesity.get("weight_change"),
                    obesity.get("weight_change_kg"),
                    obesity.get("body_shape_perception"),
                    obesity.get("weight_control_effort"),
                ),
            )

        # Insert mental health
        if "mental_health" in record:
            mh = record["mental_health"]
            cursor.execute(
                """
                INSERT INTO mental_health (
                    survey_id, sleep_hours_weekday, sleep_hours_weekend,
                    phq9_q1_depressed, phq9_q2_no_interest, phq9_q3_sleep_problem,
                    phq9_q4_appetite, phq9_q5_psychomotor, phq9_q6_fatigue,
                    phq9_q7_guilt, phq9_q8_concentration, phq9_q9_suicide,
                    phq9_total_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (survey_id) DO NOTHING
                """,
                (
                    mh["survey_id"],
                    mh.get("sleep_hours_weekday"),
                    mh.get("sleep_hours_weekend"),
                    mh.get("phq9_q1_depressed"),
                    mh.get("phq9_q2_no_interest"),
                    mh.get("phq9_q3_sleep_problem"),
                    mh.get("phq9_q4_appetite"),
                    mh.get("phq9_q5_psychomotor"),
                    mh.get("phq9_q6_fatigue"),
                    mh.get("phq9_q7_guilt"),
                    mh.get("phq9_q8_concentration"),
                    mh.get("phq9_q9_suicide"),
                    mh.get("phq9_total_score"),
                ),
            )

    conn.commit()
    print(f"✅ Inserted {len(survey_data)} survey records")


def print_statistics(conn):
    """Print database statistics"""
    cursor = conn.cursor()

    print("\n📈 Database Statistics:")

    # Patient count
    cursor.execute("SELECT COUNT(*) FROM patients")
    patient_count = cursor.fetchone()[0]
    print(f"  - Total patients: {patient_count}")

    # Exam count
    cursor.execute("SELECT COUNT(*) FROM health_exams")
    exam_count = cursor.fetchone()[0]
    print(f"  - Total health exams: {exam_count}")

    # Survey count
    cursor.execute("SELECT COUNT(*) FROM surveys")
    survey_count = cursor.fetchone()[0]
    print(f"  - Total surveys: {survey_count}")

    # Risk level distribution
    cursor.execute(
        """
        SELECT risk_level, COUNT(*)
        FROM health_exams
        WHERE risk_level IS NOT NULL
        GROUP BY risk_level
        ORDER BY risk_level
        """
    )
    print(f"\n  Risk Level Distribution:")
    for risk_level, count in cursor.fetchall():
        print(f"    - {risk_level}: {count}")

    # Sample patient summaries
    cursor.execute(
        """
        SELECT name, age, sex, risk_level, risk_factors, latest_exam_at
        FROM patient_summaries
        ORDER BY latest_exam_at DESC NULLS LAST
        LIMIT 5
        """
    )
    print(f"\n  Recent Patient Summaries:")
    for row in cursor.fetchall():
        name, age, sex, risk_level, risk_factors, exam_at = row
        exam_date = exam_at.strftime("%Y-%m-%d") if exam_at else "N/A"
        print(
            f"    - {name} ({age}세, {sex}): {risk_level or 'N/A'} "
            f"[{risk_factors or 0} factors] - Exam: {exam_date}"
        )


def main():
    """Main execution function"""
    print("=" * 60)
    print("Patient Data Population Script")
    print("=" * 60)

    # Get database connection
    db_url = get_database_url()
    print(f"\n🔌 Connecting to database...")

    try:
        conn = psycopg2.connect(db_url)
        print("✅ Connected to PostgreSQL database")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    try:
        # Load data
        test_data = load_test_data()
        survey_data = load_survey_data()

        # Insert data
        insert_patients_and_exams(conn, test_data)
        insert_surveys(conn, survey_data)

        # Print statistics
        print_statistics(conn)

        print("\n✅ Data population completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during data population: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
