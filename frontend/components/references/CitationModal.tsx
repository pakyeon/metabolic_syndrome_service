"use client";

import { useEffect } from 'react';
import styles from './CitationModal.module.css';
import { Citation } from './ReferencesPanel';

interface CitationModalProps {
  citation: Citation;
  onClose: () => void;
}

export function CitationModal({ citation, onClose }: CitationModalProps) {
  // Close modal on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className={styles.modalHeader}>
          <div className={styles.headerContent}>
            <h2 className={styles.modalTitle}>{citation.title}</h2>
            {citation.source && (
              <div className={styles.sourceInfo}>
                <span className={styles.sourceIcon}>📄</span>
                <span>{citation.source}</span>
                {citation.page !== undefined && (
                  <span className={styles.pageNumber}>페이지 {citation.page}</span>
                )}
              </div>
            )}
          </div>
          <button
            className={styles.closeButton}
            onClick={onClose}
            aria-label="닫기"
            title="닫기 (ESC)"
          >
            ✕
          </button>
        </header>

        {/* Relevance Score */}
        <div className={styles.relevanceSection}>
          <span className={styles.relevanceLabel}>관련도 점수</span>
          <div className={styles.relevanceBarLarge}>
            <div
              className={styles.relevanceBarFill}
              style={{ width: `${Math.round(citation.relevance_score * 100)}%` }}
            />
          </div>
          <span className={styles.relevanceScore}>
            {Math.round(citation.relevance_score * 100)}%
          </span>
        </div>

        {/* Content */}
        <div className={styles.modalBody}>
          <h3 className={styles.contentTitle}>문서 내용</h3>
          <div className={styles.contentText}>
            {citation.content}
          </div>
        </div>

        {/* Metadata */}
        {citation.metadata && Object.keys(citation.metadata).length > 0 && (
          <div className={styles.metadataSection}>
            <h3 className={styles.metadataTitle}>추가 정보</h3>
            <dl className={styles.metadataList}>
              {Object.entries(citation.metadata).map(([key, value]) => (
                <div key={key} className={styles.metadataItem}>
                  <dt className={styles.metadataKey}>{key}</dt>
                  <dd className={styles.metadataValue}>{String(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {/* Footer */}
        <footer className={styles.modalFooter}>
          <button className={styles.closeFooterButton} onClick={onClose}>
            닫기
          </button>
        </footer>
      </div>
    </div>
  );
}
