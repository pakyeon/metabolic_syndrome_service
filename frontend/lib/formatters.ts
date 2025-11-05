import { HealthExam, SurveyDetail } from '../hooks/usePatientData';

export interface BiomarkerHighlight {
  label: string;
  value: string;
  status: 'optimal' | 'elevated' | 'critical';
  guidance: string;
}

export interface LifestyleHighlight {
  title: string;
  detail: string;
}

export function formatBiomarkers(exam: HealthExam | null, patientSex?: string): BiomarkerHighlight[] {
  if (!exam) return [];

  const highlights: BiomarkerHighlight[] = [];

  // BMI
  if (exam.bmi !== undefined) {
    const bmiValue = exam.bmi;
    let status: 'optimal' | 'elevated' | 'critical' = 'optimal';
    let guidance = 'BMI가 정상 범위입니다. 현재 체중을 유지하세요.';

    if (bmiValue >= 30) {
      status = 'critical';
      guidance = '비만 범위입니다. 주 150분 이상 유산소 운동과 식단 조절을 권장합니다.';
    } else if (bmiValue >= 25) {
      status = 'elevated';
      guidance = '과체중 범위입니다. 주 3-4회 30분 걷기와 균형 잡힌 식단을 권장합니다.';
    }

    highlights.push({
      label: 'BMI',
      value: `${bmiValue.toFixed(1)} kg/m²`,
      status,
      guidance,
    });
  }

  // Waist circumference
  if (exam.waist_cm !== undefined) {
    const waist = exam.waist_cm;
    const maleThreshold = 90;
    const femaleThreshold = 85;
    const threshold = patientSex === '남' || patientSex === 'M' ? maleThreshold : femaleThreshold;

    let status: 'optimal' | 'elevated' | 'critical' = 'optimal';
    let guidance = '허리둘레가 정상 범위입니다.';

    if (waist >= threshold) {
      status = 'critical';
      guidance = '복부비만입니다. 생활습관 개선이 필요합니다. 스트레칭과 업무 중 2시간마다 5분 걷기를 권장합니다.';
    } else if (waist >= threshold - 5) {
      status = 'elevated';
      guidance = '허리둘레가 경계선입니다. 복부 운동과 식단 관리를 시작하세요.';
    }

    highlights.push({
      label: '허리둘레',
      value: `${waist.toFixed(0)} cm`,
      status,
      guidance,
    });
  }

  // Blood pressure
  if (exam.systolic_mmHg !== undefined && exam.diastolic_mmHg !== undefined) {
    const systolic = exam.systolic_mmHg;
    const diastolic = exam.diastolic_mmHg;

    let status: 'optimal' | 'elevated' | 'critical' = 'optimal';
    let guidance = '혈압이 정상 범위입니다.';

    if (systolic >= 140 || diastolic >= 90) {
      status = 'critical';
      guidance = '고혈압입니다. 담당 의사와 상담하시고 저염식과 규칙적인 운동을 실천하세요.';
    } else if (systolic >= 130 || diastolic >= 85) {
      status = 'elevated';
      guidance = '혈압이 경계선입니다. 염분 섭취를 줄이고 스트레스 관리를 권장합니다.';
    }

    highlights.push({
      label: '혈압',
      value: `${systolic}/${diastolic} mmHg`,
      status,
      guidance,
    });
  }

  // Fasting blood glucose
  if (exam.fbg_mg_dl !== undefined) {
    const fbg = exam.fbg_mg_dl;

    let status: 'optimal' | 'elevated' | 'critical' = 'optimal';
    let guidance = '공복혈당이 정상 범위입니다.';

    if (fbg >= 126) {
      status = 'critical';
      guidance = '당뇨병 범위입니다. 즉시 담당 의사와 상담이 필요합니다.';
    } else if (fbg >= 100) {
      status = 'elevated';
      guidance = '당뇨병 전단계입니다. 아침 조깅 전 간단한 간식과 주 3회 근력운동을 권장합니다.';
    }

    highlights.push({
      label: '공복 혈당',
      value: `${fbg.toFixed(0)} mg/dL`,
      status,
      guidance,
    });
  }

  // Triglycerides
  if (exam.tg_mg_dl !== undefined) {
    const tg = exam.tg_mg_dl;

    let status: 'optimal' | 'elevated' | 'critical' = 'optimal';
    let guidance = '중성지방이 정상 범위입니다.';

    if (tg >= 200) {
      status = 'critical';
      guidance = '중성지방이 높습니다. 유산소 운동과 저지방 식단을 권장합니다.';
    } else if (tg >= 150) {
      status = 'elevated';
      guidance = '중성지방이 경계선입니다. 주 3회 이상 30분 이상 걷기를 권장합니다.';
    }

    highlights.push({
      label: '중성지방',
      value: `${tg.toFixed(0)} mg/dL`,
      status,
      guidance,
    });
  }

  // HDL Cholesterol
  if (exam.hdl_mg_dl !== undefined) {
    const hdl = exam.hdl_mg_dl;
    const maleThreshold = 40;
    const femaleThreshold = 50;
    const threshold = patientSex === '남' || patientSex === 'M' ? maleThreshold : femaleThreshold;

    let status: 'optimal' | 'elevated' | 'critical' = 'optimal';
    let guidance = 'HDL 콜레스테롤이 정상 범위입니다.';

    if (hdl < threshold) {
      status = 'critical';
      guidance = 'HDL 콜레스테롤이 낮습니다. 유산소 운동을 늘리고 건강한 지방 섭취를 권장합니다.';
    } else if (hdl < threshold + 10) {
      status = 'elevated';
      guidance = 'HDL 콜레스테롤이 경계선입니다. 규칙적인 운동을 권장합니다.';
    } else if (hdl >= 60) {
      guidance = '최근 상승 추세이므로 긍정적 피드백을 제공하고 지속을 격려하세요.';
    }

    highlights.push({
      label: 'HDL 콜레스테롤',
      value: `${hdl.toFixed(0)} mg/dL`,
      status,
      guidance,
    });
  }

  return highlights;
}

export function formatLifestyle(survey: SurveyDetail | null): LifestyleHighlight[] {
  if (!survey) return [];

  const highlights: LifestyleHighlight[] = [];

  // Physical activity
  if (survey.physical_activity) {
    const { exercise_plan, sedentary_hours, sedentary_minutes, no_exercise_reason } = survey.physical_activity;

    let detail = '';
    if (exercise_plan === 'NONE' || exercise_plan === 'OCCASIONAL') {
      detail = `운동 계획: ${exercise_plan === 'NONE' ? '없음' : '가끔'}`;
      if (no_exercise_reason) {
        detail += `. 이유: ${no_exercise_reason}`;
      }
      detail += '. 짧은 시간 운동부터 시작하도록 격려하세요.';
    } else if (exercise_plan === 'REGULAR') {
      detail = '규칙적으로 운동 중입니다. 현재 활동을 유지하고 강도를 점진적으로 높이세요.';
    }

    if (sedentary_hours !== undefined) {
      const totalMinutes = (sedentary_hours * 60) + (sedentary_minutes || 0);
      detail += ` 좌식 시간: 하루 ${sedentary_hours}시간 ${sedentary_minutes || 0}분`;

      if (totalMinutes > 480) { // 8 hours
        detail += '. 2시간마다 5-10분 스트레칭을 권장합니다.';
      }
    }

    if (detail) {
      highlights.push({
        title: '활동 패턴',
        detail,
      });
    }
  }

  // Diet habits
  if (survey.diet_habit) {
    const { diet_total_score, breakfast_frequency } = survey.diet_habit;

    let detail = '';
    if (diet_total_score !== undefined) {
      detail = `식습관 점수: ${diet_total_score}/10점`;

      if (diet_total_score < 5) {
        detail += '. 식습관 개선이 필요합니다.';
      } else if (diet_total_score >= 7) {
        detail += '. 좋은 식습관을 유지 중입니다.';
      }
    }

    if (breakfast_frequency) {
      const freqMap: Record<string, string> = {
        'EVERYDAY': '매일',
        '5_6PW': '주 5-6회',
        '3_4PW': '주 3-4회',
        '1_2PW': '주 1-2회',
        'NONE': '거의 안 함',
      };
      detail += ` 아침식사: ${freqMap[breakfast_frequency] || breakfast_frequency}`;

      if (breakfast_frequency === '1_2PW' || breakfast_frequency === 'NONE') {
        detail += '. 아침식사를 규칙적으로 하도록 격려하세요.';
      }
    }

    if (detail) {
      highlights.push({
        title: '식습관',
        detail,
      });
    }
  }

  // Mental health
  if (survey.mental_health) {
    const { phq9_total_score, sleep_hours_weekday, sleep_hours_weekend } = survey.mental_health;

    let detail = '';
    if (phq9_total_score !== undefined) {
      detail = `정신건강 (PHQ-9): ${phq9_total_score}점`;

      if (phq9_total_score >= 10) {
        detail += '. 우울 증상이 있습니다. 전문가 상담을 권장합니다.';
      } else if (phq9_total_score >= 5) {
        detail += '. 경미한 스트레스가 있습니다. 이완 기법을 제안하세요.';
      } else {
        detail += '. 정신건강이 양호합니다.';
      }
    }

    if (sleep_hours_weekday !== undefined) {
      detail += ` 수면: 평일 ${sleep_hours_weekday}시간`;
      if (sleep_hours_weekend !== undefined) {
        detail += `, 주말 ${sleep_hours_weekend}시간`;
      }

      if (sleep_hours_weekday < 6) {
        detail += '. 수면 부족입니다. 수면 위생 개선을 권장합니다.';
      }
    }

    if (detail) {
      highlights.push({
        title: '정신건강 및 수면',
        detail,
      });
    }
  }

  // Obesity management awareness
  if (survey.obesity_management) {
    const { body_shape_perception, weight_control_effort } = survey.obesity_management;

    let detail = '';
    if (body_shape_perception) {
      const perceptionMap: Record<string, string> = {
        'VERY_THIN': '매우 마름',
        'THIN': '약간 마름',
        'NORMAL': '보통',
        'FAT': '약간 비만',
        'VERY_FAT': '매우 비만',
      };
      detail = `체형 인식: ${perceptionMap[body_shape_perception] || body_shape_perception}`;
    }

    if (weight_control_effort) {
      const effortMap: Record<string, string> = {
        'NONE': '노력 없음',
        'MAINTAIN': '체중 유지',
        'LOSE': '체중 감량',
        'GAIN': '체중 증가',
      };
      detail += ` 체중조절 노력: ${effortMap[weight_control_effort] || weight_control_effort}`;
    }

    if (detail) {
      highlights.push({
        title: '체중 관리 인식',
        detail,
      });
    }
  }

  return highlights;
}
