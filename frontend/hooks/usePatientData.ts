import { useEffect, useState } from 'react';

export interface PatientDetail {
  patient_id: string;
  name: string;
  sex: string;
  age: number;
  birth_date: string;
  contact?: string;
  registered_at: string;
  updated_at: string;
}

export interface HealthExam {
  exam_id: number;
  patient_id: string;
  exam_at: string;
  facility_name?: string;
  height_cm?: number;
  weight_kg?: number;
  bmi?: number;
  waist_cm?: number;
  systolic_mmHg?: number;
  diastolic_mmHg?: number;
  fbg_mg_dl?: number;
  tg_mg_dl?: number;
  hdl_mg_dl?: number;
  risk_factors?: number;
  risk_level?: string;
}

export interface PhysicalActivity {
  sedentary_hours?: number;
  sedentary_minutes?: number;
  exercise_plan?: string;
  no_exercise_reason?: string;
}

export interface DietHabit {
  diet_total_score?: number;
  breakfast_frequency?: string;
}

export interface MentalHealth {
  phq9_total_score?: number;
  sleep_hours_weekday?: number;
  sleep_hours_weekend?: number;
}

export interface ObesityManagement {
  body_shape_perception?: string;
  weight_control_effort?: string;
}

export interface SurveyDetail {
  survey_id: string;
  patient_id: string;
  surveyed_at: string;
  physical_activity?: PhysicalActivity;
  diet_habit?: DietHabit;
  mental_health?: MentalHealth;
  obesity_management?: ObesityManagement;
}

interface PatientData {
  patient: PatientDetail;
  latestExam: HealthExam | null;
  survey: SurveyDetail | null;
  tests: HealthExam[];
}

export function usePatientData(patientId: string | null) {
  const [data, setData] = useState<PatientData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!patientId) {
      setData(null);
      setLoading(false);
      return;
    }

    async function fetchAllData() {
      setLoading(true);
      setError(null);

      try {
        const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

        // Parallel API calls for performance
        const [patientRes, examRes, surveyRes, testsRes] = await Promise.all([
          fetch(`${baseUrl}/v1/patients/${patientId}`),
          fetch(`${baseUrl}/v1/patients/${patientId}/latest-exam`),
          fetch(`${baseUrl}/v1/patients/${patientId}/survey`),
          fetch(`${baseUrl}/v1/patients/${patientId}/tests?limit=5`),
        ]);

        // Check for errors
        if (!patientRes.ok) {
          throw new Error(`Failed to fetch patient: ${patientRes.statusText}`);
        }

        const [patient, latestExam, survey, tests] = await Promise.all([
          patientRes.json(),
          examRes.ok ? examRes.json() : null,
          surveyRes.ok ? surveyRes.json() : null,
          testsRes.ok ? testsRes.json() : [],
        ]);

        setData({ patient, latestExam, survey, tests });
      } catch (err) {
        console.error('Error fetching patient data:', err);
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchAllData();
  }, [patientId]);

  return { data, loading, error };
}
