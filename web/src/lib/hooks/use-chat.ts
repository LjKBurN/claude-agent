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
    needsApproval,
    approvalTools,
    currentAgentId,
    setSessionId,
    setCurrentAgentId,
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
    setApproval,
    clearApproval,
  } = useChatStore();

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      // 如果在审批状态，清除审批
      if (needsApproval) {
        clearApproval();
      }

      addUserMessage(text);
      startStreaming();

      const abort = new AbortController();
      abortRef.current = abort;

      try {
        const stream = await sendMessageStream(
          { message: text, session_id: sessionId, agent_config_id: currentAgentId },
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
              break;
            case "approval_needed":
              setApproval(event.tools);
              break;
            case "done":
              break;
          }
        });

        // 如果不是 approval 状态，正常 finalize
        if (!useChatStore.getState().needsApproval) {
          finalizeStream();
        }
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
      needsApproval,
      currentAgentId,
      addUserMessage,
      startStreaming,
      setSessionId,
      appendStreamText,
      addToolStart,
      addToolEnd,
      setApproval,
      finalizeStream,
      stopStreaming,
      setError,
      clearApproval,
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
    needsApproval,
    approvalTools,
    currentAgentId,
    send,
    abort,
    loadMessages,
    reset,
    setSessionId,
    setCurrentAgentId,
  };
}
