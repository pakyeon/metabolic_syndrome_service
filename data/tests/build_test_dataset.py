# -*- coding: utf-8 -*-
"""
개선된 스키마 기반 건강 검진 데이터베이스 생성 스크립트

=== 데이터베이스 스키마 ===

1. patients (환자 기본정보)
   - patient_id: 환자 고유 번호 (자동증가, 기본키)
   - name: 환자 성명
   - sex: 성별 ('남', '여')
   - age: 나이
   - rrn_masked: 주민등록번호 마스킹 (예: 990101-3******)
   - registered_at: 환자 등록 일시

2. health_exams (검진 정보 + 측정 데이터 통합)
   - exam_id: 검진 고유 번호 (자동증가, 기본키)
   - patient_id: 환자 고유 번호 (외래키)
   - exam_at: 검진 일시
   - facility_name: 검진 기관명
   - doc_registered_on: 검진 결과 등록 날짜
   - height_cm, weight_kg, bmi: 신체 측정
   - waist_cm: 허리둘레
   - systolic_mmHg, diastolic_mmHg: 혈압
   - fbg_mg_dl: 공복혈당
   - tg_mg_dl: 중성지방
   - hdl_mg_dl: HDL 콜레스테롤
   - tc_mg_dl: 총콜레스테롤
   - ldl_mg_dl: LDL 콜레스테롤

※ 대사증후군 진단기준 (한국인 기준):
  - 복부비만: 허리둘레 남성 ≥90cm, 여성 ≥85cm
  - 고혈압: 수축기 ≥130mmHg 또는 이완기 ≥85mmHg
  - 공복혈당장애: 공복혈당 ≥100mg/dL
  - 고중성지방: 중성지방 ≥150mg/dL
  - 저HDL콜레스테롤: HDL 남성 <40mg/dL, 여성 <50mg/dL
  (5개 항목 중 3개 이상 해당 시 대사증후군 진단)
"""

import json
from datetime import datetime, date
from pathlib import Path

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "test.sqlite"
CASES_JSON = BASE_DIR / "test_data.json"

Base = declarative_base()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 연결 시 외래키 제약을 활성화"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


class Patient(Base):
    """환자 기본 정보 테이블"""

    __tablename__ = "patients"
    __table_args__ = (CheckConstraint("sex IN ('남','여')", name="ck_patients_sex"),)

    patient_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    sex = Column(String, nullable=False)  # '남' 또는 '여'
    age = Column(Integer, nullable=True)
    rrn_masked = Column(String, nullable=True)
    registered_at = Column(DateTime, nullable=False, server_default=func.now())

    exams = relationship(
        "HealthExam", back_populates="patient", cascade="all, delete-orphan"
    )


class HealthExam(Base):
    """검진 측정 데이터 및 메타 정보"""

    __tablename__ = "health_exams"
    __table_args__ = (Index("idx_health_exams_patient", "patient_id", "exam_at"),)

    exam_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id", ondelete="CASCADE"))
    exam_at = Column(DateTime, nullable=False)

    facility_name = Column(String, nullable=True)
    doc_registered_on = Column(Date, nullable=True)

    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)

    waist_cm = Column(Float, nullable=True)
    systolic_mmHg = Column(Integer, nullable=True)
    diastolic_mmHg = Column(Integer, nullable=True)
    fbg_mg_dl = Column(Float, nullable=True)
    tg_mg_dl = Column(Float, nullable=True)
    hdl_mg_dl = Column(Float, nullable=True)

    tc_mg_dl = Column(Float, nullable=True)
    ldl_mg_dl = Column(Float, nullable=True)

    patient = relationship("Patient", back_populates="exams")


def calculate_bmi(height_cm, weight_kg):
    """BMI 계산 (키는 cm, 몸무게는 kg)"""
    height_m = height_cm / 100
    return round(weight_kg / (height_m**2), 2)


def load_cases():
    """JSON 파일에서 케이스 로드"""
    if not CASES_JSON.exists():
        raise FileNotFoundError(
            f"{CASES_JSON} 파일을 찾을 수 없습니다. test_data.json 파일이 필요합니다."
        )

    try:
        with open(CASES_JSON, "r", encoding="utf-8") as f:
            cases = json.load(f)
        print(f"✅ {CASES_JSON}에서 {len(cases)}개의 케이스를 로드했습니다.")
        return cases
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파일 파싱 오류: {e}")
        raise
    except Exception as e:
        print(f"❌ 파일 로드 오류: {e}")
        raise


def main():
    """메인 실행 함수"""
    # 기존 DB 삭제
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"🗑️  기존 데이터베이스 삭제: {DB_PATH}")

    # SQLAlchemy 엔진 및 세션 초기화
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    print(f"✅ 데이터베이스 생성: {DB_PATH}")

    # JSON 케이스 로드
    cases = load_cases()

    print(f"\n📊 데이터 삽입 중...")

    session = SessionLocal()

    try:
        for i, case in enumerate(cases, 1):
            # BMI 자동 계산
            calculated_bmi = calculate_bmi(case["height"], case["weight"])

            # 문자열 기반 일시 정보를 datetime 객체로 변환
            registered_at = (
                datetime.fromisoformat(case["reg"])
                if case.get("reg")
                else datetime.now()
            )
            exam_at = (
                datetime.fromisoformat(case["exam_at"])
                if case.get("exam_at")
                else datetime.now()
            )
            doc_registered_on = (
                date.fromisoformat(case["doc_reg"]) if case.get("doc_reg") else None
            )

            patient = Patient(
                name=case["name"],
                sex=case["sex"],
                age=case["age"],
                rrn_masked=case["rrn"],
                registered_at=registered_at,
            )
            session.add(patient)

            exam = HealthExam(
                patient=patient,
                exam_at=exam_at,
                facility_name=case["facility"],
                doc_registered_on=doc_registered_on,
                height_cm=case["height"],
                weight_kg=case["weight"],
                bmi=calculated_bmi,
                waist_cm=case["waist"],
                systolic_mmHg=case["sys"],
                diastolic_mmHg=case["dia"],
                fbg_mg_dl=case["fbg"],
                tg_mg_dl=case["tg"],
                hdl_mg_dl=case["hdl"],
                tc_mg_dl=case["tc"],
                ldl_mg_dl=case["ldl"],
            )
            session.add(exam)

            if i % 5 == 0:
                print(f"  ✓ {i}/{len(cases)} 환자 데이터 삽입 완료")

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"\n✅ 데이터베이스 생성 완료!")
    print(f"\n📈 통계 정보:")
    print(f"  - 총 환자 수: {len(cases)}명")

    # 연령대별 통계
    age_groups = {}
    for case in cases:
        age_group = f"{case['age']//10*10}대"
        age_groups[age_group] = age_groups.get(age_group, 0) + 1

    for age_group in sorted(age_groups.keys()):
        print(f"  - {age_group}: {age_groups[age_group]}명")

    # 성별 통계
    sex_count = {"남": 0, "여": 0}
    for case in cases:
        sex_count[case["sex"]] += 1
    print(f"  - 남성: {sex_count['남']}명, 여성: {sex_count['여']}명")


if __name__ == "__main__":
    main()
