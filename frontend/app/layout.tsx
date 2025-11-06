import type { Metadata } from "next";
import { ReactNode } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Metabolic Syndrome Counselor Assistant",
  description: "CopilotKit-powered counselor interface for preparation and live sessions."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const publicApiKey = process.env.NEXT_PUBLIC_COPILOTKIT_API_KEY?.trim();
  const runtimeUrl =
    process.env.NEXT_PUBLIC_COPILOTKIT_RUNTIME_URL?.trim() ||
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim() ||
    "http://localhost:8000";

  const copilotProps = {
    runtimeUrl,
    ...(publicApiKey ? { publicApiKey } : {})
  };

  return (
    <html lang="en">
      <body>
        <CopilotKit {...copilotProps}>{children}</CopilotKit>
      </body>
    </html>
  );
}
