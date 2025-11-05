import styles from './BiomarkerCard.module.css';

interface BiomarkerCardProps {
  label: string;
  value: number | string;
  threshold: number;
  inverse?: boolean;
  unit?: string;
}

export function BiomarkerCard({ label, value, threshold, inverse = false, unit = '' }: BiomarkerCardProps) {
  const numValue = typeof value === 'number' ? value : parseFloat(value.toString());

  if (isNaN(numValue)) {
    return (
      <div className={styles.card}>
        <div className={styles.label}>{label}</div>
        <div className={styles.value}>-</div>
      </div>
    );
  }

  // Determine status based on threshold
  let status: 'optimal' | 'elevated' | 'critical' = 'optimal';

  if (inverse) {
    // For HDL: lower is worse
    if (numValue < threshold * 0.8) {
      status = 'critical';
    } else if (numValue < threshold) {
      status = 'elevated';
    }
  } else {
    // For most biomarkers: higher is worse
    if (numValue >= threshold * 1.2) {
      status = 'critical';
    } else if (numValue >= threshold) {
      status = 'elevated';
    }
  }

  const statusColors = {
    optimal: '#16a34a',
    elevated: '#f59e0b',
    critical: '#dc2626',
  };

  const statusLabels = {
    optimal: '정상',
    elevated: '경계',
    critical: '주의',
  };

  return (
    <div className={styles.card}>
      <div className={styles.label}>{label}</div>
      <div className={styles.valueRow}>
        <span className={styles.value} style={{ color: statusColors[status] }}>
          {numValue.toFixed(1)}{unit}
        </span>
        <span className={styles.status} style={{ color: statusColors[status], backgroundColor: `${statusColors[status]}15` }}>
          {statusLabels[status]}
        </span>
      </div>
      <div className={styles.threshold}>
        기준: {inverse ? '≥' : '<'} {threshold}{unit}
      </div>
    </div>
  );
}
