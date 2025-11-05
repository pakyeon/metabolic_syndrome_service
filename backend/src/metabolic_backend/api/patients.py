"""Patient data API endpoints for metabolic syndrome counseling system."""

from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional, Dict, Any
import os
import logging

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None
    logging.warning("psycopg2 not installed - patient endpoints will not work")


# ============================================================================
# Pydantic Models
# ============================================================================

class PatientSummary(BaseModel):
    """Patient summary with latest exam information"""
    patient_id: str
    name: str
    sex: str
    age: Optional[int]
    birth_date: Optional[date]
    contact: Optional[str]
    registered_at: datetime
    latest_exam_at: Optional[datetime]
    latest_exam_id: Optional[str]
    risk_level: Optional[str]
    risk_factors: Optional[int]
    bmi: Optional[float]
    systolic_mmHg: Optional[int]
    diastolic_mmHg: Optional[int]
    fbg_mg_dl: Optional[float]


class PatientDetail(BaseModel):
    """Detailed patient information"""
    patient_id: str
    name: str
    sex: str
    age: Optional[int]
    birth_date: Optional[date]
    rrn_masked: Optional[str]
    contact: Optional[str]
    address: Optional[str]
    registered_at: datetime
    updated_at: datetime


class HealthExam(BaseModel):
    """Health examination results"""
    exam_id: str
    patient_id: str
    exam_at: datetime
    facility_name: Optional[str]
    doc_registered_on: Optional[date]

    # Body measurements
    height_cm: Optional[float]
    weight_kg: Optional[float]
    bmi: Optional[float]
    waist_cm: Optional[float]

    # Blood pressure
    systolic_mmHg: Optional[int]
    diastolic_mmHg: Optional[int]

    # Metabolic markers
    fbg_mg_dl: Optional[float]
    tg_mg_dl: Optional[float]
    hdl_mg_dl: Optional[float]
    tc_mg_dl: Optional[float]
    ldl_mg_dl: Optional[float]

    # Risk assessment
    risk_level: Optional[str]
    risk_factors: Optional[int]

    created_at: datetime


class Survey(BaseModel):
    """Patient survey response"""
    survey_id: str
    patient_id: str
    patient_name: Optional[str]
    sex: Optional[str]
    visit_type: str
    survey_date: datetime
    facility: Optional[str]


class PhysicalActivity(BaseModel):
    """Physical activity data from survey"""
    survey_id: str
    sedentary_hours: Optional[int]
    sedentary_minutes: Optional[int]
    work_moderate_days: Optional[int]
    transport_days: Optional[int]
    leisure_moderate_days: Optional[int]
    exercise_plan: Optional[str]
    no_exercise_reason: Optional[str]


class DietHabit(BaseModel):
    """Diet habit data from survey"""
    survey_id: str
    breakfast_frequency: Optional[str]
    diet_total_score: Optional[int]
    poor_diet_reason: Optional[str]


class MentalHealth(BaseModel):
    """Mental health data from survey"""
    survey_id: str
    sleep_hours_weekday: Optional[int]
    sleep_hours_weekend: Optional[int]
    phq9_total_score: Optional[int]


class SurveyDetail(BaseModel):
    """Complete survey with related data"""
    survey: Survey
    diseases: List[Dict[str, Any]]
    physical_activity: Optional[PhysicalActivity]
    diet_habit: Optional[DietHabit]
    mental_health: Optional[MentalHealth]
    obesity_management: Optional[Dict[str, Any]]


# ============================================================================
# Database Connection
# ============================================================================

def get_db_connection():
    """Get PostgreSQL database connection"""
    if psycopg2 is None:
        raise HTTPException(status_code=500, detail="Database driver not available")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")

    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


# ============================================================================
# Router
# ============================================================================

router = APIRouter(prefix="/v1/patients", tags=["patients"])


@router.get("", response_model=List[PatientSummary])
def list_patients(
    sort_by: str = Query("latest_exam_at", description="Sort field (latest_exam_at, name, risk_level)"),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of patients to return"),
):
    """
    List all patients with their latest exam information.

    Sorted by most recent exam date by default (for counselor preparation workflow).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Validate sort parameters
        valid_sort_fields = ["latest_exam_at", "name", "risk_level", "registered_at"]
        if sort_by not in valid_sort_fields:
            sort_by = "latest_exam_at"

        sort_order = "DESC" if order.lower() == "desc" else "ASC"

        # Handle NULL values in sorting (put nulls last)
        nulls_position = "NULLS LAST" if order.lower() == "desc" else "NULLS FIRST"

        query = f"""
            SELECT
                patient_id,
                name,
                sex,
                age,
                birth_date,
                contact,
                registered_at,
                latest_exam_at,
                latest_exam_id::TEXT as latest_exam_id,
                risk_level,
                risk_factors,
                bmi,
                systolic_mmHg,
                diastolic_mmHg,
                fbg_mg_dl
            FROM patient_summaries
            ORDER BY {sort_by} {sort_order} {nulls_position}
            LIMIT %s
        """

        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        return [PatientSummary(**dict(row)) for row in rows]

    finally:
        conn.close()


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: str):
    """Get detailed patient information"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                patient_id,
                name,
                sex,
                age,
                birth_date,
                rrn_masked,
                contact,
                address,
                registered_at,
                updated_at
            FROM patients
            WHERE patient_id = %s
            """,
            (patient_id,),
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        return PatientDetail(**dict(row))

    finally:
        conn.close()


@router.get("/{patient_id}/tests", response_model=List[HealthExam])
def get_patient_tests(patient_id: str, limit: int = Query(10, ge=1, le=100)):
    """Get health examination results for a patient, sorted by date descending"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                exam_id::TEXT as exam_id,
                patient_id,
                exam_at,
                facility_name,
                doc_registered_on,
                height_cm,
                weight_kg,
                bmi,
                waist_cm,
                systolic_mmHg,
                diastolic_mmHg,
                fbg_mg_dl,
                tg_mg_dl,
                hdl_mg_dl,
                tc_mg_dl,
                ldl_mg_dl,
                risk_level,
                risk_factors,
                created_at
            FROM health_exams
            WHERE patient_id = %s
            ORDER BY exam_at DESC
            LIMIT %s
            """,
            (patient_id, limit),
        )

        rows = cursor.fetchall()
        return [HealthExam(**dict(row)) for row in rows]

    finally:
        conn.close()


@router.get("/{patient_id}/survey", response_model=Optional[SurveyDetail])
def get_patient_survey(patient_id: str):
    """
    Get most recent survey response for a patient with all related data.

    Returns survey, diseases, physical activity, diet habits, mental health, and obesity management.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get most recent survey
        cursor.execute(
            """
            SELECT
                survey_id,
                patient_id,
                patient_name,
                sex,
                visit_type,
                survey_date,
                facility
            FROM surveys
            WHERE patient_id = %s
            ORDER BY survey_date DESC
            LIMIT 1
            """,
            (patient_id,),
        )

        survey_row = cursor.fetchone()
        if not survey_row:
            return None

        survey_id = survey_row["survey_id"]
        survey = Survey(**dict(survey_row))

        # Get disease history
        cursor.execute(
            """
            SELECT
                disease_code,
                disease_name,
                diagnosed,
                prescribed,
                taking_medication,
                regular_medication,
                duration_years
            FROM disease_history
            WHERE survey_id = %s
            """,
            (survey_id,),
        )
        diseases = [dict(row) for row in cursor.fetchall()]

        # Get physical activity
        cursor.execute(
            """
            SELECT
                survey_id,
                sedentary_hours,
                sedentary_minutes,
                work_moderate_days,
                transport_days,
                leisure_moderate_days,
                exercise_plan,
                no_exercise_reason
            FROM physical_activity
            WHERE survey_id = %s
            """,
            (survey_id,),
        )
        pa_row = cursor.fetchone()
        physical_activity = PhysicalActivity(**dict(pa_row)) if pa_row else None

        # Get diet habit
        cursor.execute(
            """
            SELECT
                survey_id,
                breakfast_frequency,
                diet_total_score,
                poor_diet_reason
            FROM diet_habit
            WHERE survey_id = %s
            """,
            (survey_id,),
        )
        diet_row = cursor.fetchone()
        diet_habit = DietHabit(**dict(diet_row)) if diet_row else None

        # Get mental health
        cursor.execute(
            """
            SELECT
                survey_id,
                sleep_hours_weekday,
                sleep_hours_weekend,
                phq9_total_score
            FROM mental_health
            WHERE survey_id = %s
            """,
            (survey_id,),
        )
        mh_row = cursor.fetchone()
        mental_health = MentalHealth(**dict(mh_row)) if mh_row else None

        # Get obesity management
        cursor.execute(
            """
            SELECT
                weight_change,
                weight_change_kg,
                body_shape_perception,
                weight_control_effort
            FROM obesity_management
            WHERE survey_id = %s
            """,
            (survey_id,),
        )
        obesity_row = cursor.fetchone()
        obesity_management = dict(obesity_row) if obesity_row else None

        return SurveyDetail(
            survey=survey,
            diseases=diseases,
            physical_activity=physical_activity,
            diet_habit=diet_habit,
            mental_health=mental_health,
            obesity_management=obesity_management,
        )

    finally:
        conn.close()


@router.get("/{patient_id}/latest-exam", response_model=Optional[HealthExam])
def get_patient_latest_exam(patient_id: str):
    """Get the most recent health examination for a patient"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                exam_id::TEXT as exam_id,
                patient_id,
                exam_at,
                facility_name,
                doc_registered_on,
                height_cm,
                weight_kg,
                bmi,
                waist_cm,
                systolic_mmHg,
                diastolic_mmHg,
                fbg_mg_dl,
                tg_mg_dl,
                hdl_mg_dl,
                tc_mg_dl,
                ldl_mg_dl,
                risk_level,
                risk_factors,
                created_at
            FROM health_exams
            WHERE patient_id = %s
            ORDER BY exam_at DESC
            LIMIT 1
            """,
            (patient_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return HealthExam(**dict(row))

    finally:
        conn.close()
