"use client";

import { useState } from 'react';
import styles from './ReferencesPanel.module.css';
import { CitationModal } from './CitationModal';

export interface Citation {
  id: string;
  title: string;
  content: string;
  relevance_score: number;
  source?: string;
  page?: number;
  metadata?: Record<string, any>;
}

interface ReferencesPanelProps {
  citations: Citation[];
  title?: string;
}

export function ReferencesPanel({ citations, title = "참고 문서" }: ReferencesPanelProps) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  if (citations.length === 0) {
    return (
      <aside className={styles.referencesPanel}>
        <h3 className={styles.panelTitle}>{title}</h3>
        <p className={styles.emptyState}>아직 참고 문서가 없습니다.</p>
      </aside>
    );
  }

  return (
    <>
      <aside className={styles.referencesPanel}>
        <h3 className={styles.panelTitle}>
          {title}
          <span className={styles.citationCount}>{citations.length}</span>
        </h3>
        <div className={styles.citationList}>
          {citations.map((citation, idx) => (
            <div
              key={citation.id || idx}
              className={styles.citationCard}
              onClick={() => setSelectedCitation(citation)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  setSelectedCitation(citation);
                }
              }}
            >
              <div className={styles.citationHeader}>
                <span className={styles.citationNumber}>#{idx + 1}</span>
                <strong className={styles.citationTitle}>{citation.title}</strong>
              </div>

              {citation.source && (
                <div className={styles.citationSource}>
                  <span className={styles.sourceIcon}>📄</span>
                  <span className={styles.sourceText}>{citation.source}</span>
                  {citation.page !== undefined && (
                    <span className={styles.pageText}>p.{citation.page}</span>
                  )}
                </div>
              )}

              <div className={styles.citationPreview}>
                {citation.content.substring(0, 120)}
                {citation.content.length > 120 ? '...' : ''}
              </div>

              <div className={styles.relevanceSection}>
                <span className={styles.relevanceLabel}>관련도</span>
                <div className={styles.relevanceBar}>
                  <div
                    className={styles.relevanceBarFill}
                    style={{ width: `${Math.round(citation.relevance_score * 100)}%` }}
                  />
                </div>
                <span className={styles.relevanceScore}>
                  {Math.round(citation.relevance_score * 100)}%
                </span>
              </div>

              <div className={styles.citationFooter}>
                <span className={styles.viewDetailsLink}>상세 보기 →</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {selectedCitation && (
        <CitationModal
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </>
  );
}
