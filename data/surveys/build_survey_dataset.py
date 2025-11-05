# -*- coding: utf-8 -*-
"""
대사증후군 기초설문지 스키마 (Metabolic Syndrome Survey Schema)

설문지 구조:
- 첫 방문/12개월: 전체 문항 (1-22)
- 3/6/9개월: 축약 문항 (1-14)

주요 섹션:
- DX: 질병 이력 및 관리
- BP_BG: 혈압 및 혈당 관리
- EDU: 교육 경험
- SMK: 흡연
- ALC: 음주
- PA: 신체활동
- OBES: 비만 및 체중조절
- DIET: 식습관
- MH: 정신건강
- DEMO: 일반정보
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Text,
    Boolean,
    Date,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, Session, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import json
from pathlib import Path

Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "survey.sqlite"
DEFAULT_JSON_PATH = BASE_DIR / "survey_data.json"


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 연결 시 외래키 제약을 활성화"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# ============================================================
# 1. 기본 설문 정보
# ============================================================


class Survey(Base):
    """설문 기본 정보"""

    __tablename__ = "surveys"

    survey_id = Column(String(32), primary_key=True)
    patient_id = Column(String(32), index=True, nullable=False)
    patient_name = Column(String(64), nullable=True)
    sex = Column(String(1), nullable=True)  # M/F
    birth_date = Column(Date, nullable=True)
    contact = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)

    visit_type = Column(String(16), nullable=False)  # first, m3, m6, m9, m12
    survey_date = Column(DateTime, nullable=False)
    facility = Column(String(100), nullable=True)

    # 최근 건강검진 이력
    recent_checkup = Column(Boolean, nullable=True)
    recent_checkup_date = Column(Date, nullable=True)

    created_at = Column(DateTime, nullable=False, default=func.now())
    created_by = Column(String(64), nullable=True)

    # Relationships
    diseases = relationship(
        "DiseaseHistory", back_populates="survey", cascade="all, delete-orphan"
    )
    medication = relationship(
        "MedicationCompliance",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    bp_bg_monitoring = relationship(
        "BPBGMonitoring",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    education = relationship(
        "EducationHistory",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    smoking = relationship(
        "SmokingHistory",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    alcohol = relationship(
        "AlcoholConsumption",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    physical_activity = relationship(
        "PhysicalActivity",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    obesity = relationship(
        "ObesityManagement",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    diet = relationship(
        "DietHabit",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mental_health = relationship(
        "MentalHealth",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )
    demographics = relationship(
        "Demographics",
        back_populates="survey",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ============================================================
# 2. 질병 이력 및 관리 (DX)
# ============================================================


class DiseaseHistory(Base):
    """질환별 진단 및 치료 현황 (문항 1)"""

    __tablename__ = "disease_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), index=True)

    disease_code = Column(
        String(16), nullable=False
    )  # HTN, DM, DYSLIP, STROKE, CAD, CKD, OTHER
    disease_name = Column(String(100), nullable=True)  # OTHER인 경우 질환명

    diagnosed = Column(Boolean, default=False)
    prescribed = Column(Boolean, default=False)
    taking_medication = Column(Boolean, default=False)
    regular_medication = Column(Boolean, nullable=True)  # 월 20일 이상
    duration_years = Column(Integer, nullable=True)

    survey = relationship("Survey", back_populates="diseases")


class MedicationCompliance(Base):
    """약물 복용 순응도 (문항 1-1, 1-2)"""

    __tablename__ = "medication_compliance"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 1-1. 정기 진료 여부
    regular_visit = Column(Boolean, nullable=True)
    visit_facility_health_center = Column(Boolean, default=False)
    visit_facility_clinic = Column(Boolean, default=False)
    visit_facility_hospital = Column(Boolean, default=False)
    visit_facility_other = Column(String(100), nullable=True)

    # 1-2. 복약 순응도
    compliant = Column(Boolean, nullable=True)
    non_compliance_reason = Column(
        String(16), nullable=True
    )  # NO_SYMPTOM, NO_EFFECT, SIDE_EFFECT, etc.
    non_compliance_reason_text = Column(String(200), nullable=True)

    survey = relationship("Survey", back_populates="medication")


# ============================================================
# 3. 혈압 및 혈당 관리 (BP_BG)
# ============================================================


class BPBGMonitoring(Base):
    """혈압/혈당 모니터링 (문항 2, 3)"""

    __tablename__ = "bp_bg_monitoring"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 2: 혈압
    bp_awareness = Column(String(16), nullable=True)  # KNOW, UNKNOWN, NOT_MEASURED
    bp_frequency = Column(
        String(16), nullable=True
    )  # DAILY_WEEKLY, MONTHLY, OCCASIONALLY
    bp_times_per_week = Column(Integer, nullable=True)
    bp_times_per_month = Column(Integer, nullable=True)
    bp_times_per_6months = Column(Integer, nullable=True)

    # 문항 3: 혈당
    bg_awareness = Column(String(16), nullable=True)  # KNOW, UNKNOWN, NOT_MEASURED
    bg_frequency = Column(
        String(16), nullable=True
    )  # DAILY_WEEKLY, MONTHLY, OCCASIONALLY
    bg_times_per_week = Column(Integer, nullable=True)
    bg_times_per_month = Column(Integer, nullable=True)
    bg_times_per_6months = Column(Integer, nullable=True)

    survey = relationship("Survey", back_populates="bp_bg_monitoring")


# ============================================================
# 4. 교육 경험 (EDU)
# ============================================================


class EducationHistory(Base):
    """만성질환 교육 경험 (문항 4)"""

    __tablename__ = "education_history"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    received_education = Column(Boolean, nullable=True)

    survey = relationship("Survey", back_populates="education")


# ============================================================
# 5. 흡연 (SMK)
# ============================================================


class SmokingHistory(Base):
    """흡연 이력 및 현황 (문항 5, 6)"""

    __tablename__ = "smoking_history"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 5: 흡연 경험
    lifetime_smoking = Column(
        String(16), nullable=True
    )  # LESS_5PACKS, MORE_5PACKS, NEVER

    # 문항 5-1: 현재 흡연 상태
    current_status = Column(
        String(16), nullable=True
    )  # DAILY, OCCASIONAL, FORMER, NEVER

    # 문항 5-2: 담배 종류
    cigarette_type = Column(String(16), nullable=True)  # REGULAR, HEATED, LIQUID, OTHER
    cigarette_type_other = Column(String(50), nullable=True)

    # 문항 5-3: 흡연량 및 기간
    frequency_type = Column(String(16), nullable=True)  # DAILY, OCCASIONAL
    daily_amount = Column(Integer, nullable=True)  # 개비/일
    occasional_amount = Column(Integer, nullable=True)  # 개비/회
    occasional_days_per_month = Column(Integer, nullable=True)  # 일/월
    smoking_duration_years = Column(Integer, nullable=True)

    # 문항 6: 금연 계획
    quit_plan = Column(
        String(16), nullable=True
    )  # NO_PLAN, WITHIN_1M, WITHIN_6M, SOMEDAY

    survey = relationship("Survey", back_populates="smoking")


# ============================================================
# 6. 음주 (ALC)
# ============================================================


class AlcoholConsumption(Base):
    """음주 습관 (문항 7)"""

    __tablename__ = "alcohol_consumption"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 7: 최근 6개월 음주
    current_drinker = Column(Boolean, nullable=True)

    # 음주 빈도
    frequency = Column(
        String(16), nullable=True
    )  # LESS_1PM, ONCE_PM, 2_4PM, 2_3PW, 4PLUS_PW

    # 1회 음주량 (잔)
    amount_per_occasion = Column(
        String(16), nullable=True
    )  # 1_2, 3_4, 5_6, 7_9, 10PLUS
    amount_per_occasion_num = Column(
        Integer, nullable=True
    )  # 10잔 이상인 경우 구체적 수치

    survey = relationship("Survey", back_populates="alcohol")


# ============================================================
# 7. 신체활동 (PA)
# ============================================================


class PhysicalActivity(Base):
    """신체활동 (문항 8, 9)"""

    __tablename__ = "physical_activity"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 8: 좌식 시간
    sedentary_hours = Column(Integer, nullable=True)
    sedentary_minutes = Column(Integer, nullable=True)

    # 문항 9: 신체활동 (직업형)
    work_vigorous_days = Column(Integer, nullable=True)
    work_vigorous_hours = Column(Integer, nullable=True)
    work_vigorous_minutes = Column(Integer, nullable=True)

    work_moderate_days = Column(Integer, nullable=True)
    work_moderate_hours = Column(Integer, nullable=True)
    work_moderate_minutes = Column(Integer, nullable=True)

    # 이동형
    transport_days = Column(Integer, nullable=True)
    transport_hours = Column(Integer, nullable=True)
    transport_minutes = Column(Integer, nullable=True)

    # 여가형
    leisure_vigorous_days = Column(Integer, nullable=True)
    leisure_vigorous_hours = Column(Integer, nullable=True)
    leisure_vigorous_minutes = Column(Integer, nullable=True)

    leisure_moderate_days = Column(Integer, nullable=True)
    leisure_moderate_hours = Column(Integer, nullable=True)
    leisure_moderate_minutes = Column(Integer, nullable=True)

    # 문항 9-1: 실천 계획
    exercise_plan = Column(
        String(16), nullable=True
    )  # NO_PLAN, FUTURE, OCCASIONAL, LESS_6M, MORE_6M

    # 문항 9-2: 미실천 이유
    no_exercise_reason = Column(
        String(16), nullable=True
    )  # DISEASE, LAZY, NO_MONEY, NO_TIME, NO_FACILITY, OTHER
    no_exercise_reason_text = Column(String(100), nullable=True)

    survey = relationship("Survey", back_populates="physical_activity")


# ============================================================
# 8. 비만 및 체중조절 (OBES)
# ============================================================


class ObesityManagement(Base):
    """비만 및 체중관리 (문항 10, 11, 12)"""

    __tablename__ = "obesity_management"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 10: 6개월간 체중 변화
    weight_change = Column(String(16), nullable=True)  # NO_CHANGE, DECREASED, INCREASED
    weight_change_kg = Column(Float, nullable=True)

    # 문항 11: 체형 인식
    body_shape_perception = Column(
        String(16), nullable=True
    )  # VERY_THIN, THIN, NORMAL, OVERWEIGHT, OBESE

    # 문항 12: 체중조절 노력
    weight_control_effort = Column(
        String(16), nullable=True
    )  # LOSE, MAINTAIN, GAIN, NONE

    survey = relationship("Survey", back_populates="obesity")


# ============================================================
# 9. 식습관 (DIET)
# ============================================================


class DietHabit(Base):
    """식습관 (문항 13, 14, 15)"""

    __tablename__ = "diet_habit"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 13: 아침식사 빈도
    breakfast_frequency = Column(
        String(16), nullable=True
    )  # 5_7PW, 3_4PW, 1_2PW, RARELY

    # 문항 14: 식생활 실천 (각 항목 0 또는 1점)
    diet_q1_whole_grains = Column(Integer, nullable=True)
    diet_q2_vegetables = Column(Integer, nullable=True)
    diet_q3_fruits = Column(Integer, nullable=True)
    diet_q4_dairy = Column(Integer, nullable=True)
    diet_q5_regular_meals = Column(Integer, nullable=True)
    diet_q6_balanced_diet = Column(Integer, nullable=True)
    diet_q7_low_salt = Column(Integer, nullable=True)
    diet_q8_no_extra_salt = Column(Integer, nullable=True)
    diet_q9_trim_fat = Column(Integer, nullable=True)
    diet_q10_avoid_fried = Column(Integer, nullable=True)

    diet_total_score = Column(Integer, nullable=True)  # 0-10점

    # 문항 15: 불량 식습관 이유
    poor_diet_reason = Column(
        String(16), nullable=True
    )  # ECONOMIC, NO_HELP, WEAK_WILL, DENTAL, NO_INFO, NO_APPETITE, OTHER
    poor_diet_reason_text = Column(String(100), nullable=True)

    survey = relationship("Survey", back_populates="diet")


# ============================================================
# 10. 정신건강 (MH)
# ============================================================


class MentalHealth(Base):
    """정신건강 (문항 16, 17)"""

    __tablename__ = "mental_health"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 16: 수면 시간
    sleep_hours_weekday = Column(Integer, nullable=True)
    sleep_hours_weekend = Column(Integer, nullable=True)

    # 문항 17: PHQ-9 (각 항목 0-3점)
    phq9_q1_depressed = Column(Integer, nullable=True)
    phq9_q2_no_interest = Column(Integer, nullable=True)
    phq9_q3_sleep_problem = Column(Integer, nullable=True)
    phq9_q4_appetite = Column(Integer, nullable=True)
    phq9_q5_psychomotor = Column(Integer, nullable=True)
    phq9_q6_fatigue = Column(Integer, nullable=True)
    phq9_q7_guilt = Column(Integer, nullable=True)
    phq9_q8_concentration = Column(Integer, nullable=True)
    phq9_q9_suicide = Column(Integer, nullable=True)

    phq9_total_score = Column(Integer, nullable=True)  # 0-27점

    survey = relationship("Survey", back_populates="mental_health")


# ============================================================
# 11. 일반정보 (DEMO) - 선택사항
# ============================================================


class Demographics(Base):
    """일반정보 (문항 18-22)"""

    __tablename__ = "demographics"

    survey_id = Column(String(32), ForeignKey("surveys.survey_id"), primary_key=True)

    # 문항 18: 혼인상태
    marital_status = Column(
        String(16), nullable=True
    )  # MARRIED_WITH, MARRIED_WITHOUT, SINGLE, NO_ANSWER

    # 문항 19: 가구원 수
    household_size = Column(Integer, nullable=True)  # 1, 2, 3, 4+, NO_ANSWER

    # 문항 20: 건강보험
    insurance_type = Column(String(16), nullable=True)  # NHI, MEDICAID, NONE, NO_ANSWER

    # 문항 21: 최종학력
    education_level = Column(
        String(16), nullable=True
    )  # ELEMENTARY, MIDDLE, HIGH, COLLEGE, NO_ANSWER

    # 문항 22: 월 가구소득
    monthly_income = Column(
        String(16), nullable=True
    )  # LESS_2M, 2_4M, 4_6M, MORE_6M, NO_ANSWER

    survey = relationship("Survey", back_populates="demographics")


# ============================================================
# 데이터베이스 초기화 및 유틸리티
# ============================================================


def init_db(db_path: Path | str = DEFAULT_DB_PATH):
    """데이터베이스 초기화"""
    db_path = Path(db_path)
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def load_survey_data(session: Session, json_path: Path | str):
    """JSON 파일에서 설문 데이터 로드"""
    from datetime import date

    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for survey_data in data:
        # Survey 객체 생성
        s = survey_data["survey"]

        # Date 필드 변환
        birth_date = None
        if s.get("birth_date"):
            birth_date_str = s["birth_date"]
            birth_date = date.fromisoformat(birth_date_str)

        recent_checkup_date = None
        if s.get("recent_checkup_date"):
            recent_checkup_date = date.fromisoformat(s["recent_checkup_date"])

        survey = Survey(
            survey_id=s["survey_id"],
            patient_id=s["patient_id"],
            patient_name=s.get("patient_name"),
            sex=s.get("sex"),
            birth_date=birth_date,
            contact=s.get("contact"),
            address=s.get("address"),
            visit_type=s["visit_type"],
            survey_date=datetime.fromisoformat(s["survey_date"]),
            facility=s.get("facility"),
            recent_checkup=s.get("recent_checkup"),
            recent_checkup_date=recent_checkup_date,
            created_at=(
                datetime.fromisoformat(s["created_at"])
                if s.get("created_at")
                else datetime.now()
            ),
            created_by=s.get("created_by"),
        )
        session.add(survey)

        # 질병 이력
        for disease in survey_data.get("diseases", []):
            session.add(DiseaseHistory(**disease))

        # 복약 순응도
        if "medication" in survey_data and survey_data["medication"] is not None:
            session.add(MedicationCompliance(**survey_data["medication"]))

        # 혈압/혈당 모니터링
        if "bp_bg_monitoring" in survey_data:
            session.add(BPBGMonitoring(**survey_data["bp_bg_monitoring"]))

        # 교육 이력
        if "education" in survey_data:
            session.add(EducationHistory(**survey_data["education"]))

        # 흡연
        if "smoking" in survey_data:
            session.add(SmokingHistory(**survey_data["smoking"]))

        # 음주
        if "alcohol" in survey_data:
            session.add(AlcoholConsumption(**survey_data["alcohol"]))

        # 신체활동
        if "physical_activity" in survey_data:
            session.add(PhysicalActivity(**survey_data["physical_activity"]))

        # 비만관리
        if "obesity" in survey_data:
            session.add(ObesityManagement(**survey_data["obesity"]))

        # 식습관
        if "diet" in survey_data:
            session.add(DietHabit(**survey_data["diet"]))

        # 정신건강
        if "mental_health" in survey_data:
            session.add(MentalHealth(**survey_data["mental_health"]))

        # 인구통계
        if "demographics" in survey_data:
            session.add(Demographics(**survey_data["demographics"]))

    session.commit()
    return len(data)


if __name__ == "__main__":
    # 데이터베이스 초기화
    SessionFactory = init_db(DEFAULT_DB_PATH)
    print("✓ 데이터베이스 스키마 생성 완료")

    # 샘플 데이터 로드
    if DEFAULT_JSON_PATH.exists():
        session = SessionFactory()
        try:
            count = load_survey_data(session, DEFAULT_JSON_PATH)
            print(f"✓ {count}건의 설문 데이터 로드 완료")
        finally:
            session.close()
    else:
        print(f"⚠ {DEFAULT_JSON_PATH.name} 파일을 찾을 수 없습니다.")
