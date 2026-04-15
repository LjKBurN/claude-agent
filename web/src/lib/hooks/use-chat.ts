"use client";

import { useCallback, useRef } from "react";
import { useChatStore } from "@/lib/store/chat-store";
import { sendMessageStream } from "@/lib/api/chat";
import { parseSSEStream } from "@/lib/sse/parser";

export function useChat() {
  const abortRef = useRef<AbortController | null>(null);

  const {
    sessionId,
    messages,
    isStreaming,
    streamingText,
    streamingToolCalls,
    streamingToolName,
    error,
    setSessionId,
    addUserMessage,
    appendStreamText,
    addToolStart,
    addToolEnd,
    finalizeStream,
    startStreaming,
    stopStreaming,
    setError,
    loadMessages,
    reset,
  } = useChatStore();

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      addUserMessage(text);
      startStreaming();

      const abort = new AbortController();
      abortRef.current = abort;

      try {
        const stream = await sendMessageStream(
          { message: text, session_id: sessionId },
          abort.signal,
        );

        await parseSSEStream(stream, (event) => {
          switch (event.type) {
            case "session_id":
              setSessionId(event.session_id);
              break;
            case "text":
              appendStreamText(event.content);
              break;
            case "tool_start":
              addToolStart(event.name);
              break;
            case "tool_end":
              addToolEnd({
                name: event.name,
                input: {},
                output: event.output,
              });
              break;
            case "skill_load":
              // skill loading indicator - handled in UI
              break;
            case "done":
              // Replace tool_calls with the complete list from done event
              break;
          }
        });

        finalizeStream();
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          stopStreaming();
        } else {
          const message = err instanceof Error ? err.message : "Unknown error";
          setError(message);
        }
      } finally {
        abortRef.current = null;
      }
    },
    [
      sessionId,
      isStreaming,
      addUserMessage,
      startStreaming,
      setSessionId,
      appendStreamText,
      addToolStart,
      addToolEnd,
      finalizeStream,
      stopStreaming,
      setError,
    ],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    sessionId,
    messages,
    isStreaming,
    streamingText,
    streamingToolCalls,
    streamingToolName,
    error,
    send,
    abort,
    loadMessages,
    reset,
    setSessionId,
  };
}
