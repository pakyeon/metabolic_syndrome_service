"use client";

import { ReactNode } from "react";
import styles from "./quickActions.module.css";

export type QuickAction = {
  id: string;
  label: string;
  description: string;
  prompt: string;
  icon?: ReactNode;
};

type QuickActionsProps = {
  actions: QuickAction[];
  onSelect: (action: QuickAction) => void;
};

export function QuickActions({ actions, onSelect }: QuickActionsProps) {
  return (
    <div className={styles.grid} aria-label="Quick action prompts">
      {actions.map((action) => (
        <button
          key={action.id}
          type="button"
          onClick={() => onSelect(action)}
          className={styles.button}
        >
          <span className={styles.label}>
            {action.icon}
            {action.label}
          </span>
          <span className={styles.helper}>{action.description}</span>
        </button>
      ))}
    </div>
  );
}
