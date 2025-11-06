"""Patient data API endpoints using SQLite databases (survey.sqlite + test.sqlite)."""

from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pathlib import Path
import sqlite3
import logging

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query


# ============================================================================
# Database Paths
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SURVEY_DB = PROJECT_ROOT / "data" / "surveys" / "survey.sqlite"
TEST_DB = PROJECT_ROOT / "data" / "tests" / "test.sqlite"


# ============================================================================
# Pydantic Models (simplified for SQLite schema)
# ============================================================================

class PatientSummary(BaseModel):
    """Patient summary with latest exam information"""
    patient_id: int
    name: str
    sex: str
    age: Optional[int]
    latest_exam_at: Optional[datetime]
    bmi: Optional[float]
    systolic_mmHg: Optional[int]
    fbg_mg_dl: Optional[float]


class PatientDetail(BaseModel):
    """Detailed patient information"""
    patient_id: int
    name: str
    sex: str
    age: Optional[int]
    rrn_masked: Optional[str]
    registered_at: datetime


class HealthExam(BaseModel):
    """Health examination results"""
    exam_id: int
    patient_id: int
    exam_at: datetime
    facility_name: Optional[str]

    height_cm: Optional[float]
    weight_kg: Optional[float]
    bmi: Optional[float]
    waist_cm: Optional[float]

    systolic_mmHg: Optional[int]
    diastolic_mmHg: Optional[int]

    fbg_mg_dl: Optional[float]
    tg_mg_dl: Optional[float]
    hdl_mg_dl: Optional[float]
    tc_mg_dl: Optional[float]
    ldl_mg_dl: Optional[float]


class SurveyBasic(BaseModel):
    """Basic survey information"""
    survey_id: str
    patient_id: int
    patient_name: Optional[str]
    visit_type: str
    survey_date: datetime


# ============================================================================
# Database Connections
# ============================================================================

def get_test_db():
    """Get connection to test.sqlite"""
    if not TEST_DB.exists():
        raise HTTPException(status_code=500, detail=f"Test database not found: {TEST_DB}")

    conn = sqlite3.connect(str(TEST_DB))
    conn.row_factory = sqlite3.Row
    return conn


def get_survey_db():
    """Get connection to survey.sqlite"""
    if not SURVEY_DB.exists():
        raise HTTPException(status_code=500, detail=f"Survey database not found: {SURVEY_DB}")

    conn = sqlite3.connect(str(SURVEY_DB))
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# Router
# ============================================================================

router = APIRouter(prefix="/v1/patients", tags=["patients"])


@router.get("", response_model=List[PatientSummary])
def list_patients(
    sort_by: str = Query("latest_exam_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all patients with their latest exam information"""
    test_conn = get_test_db()

    try:
        cursor = test_conn.cursor()

        # Join patients with their latest exam
        query = """
            SELECT
                p.patient_id,
                p.name,
                p.sex,
                p.age,
                e.exam_at as latest_exam_at,
                e.bmi,
                e.systolic_mmHg,
                e.fbg_mg_dl
            FROM patients p
            LEFT JOIN health_exams e ON p.patient_id = e.patient_id
            ORDER BY e.exam_at DESC
            LIMIT ?
        """

        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        return [PatientSummary(**dict(row)) for row in rows]

    finally:
        test_conn.close()


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: int):
    """Get detailed patient information"""
    test_conn = get_test_db()

    try:
        cursor = test_conn.cursor()

        cursor.execute(
            """
            SELECT
                patient_id,
                name,
                sex,
                age,
                rrn_masked,
                registered_at
            FROM patients
            WHERE patient_id = ?
            """,
            (patient_id,),
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

        return PatientDetail(**dict(row))

    finally:
        test_conn.close()


@router.get("/{patient_id}/tests", response_model=List[HealthExam])
def get_patient_tests(patient_id: int, limit: int = Query(10, ge=1, le=100)):
    """Get health examination results for a patient"""
    test_conn = get_test_db()

    try:
        cursor = test_conn.cursor()

        cursor.execute(
            """
            SELECT
                exam_id,
                patient_id,
                exam_at,
                facility_name,
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
                ldl_mg_dl
            FROM health_exams
            WHERE patient_id = ?
            ORDER BY exam_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        )

        rows = cursor.fetchall()
        return [HealthExam(**dict(row)) for row in rows]

    finally:
        test_conn.close()


@router.get("/{patient_id}/latest-exam", response_model=Optional[HealthExam])
def get_patient_latest_exam(patient_id: int):
    """Get the most recent health examination for a patient"""
    test_conn = get_test_db()

    try:
        cursor = test_conn.cursor()

        cursor.execute(
            """
            SELECT
                exam_id,
                patient_id,
                exam_at,
                facility_name,
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
                ldl_mg_dl
            FROM health_exams
            WHERE patient_id = ?
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
        test_conn.close()


@router.get("/{patient_id}/survey", response_model=Optional[SurveyBasic])
def get_patient_survey(patient_id: int):
    """Get most recent survey response for a patient"""
    survey_conn = get_survey_db()

    try:
        cursor = survey_conn.cursor()

        cursor.execute(
            """
            SELECT
                survey_id,
                patient_id,
                patient_name,
                visit_type,
                survey_date
            FROM surveys
            WHERE patient_id = ?
            ORDER BY survey_date DESC
            LIMIT 1
            """,
            (str(patient_id),),  # patient_id is TEXT in survey.sqlite
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Convert patient_id to int for response model
        data = dict(row)
        data['patient_id'] = int(data['patient_id'])

        return SurveyBasic(**data)

    finally:
        survey_conn.close()
