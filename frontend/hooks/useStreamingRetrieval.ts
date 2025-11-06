"use client";

import { useCallback, useState } from "react";

export type AGUIMessage = {
  role: "reasoning" | "action" | "observation";
  title: string;
  content: string;
};

export type StreamEvent =
  | { type: "node_update"; node: string; data: any }
  | { type: "complete"; total_duration: number }
  | { type: "error"; message: string };

export type StreamingState = {
  isStreaming: boolean;
  messages: AGUIMessage[];
  answer: string;
  citations: any[];  // Changed from string[] to any[] to support structured citation objects from backend
  safety: any;
  error: string | null;
};

export function useStreamingRetrieval(backendUrl: string) {
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    messages: [],
    answer: "",
    citations: [],
    safety: null,
    error: null,
  });

  const streamQuestion = useCallback(
    async (question: string, context?: string) => {
      setState({
        isStreaming: true,
        messages: [],
        answer: "",
        citations: [],
        safety: null,
        error: null,
      });

      try {
        const response = await fetch(`${backendUrl}/v1/retrieve/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, context }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error("Response body is not readable");
        }

        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;

            const data = line.slice(6);
            if (!data.trim()) continue;

            try {
              const event: StreamEvent = JSON.parse(data);

              if (event.type === "node_update") {
                // Extract observations from node update
                const nodeData = event.data;
                const observations = nodeData.observations || [];

                // Convert observations to AG-UI messages
                const newMessages: AGUIMessage[] = [];
                for (const obs of observations) {
                  if (typeof obs === "object" && obs.role) {
                    newMessages.push({
                      role: obs.role as "reasoning" | "action" | "observation",
                      title: obs.title || "",
                      content: obs.content || "",
                    });
                  }
                }

                setState((prev) => ({
                  ...prev,
                  messages: [...prev.messages, ...newMessages],
                  answer: nodeData.answer || prev.answer,
                  citations: nodeData.citations || prev.citations,
                  safety: nodeData.safety || prev.safety,
                }));
              } else if (event.type === "complete") {
                setState((prev) => ({
                  ...prev,
                  isStreaming: false,
                }));
              } else if (event.type === "error") {
                setState((prev) => ({
                  ...prev,
                  isStreaming: false,
                  error: event.message,
                }));
              }
            } catch (parseError) {
              console.error("Failed to parse SSE data:", parseError);
            }
          }
        }
      } catch (error) {
        console.error("Streaming error:", error);
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: error instanceof Error ? error.message : "Unknown error",
        }));
      }
    },
    [backendUrl]
  );

  return {
    ...state,
    streamQuestion,
  };
}
