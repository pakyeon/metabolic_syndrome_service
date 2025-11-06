"use client";

import { useState } from "react";
import styles from "./RightSidebar.module.css";
import { InsightsTab } from "./InsightsTab";
import { ReferencesPanel, Citation } from "../references/ReferencesPanel";

type TabType = "insights" | "references";

interface RightSidebarProps {
  // Insights 탭용 props
  patient: any;
  exam: any;
  survey: any;
  preparationAnalysis: any;
  highlightedQuestion?: string | null;

  // References 탭용 props
  citations: Citation[];

  // 상태 제어
  activeTab?: TabType;
  collapsed: boolean;
  onToggle: () => void;
}

export function RightSidebar({
  patient,
  exam,
  survey,
  preparationAnalysis,
  highlightedQuestion,
  citations,
  activeTab: controlledTab,
  collapsed,
  onToggle,
}: RightSidebarProps) {
  const [internalTab, setInternalTab] = useState<TabType>("insights");
  const activeTab = controlledTab || internalTab;

  if (collapsed) {
    return (
      <aside className={`${styles.sidebar} ${styles.collapsed}`}>
        <button onClick={onToggle} className={styles.toggleBtn}>
          «
        </button>
      </aside>
    );
  }

  return (
    <aside className={styles.sidebar}>
      <header className={styles.header}>
        <div className={styles.tabs}>
          <button
            className={`${styles.tabButton} ${activeTab === "insights" ? styles.active : ""}`}
            onClick={() => setInternalTab("insights")}
          >
            환자 & 인사이트
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === "references" ? styles.active : ""}`}
            onClick={() => setInternalTab("references")}
          >
            참고 문서
          </button>
        </div>
        <button onClick={onToggle} className={styles.toggleBtn}>
          »
        </button>
      </header>

      <div className={styles.body}>
        {activeTab === "insights" ? (
          <InsightsTab
            patient={patient}
            exam={exam}
            survey={survey}
            preparationAnalysis={preparationAnalysis}
            highlightedQuestion={highlightedQuestion}
          />
        ) : (
          <div className={styles.referencesWrapper}>
            <ReferencesPanel citations={citations} title="참고 문서" />
          </div>
        )}
      </div>
    </aside>
  );
}
