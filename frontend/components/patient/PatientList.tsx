'use client';

import { useRouter } from 'next/navigation';
import { usePatients } from '../../hooks/usePatients';
import styles from './PatientList.module.css';

export default function PatientList() {
  const { patients, loading, error } = usePatients('latest_exam_at', 'desc');
  const router = useRouter();

  const handlePatientClick = (patientId: string) => {
    router.push(`/?patient_id=${patientId}`);
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  const getRiskBadgeClass = (riskLevel?: string) => {
    if (!riskLevel) return styles.riskBadge;
    switch (riskLevel.toLowerCase()) {
      case 'high':
        return `${styles.riskBadge} ${styles.riskHigh}`;
      case 'moderate':
        return `${styles.riskBadge} ${styles.riskModerate}`;
      case 'low':
        return `${styles.riskBadge} ${styles.riskLow}`;
      default:
        return styles.riskBadge;
    }
  };

  const getBiomarkerClass = (value?: number, threshold?: number, inverse: boolean = false) => {
    if (value === undefined || threshold === undefined) return styles.biomarkerValue;

    const isElevated = inverse ? value < threshold : value >= threshold;
    const isCritical = inverse
      ? value < threshold * 0.8
      : value >= threshold * 1.2;

    if (isCritical) return `${styles.biomarkerValue} ${styles.biomarkerCritical}`;
    if (isElevated) return `${styles.biomarkerValue} ${styles.biomarkerElevated}`;
    return `${styles.biomarkerValue} ${styles.biomarkerOptimal}`;
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <p>환자 목록을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.errorContainer}>
          <h2>오류가 발생했습니다</h2>
          <p>{error.message}</p>
        </div>
      </div>
    );
  }

  if (patients.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <p>등록된 환자가 없습니다</p>
          <small>환자 데이터를 추가해주세요.</small>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>환자 목록</h1>
        <p>{patients.length}명의 환자 · 최근 검사 순으로 정렬</p>
      </div>

      <table className={styles.patientTable}>
        <thead>
          <tr>
            <th>이름</th>
            <th>나이</th>
            <th>성별</th>
            <th>최근 검사일</th>
            <th>위험도</th>
            <th>BMI</th>
            <th>혈압</th>
            <th>공복혈당</th>
          </tr>
        </thead>
        <tbody>
          {patients.map((patient) => (
            <tr
              key={patient.patient_id}
              onClick={() => handlePatientClick(patient.patient_id)}
              className={styles.clickableRow}
            >
              <td>{patient.name}</td>
              <td>{patient.age}세</td>
              <td>{patient.sex === 'M' || patient.sex === '남' ? '남' : '여'}</td>
              <td>{formatDate(patient.latest_exam_at)}</td>
              <td>
                {patient.risk_level ? (
                  <span className={getRiskBadgeClass(patient.risk_level)}>
                    {patient.risk_level}
                    {patient.risk_factors !== undefined && ` (${patient.risk_factors}/5)`}
                  </span>
                ) : (
                  '-'
                )}
              </td>
              <td>
                <span className={getBiomarkerClass(patient.bmi, 25)}>
                  {patient.bmi?.toFixed(1) ?? '-'}
                </span>
              </td>
              <td>
                <span className={getBiomarkerClass(patient.systolic_mmHg, 130)}>
                  {patient.systolic_mmHg && patient.diastolic_mmHg
                    ? `${patient.systolic_mmHg}/${patient.diastolic_mmHg}`
                    : '-'}
                </span>
              </td>
              <td>
                <span className={getBiomarkerClass(patient.fbg_mg_dl, 100)}>
                  {patient.fbg_mg_dl?.toFixed(0) ?? '-'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
