"use client";

import { useCallback } from "react";
import type { ChangeEvent } from "react";

type Mode = "preparation" | "live";

type ModeSwitchProps = {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  disabled?: boolean;
};

export function ModeSwitch({ mode, onModeChange, disabled = false }: ModeSwitchProps) {
  const handleChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;
      const selected = event.target.value as Mode;
      onModeChange(selected);
    },
    [onModeChange, disabled]
  );

  return (
    <fieldset
      style={{
        border: "1px solid rgba(28, 35, 51, 0.1)",
        borderRadius: "999px",
        padding: "0.35rem",
        display: "inline-flex",
        alignItems: "center",
        gap: "0.35rem",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <legend style={{ fontSize: "0.8rem", padding: "0 0.5rem", color: "#5b6478" }}>Mode</legend>
      {(
        [
          { value: "preparation", label: "준비" },
          { value: "live", label: "실시간" }
        ] as const
      ).map(({ value, label }) => (
        <label
          key={value}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.4rem",
            padding: "0.25rem 0.75rem",
            borderRadius: "999px",
            background: mode === value ? "#1c2333" : "transparent",
            color: mode === value ? "#ffffff" : "#1c2333",
            cursor: disabled ? "not-allowed" : "pointer",
            fontWeight: 600
          }}
        >
          <input
            type="radio"
            name="mode-switch"
            value={value}
            checked={mode === value}
            onChange={handleChange}
            disabled={disabled}
            style={{ display: "none" }}
          />
          {label}
        </label>
      ))}
    </fieldset>
  );
}
