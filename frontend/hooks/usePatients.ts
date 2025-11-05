import { useEffect, useState } from 'react';

export interface PatientSummary {
  patient_id: string;
  name: string;
  sex: string;
  age: number;
  birth_date: string;
  contact?: string;
  latest_exam_at?: string;
  latest_exam_id?: string;
  risk_level?: string;
  risk_factors?: number;
  bmi?: number;
  systolic_mmHg?: number;
  diastolic_mmHg?: number;
  fbg_mg_dl?: number;
}

export function usePatients(sortBy: string = 'latest_exam_at', order: string = 'desc') {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchPatients() {
      setLoading(true);
      setError(null);

      try {
        const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const response = await fetch(
          `${baseUrl}/v1/patients?sort_by=${sortBy}&order=${order}&limit=100`
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch patients: ${response.statusText}`);
        }

        const data = await response.json();
        setPatients(data);
      } catch (err) {
        console.error('Error fetching patients:', err);
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchPatients();
  }, [sortBy, order]);

  return { patients, loading, error };
}
