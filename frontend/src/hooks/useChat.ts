"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi } from "@/lib/api";
import type { Citation, Message, SSEEvent, StreamingMessage } from "@/lib/types";
import { useAppStore } from "@/store/appStore";

const PLACEHOLDER_ID = "__streaming__";

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<StreamingMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const triggerSeek = useAppStore((s) => s.triggerSeek);

  // ── Load history on session mount ─────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    chatApi
      .getMessages(sessionId)
      .then(({ data }) => setMessages(data as StreamingMessage[]))
      .catch(() => setMessages([]));
  }, [sessionId]);

  // ── Send a question and stream the answer ──────────────────────────────────
  const sendMessage = useCallback(
    async (question: string) => {
      if (!sessionId || isStreaming) return;

      const userMsg: StreamingMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: question,
        citations: null,
      };
      const assistantPlaceholder: StreamingMessage = {
        id: PLACEHOLDER_ID,
        role: "assistant",
        content: "",
        citations: null,
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
      setIsStreaming(true);
      setError(null);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const stream = await chatApi.streamMessage(sessionId, question);
        const reader = stream.getReader();
        let buffer = "";
        let fullContent = "";
        let finalCitations: Citation[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += value;
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event: SSEEvent = JSON.parse(line.slice(6));

              if (event.type === "token" && typeof event.data === "string") {
                fullContent += event.data;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === PLACEHOLDER_ID ? { ...m, content: fullContent } : m
                  )
                );
              } else if (event.type === "citations" && Array.isArray(event.data)) {
                finalCitations = event.data as Citation[];
              } else if (event.type === "done") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === PLACEHOLDER_ID
                      ? {
                          ...m,
                          id: `assistant-${Date.now()}`,
                          content: fullContent,
                          citations: finalCitations,
                          isStreaming: false,
                        }
                      : m
                  )
                );
              } else if (event.type === "error") {
                setError(typeof event.data === "string" ? event.data : "Stream error");
              }
            } catch {
              // Ignore malformed SSE lines
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError("Connection lost. Please try again.");
          setMessages((prev) => prev.filter((m) => m.id !== PLACEHOLDER_ID));
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [sessionId, isStreaming]
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const jumpToTimestamp = useCallback(
    (seconds: number) => {
      triggerSeek(seconds);
    },
    [triggerSeek]
  );

  return { messages, isStreaming, error, sendMessage, stopStream, jumpToTimestamp };
}
