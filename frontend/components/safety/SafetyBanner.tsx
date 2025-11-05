"use client";

import { SafetyBannerState } from "../../hooks/useSafetyEnvelope";

type SafetyBannerProps = {
  envelope: SafetyBannerState;
};

const COLOR_MAP: Record<SafetyBannerState["level"], string> = {
  clear: "#1a936f",
  caution: "#f9a825",
  escalate: "#d64545"
};

export function SafetyBanner({ envelope }: SafetyBannerProps) {
  if (!envelope.shouldShow || envelope.level === "clear") {
    return null;
  }

  const accent = COLOR_MAP[envelope.level];

  return (
    <div
      aria-live="assertive"
      role="status"
      style={{
        borderRadius: "0.85rem",
        border: `1px solid ${accent}33`,
        background: `${envelope.level === "escalate" ? "#fff5f5" : "#fff9e3"}`,
        padding: "0.9rem 1.1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.4rem",
        marginBottom: "1rem"
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <span
          aria-hidden
          style={{
            width: "0.75rem",
            height: "0.75rem",
            borderRadius: "50%",
            background: accent,
            flexShrink: 0
          }}
        />
        <strong style={{ color: accent, fontSize: "0.95rem" }}>{envelope.headline}</strong>
      </div>
      <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: 1.45 }}>{envelope.body}</p>
      <p style={{ margin: 0, fontSize: "0.82rem", lineHeight: 1.4, color: "#404659" }}>{envelope.escalationCopy}</p>
    </div>
  );
}

