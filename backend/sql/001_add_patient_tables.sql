-- Migration: Add patient data tables
-- This migration adds patient information, health exams, and survey data tables
-- to support the metabolic syndrome counseling system.
--
-- SETUP INSTRUCTIONS:
-- Execute this migration: psql "$DATABASE_URL" -f backend/sql/001_add_patient_tables.sql

-- ============================================================================
-- PATIENTS TABLE
-- Stores basic patient information
-- ============================================================================
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,                       -- Patient unique ID (e.g., "P0001")
    name TEXT NOT NULL,                                -- Patient name
    sex TEXT NOT NULL CHECK (sex IN ('남', '여', 'M', 'F')),
    age INTEGER,                                       -- Current age
    birth_date DATE,                                   -- Birth date
    rrn_masked TEXT,                                   -- Masked resident registration number
    contact TEXT,                                      -- Phone number
    address TEXT,                                      -- Address
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patients_name ON patients (name);
CREATE INDEX idx_patients_registered_at ON patients (registered_at DESC);

-- ============================================================================
-- HEALTH_EXAMS TABLE
-- Stores metabolic syndrome test results
-- ============================================================================
CREATE TABLE IF NOT EXISTS health_exams (
    exam_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    exam_at TIMESTAMP WITH TIME ZONE NOT NULL,         -- Exam datetime
    facility_name TEXT,                                -- Exam facility
    doc_registered_on DATE,                            -- Document registration date

    -- Body measurements
    height_cm FLOAT,
    weight_kg FLOAT,
    bmi FLOAT,
    waist_cm FLOAT,

    -- Blood pressure
    systolic_mmHg INTEGER,
    diastolic_mmHg INTEGER,

    -- Metabolic markers
    fbg_mg_dl FLOAT,                                   -- Fasting blood glucose
    tg_mg_dl FLOAT,                                    -- Triglycerides
    hdl_mg_dl FLOAT,                                   -- HDL cholesterol
    tc_mg_dl FLOAT,                                    -- Total cholesterol
    ldl_mg_dl FLOAT,                                   -- LDL cholesterol

    -- Metabolic syndrome risk calculation
    risk_level TEXT CHECK (risk_level IN ('low', 'moderate', 'high')),
    risk_factors INTEGER DEFAULT 0,                    -- Number of risk factors (0-5)

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_health_exams_patient_id ON health_exams (patient_id, exam_at DESC);
CREATE INDEX idx_health_exams_exam_at ON health_exams (exam_at DESC);
CREATE INDEX idx_health_exams_risk_level ON health_exams (risk_level);

-- ============================================================================
-- SURVEYS TABLE
-- Stores survey responses (basic info)
-- ============================================================================
CREATE TABLE IF NOT EXISTS surveys (
    survey_id TEXT PRIMARY KEY,                        -- Survey unique ID (e.g., "SV202410280001")
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    patient_name TEXT,
    sex TEXT CHECK (sex IN ('M', 'F', '남', '여')),
    birth_date DATE,
    contact TEXT,
    address TEXT,

    -- Survey metadata
    visit_type TEXT NOT NULL CHECK (visit_type IN ('first', 'm3', 'm6', 'm9', 'm12')),
    survey_date TIMESTAMP WITH TIME ZONE NOT NULL,
    facility TEXT,

    -- Recent checkup info
    recent_checkup BOOLEAN,
    recent_checkup_date DATE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

CREATE INDEX idx_surveys_patient_id ON surveys (patient_id, survey_date DESC);
CREATE INDEX idx_surveys_survey_date ON surveys (survey_date DESC);
CREATE INDEX idx_surveys_visit_type ON surveys (visit_type);

-- ============================================================================
-- DISEASE_HISTORY TABLE
-- Stores patient disease diagnosis and treatment history
-- ============================================================================
CREATE TABLE IF NOT EXISTS disease_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    survey_id TEXT NOT NULL REFERENCES surveys(survey_id) ON DELETE CASCADE,

    disease_code TEXT NOT NULL,                        -- HTN, DM, DYSLIP, STROKE, CAD, CKD, OTHER
    disease_name TEXT,                                 -- Disease name (for OTHER)

    diagnosed BOOLEAN DEFAULT FALSE,
    prescribed BOOLEAN DEFAULT FALSE,
    taking_medication BOOLEAN DEFAULT FALSE,
    regular_medication BOOLEAN,                        -- Taking medication 20+ days/month
    duration_years INTEGER
);

CREATE INDEX idx_disease_history_survey_id ON disease_history (survey_id);
CREATE INDEX idx_disease_history_disease_code ON disease_history (disease_code);

-- ============================================================================
-- PHYSICAL_ACTIVITY TABLE
-- Stores patient physical activity and exercise data
-- ============================================================================
CREATE TABLE IF NOT EXISTS physical_activity (
    survey_id TEXT PRIMARY KEY REFERENCES surveys(survey_id) ON DELETE CASCADE,

    -- Sedentary time
    sedentary_hours INTEGER,
    sedentary_minutes INTEGER,

    -- Work-related activity (vigorous)
    work_vigorous_days INTEGER,
    work_vigorous_hours INTEGER,
    work_vigorous_minutes INTEGER,

    -- Work-related activity (moderate)
    work_moderate_days INTEGER,
    work_moderate_hours INTEGER,
    work_moderate_minutes INTEGER,

    -- Transportation
    transport_days INTEGER,
    transport_hours INTEGER,
    transport_minutes INTEGER,

    -- Leisure activity (vigorous)
    leisure_vigorous_days INTEGER,
    leisure_vigorous_hours INTEGER,
    leisure_vigorous_minutes INTEGER,

    -- Leisure activity (moderate)
    leisure_moderate_days INTEGER,
    leisure_moderate_hours INTEGER,
    leisure_moderate_minutes INTEGER,

    -- Exercise planning
    exercise_plan TEXT CHECK (exercise_plan IN ('NO_PLAN', 'FUTURE', 'OCCASIONAL', 'LESS_6M', 'MORE_6M')),
    no_exercise_reason TEXT CHECK (no_exercise_reason IN ('DISEASE', 'LAZY', 'NO_MONEY', 'NO_TIME', 'NO_FACILITY', 'OTHER')),
    no_exercise_reason_text TEXT
);

-- ============================================================================
-- DIET_HABIT TABLE
-- Stores patient diet and nutrition habits
-- ============================================================================
CREATE TABLE IF NOT EXISTS diet_habit (
    survey_id TEXT PRIMARY KEY REFERENCES surveys(survey_id) ON DELETE CASCADE,

    -- Breakfast frequency
    breakfast_frequency TEXT CHECK (breakfast_frequency IN ('5_7PW', '3_4PW', '1_2PW', 'RARELY')),

    -- Diet practice score (each 0 or 1)
    diet_q1_whole_grains INTEGER CHECK (diet_q1_whole_grains IN (0, 1)),
    diet_q2_vegetables INTEGER CHECK (diet_q2_vegetables IN (0, 1)),
    diet_q3_fruits INTEGER CHECK (diet_q3_fruits IN (0, 1)),
    diet_q4_dairy INTEGER CHECK (diet_q4_dairy IN (0, 1)),
    diet_q5_regular_meals INTEGER CHECK (diet_q5_regular_meals IN (0, 1)),
    diet_q6_balanced_diet INTEGER CHECK (diet_q6_balanced_diet IN (0, 1)),
    diet_q7_low_salt INTEGER CHECK (diet_q7_low_salt IN (0, 1)),
    diet_q8_no_extra_salt INTEGER CHECK (diet_q8_no_extra_salt IN (0, 1)),
    diet_q9_trim_fat INTEGER CHECK (diet_q9_trim_fat IN (0, 1)),
    diet_q10_avoid_fried INTEGER CHECK (diet_q10_avoid_fried IN (0, 1)),

    diet_total_score INTEGER CHECK (diet_total_score >= 0 AND diet_total_score <= 10),

    -- Poor diet reasons
    poor_diet_reason TEXT CHECK (poor_diet_reason IN ('ECONOMIC', 'NO_HELP', 'WEAK_WILL', 'DENTAL', 'NO_INFO', 'NO_APPETITE', 'OTHER')),
    poor_diet_reason_text TEXT
);

-- ============================================================================
-- OBESITY_MANAGEMENT TABLE
-- Stores weight change and body perception data
-- ============================================================================
CREATE TABLE IF NOT EXISTS obesity_management (
    survey_id TEXT PRIMARY KEY REFERENCES surveys(survey_id) ON DELETE CASCADE,

    -- Weight change in past 6 months
    weight_change TEXT CHECK (weight_change IN ('NO_CHANGE', 'DECREASED', 'INCREASED')),
    weight_change_kg FLOAT,

    -- Body shape perception
    body_shape_perception TEXT CHECK (body_shape_perception IN ('VERY_THIN', 'THIN', 'NORMAL', 'OVERWEIGHT', 'OBESE')),

    -- Weight control effort
    weight_control_effort TEXT CHECK (weight_control_effort IN ('LOSE', 'MAINTAIN', 'GAIN', 'NONE'))
);

-- ============================================================================
-- MENTAL_HEALTH TABLE
-- Stores sleep and PHQ-9 depression screening data
-- ============================================================================
CREATE TABLE IF NOT EXISTS mental_health (
    survey_id TEXT PRIMARY KEY REFERENCES surveys(survey_id) ON DELETE CASCADE,

    -- Sleep hours
    sleep_hours_weekday INTEGER,
    sleep_hours_weekend INTEGER,

    -- PHQ-9 scores (each 0-3)
    phq9_q1_depressed INTEGER CHECK (phq9_q1_depressed >= 0 AND phq9_q1_depressed <= 3),
    phq9_q2_no_interest INTEGER CHECK (phq9_q2_no_interest >= 0 AND phq9_q2_no_interest <= 3),
    phq9_q3_sleep_problem INTEGER CHECK (phq9_q3_sleep_problem >= 0 AND phq9_q3_sleep_problem <= 3),
    phq9_q4_appetite INTEGER CHECK (phq9_q4_appetite >= 0 AND phq9_q4_appetite <= 3),
    phq9_q5_psychomotor INTEGER CHECK (phq9_q5_psychomotor >= 0 AND phq9_q5_psychomotor <= 3),
    phq9_q6_fatigue INTEGER CHECK (phq9_q6_fatigue >= 0 AND phq9_q6_fatigue <= 3),
    phq9_q7_guilt INTEGER CHECK (phq9_q7_guilt >= 0 AND phq9_q7_guilt <= 3),
    phq9_q8_concentration INTEGER CHECK (phq9_q8_concentration >= 0 AND phq9_q8_concentration <= 3),
    phq9_q9_suicide INTEGER CHECK (phq9_q9_suicide >= 0 AND phq9_q9_suicide <= 3),

    phq9_total_score INTEGER CHECK (phq9_total_score >= 0 AND phq9_total_score <= 27)
);

-- ============================================================================
-- CUSTOM FUNCTIONS
-- ============================================================================

-- Calculate metabolic syndrome risk level for a health exam
CREATE OR REPLACE FUNCTION calculate_metabolic_syndrome_risk(
    sex_param TEXT,
    waist_cm_param FLOAT,
    systolic_param INTEGER,
    diastolic_param INTEGER,
    fbg_param FLOAT,
    tg_param FLOAT,
    hdl_param FLOAT
)
RETURNS TABLE (
    risk_factors INTEGER,
    risk_level TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    risk_count INTEGER := 0;
    normalized_sex TEXT;
BEGIN
    -- Normalize sex parameter
    normalized_sex := CASE
        WHEN sex_param IN ('M', '남') THEN 'M'
        WHEN sex_param IN ('F', '여') THEN 'F'
        ELSE sex_param
    END;

    -- 1. Abdominal obesity (Korean criteria)
    IF (normalized_sex = 'M' AND waist_cm_param >= 90) OR
       (normalized_sex = 'F' AND waist_cm_param >= 85) THEN
        risk_count := risk_count + 1;
    END IF;

    -- 2. Hypertension
    IF systolic_param >= 130 OR diastolic_param >= 85 THEN
        risk_count := risk_count + 1;
    END IF;

    -- 3. Impaired fasting glucose
    IF fbg_param >= 100 THEN
        risk_count := risk_count + 1;
    END IF;

    -- 4. Hypertriglyceridemia
    IF tg_param >= 150 THEN
        risk_count := risk_count + 1;
    END IF;

    -- 5. Low HDL cholesterol
    IF (normalized_sex = 'M' AND hdl_param < 40) OR
       (normalized_sex = 'F' AND hdl_param < 50) THEN
        risk_count := risk_count + 1;
    END IF;

    -- Determine risk level
    RETURN QUERY SELECT
        risk_count,
        CASE
            WHEN risk_count >= 3 THEN 'high'
            WHEN risk_count = 2 THEN 'moderate'
            ELSE 'low'
        END;
END;
$$;

-- Update trigger for health_exams to auto-calculate risk
CREATE OR REPLACE FUNCTION update_health_exam_risk()
RETURNS TRIGGER AS $$
DECLARE
    patient_sex TEXT;
    calc_result RECORD;
BEGIN
    -- Get patient sex
    SELECT sex INTO patient_sex FROM patients WHERE patient_id = NEW.patient_id;

    -- Calculate risk
    SELECT * INTO calc_result FROM calculate_metabolic_syndrome_risk(
        patient_sex,
        NEW.waist_cm,
        NEW.systolic_mmHg,
        NEW.diastolic_mmHg,
        NEW.fbg_mg_dl,
        NEW.tg_mg_dl,
        NEW.hdl_mg_dl
    );

    -- Update NEW record
    NEW.risk_factors := calc_result.risk_factors;
    NEW.risk_level := calc_result.risk_level;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_health_exam_risk_trigger
    BEFORE INSERT OR UPDATE ON health_exams
    FOR EACH ROW
    EXECUTE FUNCTION update_health_exam_risk();

-- Auto-update timestamps
CREATE TRIGGER update_patients_updated_at BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_health_exams_updated_at BEFORE UPDATE ON health_exams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- Latest health exam for each patient
CREATE OR REPLACE VIEW patient_latest_exams AS
SELECT DISTINCT ON (patient_id)
    patient_id,
    exam_id,
    exam_at,
    facility_name,
    bmi,
    waist_cm,
    systolic_mmHg,
    diastolic_mmHg,
    fbg_mg_dl,
    tg_mg_dl,
    hdl_mg_dl,
    risk_level,
    risk_factors
FROM health_exams
ORDER BY patient_id, exam_at DESC;

-- Patient summary with latest exam
CREATE OR REPLACE VIEW patient_summaries AS
SELECT
    p.patient_id,
    p.name,
    p.sex,
    p.age,
    p.birth_date,
    p.contact,
    p.registered_at,
    e.exam_at AS latest_exam_at,
    e.exam_id AS latest_exam_id,
    e.risk_level,
    e.risk_factors,
    e.bmi,
    e.systolic_mmHg,
    e.diastolic_mmHg,
    e.fbg_mg_dl
FROM patients p
LEFT JOIN patient_latest_exams e ON p.patient_id = e.patient_id;

-- ============================================================================
-- VERIFICATION QUERIES
-- Run these to verify the migration was successful:
--
-- List new tables:
--   SELECT tablename FROM pg_tables WHERE schemaname = 'public'
--   AND tablename IN ('patients', 'health_exams', 'surveys');
--
-- Check patient count:
--   SELECT COUNT(*) FROM patients;
--
-- View patient summaries:
--   SELECT * FROM patient_summaries ORDER BY latest_exam_at DESC NULLS LAST LIMIT 5;
-- ============================================================================
