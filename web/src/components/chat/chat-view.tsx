"use client";

import { useChat } from "@/lib/hooks/use-chat";
import { MessageList } from "./message-list";
import { MessageInput } from "./message-input";
import { ApprovalBanner } from "./approval-banner";
import { AlertCircle, Bot } from "lucide-react";
import { useAgentConfigs } from "@/lib/hooks/use-agent-configs";

interface ChatViewProps {
  sessionId?: string;
}

export function ChatView({ sessionId }: ChatViewProps) {
  const chat = useChat();
  const { configs } = useAgentConfigs();
  const currentAgent = configs.find((c) => c.id === chat.currentAgentId);

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Current Agent indicator */}
      {currentAgent && (
        <div className="flex items-center gap-2 border-b bg-muted/30 px-4 py-1.5 text-xs text-muted-foreground">
          <span>{currentAgent.avatar || <Bot className="h-3 w-3" />}</span>
          <span>{currentAgent.name}</span>
          {currentAgent.builtin_tools.length > 0 && (
            <span className="text-muted-foreground/60">
              ({currentAgent.builtin_tools.length} 工具)
            </span>
          )}
        </div>
      )}

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
        subAgentInfo={chat.subAgentInfo}
      />

      {/* Approval banner */}
      {chat.needsApproval && chat.approvalTools.length > 0 && (
        <ApprovalBanner tools={chat.approvalTools} onApprove={() => chat.send("确认")} onReject={() => chat.send("取消执行")} />
      )}

      <MessageInput
        onSend={chat.send}
        onAbort={chat.abort}
        isStreaming={chat.isStreaming}
        disabled={chat.needsApproval}
      />
    </div>
  );
}
