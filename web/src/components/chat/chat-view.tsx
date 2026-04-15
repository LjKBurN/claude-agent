"use client";

import { useChat } from "@/lib/hooks/use-chat";
import { MessageList } from "./message-list";
import { MessageInput } from "./message-input";
import { AlertCircle } from "lucide-react";

interface ChatViewProps {
  sessionId?: string;
}

export function ChatView({ sessionId }: ChatViewProps) {
  const chat = useChat();

  // If we have a sessionId prop, set it
  // (handled by the page component via loadMessages)

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Error bar */}
      {chat.error && (
        <div className="flex items-center gap-2 border-b bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {chat.error}
        </div>
      )}

      <MessageList
        messages={chat.messages}
        isStreaming={chat.isStreaming}
        streamingText={chat.streamingText}
        streamingToolCalls={chat.streamingToolCalls}
        streamingToolName={chat.streamingToolName}
      />

      <MessageInput
        onSend={chat.send}
        onAbort={chat.abort}
        isStreaming={chat.isStreaming}
      />
    </div>
  );
}
