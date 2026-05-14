"use client";

import { useEffect, useRef } from "react";
import type { DisplayMessage } from "@/lib/store/chat-store";
import type { ToolCall } from "@/lib/api/types";
import { MessageItem } from "./message-item";
import { MarkdownRenderer } from "./markdown-renderer";
import { StreamingText } from "./streaming-text";
import { ToolCallBlock } from "./tool-call-block";
import { EmptyState } from "./empty-state";
import { Bot, Loader2 } from "lucide-react";

interface MessageListProps {
  messages: DisplayMessage[];
  isStreaming: boolean;
  streamingText: string;
  streamingToolCalls: ToolCall[];
  streamingToolName: string | null;
  subAgentInfo: { task: string; status: "running" | "done" } | null;
}

export function MessageList({
  messages,
  isStreaming,
  streamingText,
  streamingToolCalls,
  streamingToolName,
  subAgentInfo,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, streamingToolCalls, streamingToolName]);

  if (messages.length === 0 && !isStreaming) {
    return <EmptyState />;
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}

      {/* Streaming state */}
      {isStreaming && (
        <div className="flex gap-3 px-4 py-4">
          <Bot className="h-7 w-7 shrink-0 text-muted-foreground p-1 rounded-full bg-muted" />

          <div className="flex-1 min-w-0 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              Claude
            </div>

            {streamingText && (
              <div className="max-w-none">
                <MarkdownRenderer content={streamingText} />
                <span className="inline-block h-4 w-0.5 animate-pulse bg-foreground ml-0.5 align-text-bottom" />
              </div>
            )}

            {/* Completed tool calls during streaming */}
            {streamingToolCalls.map((tc, i) => (
              <ToolCallBlock key={i} toolCall={tc} />
            ))}

            {/* Currently running tool */}
            {streamingToolName && (
              <ToolCallBlock
                toolCall={{ name: streamingToolName, input: {}, output: "" }}
                isRunning
                defaultOpen
                subAgentInfo={streamingToolName === "spawn_subagent" ? subAgentInfo : null}
              />
            )}

            {!streamingText && !streamingToolName && streamingToolCalls.length === 0 && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                正在思考...
              </div>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
