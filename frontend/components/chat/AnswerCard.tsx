import styles from './AnswerCard.module.css';

interface AnswerCardProps {
  answer: string;
  citations?: string[];
  onCitationClick?: (citation: string) => void;
}

export function AnswerCard({ answer, citations = [], onCitationClick }: AnswerCardProps) {
  // Extract key recommendations (first 1-2 sentences or bullet points)
  const { keyPoints, details } = extractSections(answer);

  return (
    <div className={styles.answerCard}>
      {/* Key Recommendations */}
      <div className={styles.keyPoints}>
        <div className={styles.keyPointsHeader}>
          <span className={styles.keyPointsIcon}>💡</span>
          <span>핵심 권장사항</span>
        </div>
        <p className={styles.keyPointsText}>{keyPoints}</p>
      </div>

      {/* Detailed Explanation */}
      {details && (
        <div className={styles.details}>
          <div className={styles.detailsTitle}>상세 설명</div>
          <div className={styles.detailsText}>{details}</div>
        </div>
      )}

      {/* Citations */}
      {citations.length > 0 && (
        <div className={styles.citations}>
          <span className={styles.citationsLabel}>출처:</span>
          {citations.map((citation, idx) => (
            <button
              key={idx}
              className={styles.citationBadge}
              onClick={() => onCitationClick?.(citation)}
              title={`출처 상세보기: ${citation}`}
            >
              <span className={styles.citationIcon}>📄</span>
              <span>{citation}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function extractSections(answer: string): { keyPoints: string; details: string | null } {
  // Remove citations that were appended by composeAnswer
  const cleanAnswer = answer.replace(/\n\n참고:.*$/s, '').trim();

  // Split by sentences
  const sentences = cleanAnswer.split(/(?<=[.!?])\s+/);

  if (sentences.length === 0) {
    return { keyPoints: cleanAnswer, details: null };
  }

  // Check if answer has bullet points or numbered lists
  const lines = cleanAnswer.split('\n');
  const hasBullets = lines.some(line => /^[\-\*\d]+[\.\)]\s/.test(line.trim()));

  if (hasBullets) {
    // Extract first bullet point or first paragraph as key points
    const firstParagraphEnd = lines.findIndex((line, idx) => idx > 0 && line.trim() === '');
    if (firstParagraphEnd > 0) {
      const keyPointsLines = lines.slice(0, firstParagraphEnd);
      const detailsLines = lines.slice(firstParagraphEnd + 1);

      return {
        keyPoints: keyPointsLines.join('\n').trim(),
        details: detailsLines.length > 0 ? detailsLines.join('\n').trim() : null,
      };
    }
  }

  // Fallback: First 1-2 sentences as key points
  if (sentences.length <= 2) {
    return {
      keyPoints: cleanAnswer,
      details: null,
    };
  }

  const keyPoints = sentences.slice(0, 2).join(' ');
  const details = sentences.slice(2).join(' ');

  return {
    keyPoints,
    details: details.length > 0 ? details : null,
  };
}
