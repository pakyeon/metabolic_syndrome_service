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
  const publicApiKey = process.env.NEXT_PUBLIC_COPILOTKIT_API_KEY ?? "";

  return (
    <html lang="en">
      <body>
        <CopilotKit publicApiKey={publicApiKey}>{children}</CopilotKit>
      </body>
    </html>
  );
}
