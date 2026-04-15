"use client";

import { User, Bot } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { DisplayMessage } from "@/lib/store/chat-store";
import { ToolCallBlock } from "./tool-call-block";
import { MarkdownRenderer } from "./markdown-renderer";
import { cn } from "@/lib/utils";

interface MessageItemProps {
  message: DisplayMessage;
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 px-4 py-4", isUser && "flex-row-reverse")}>
      <Avatar className="h-7 w-7 shrink-0">
        <AvatarFallback
          className={cn(
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          )}
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "min-w-0 space-y-2 max-w-[80%]",
          isUser ? "items-end" : "flex-1"
        )}
      >
        <div
          className={cn(
            "text-xs font-medium text-muted-foreground",
            isUser && "text-right"
          )}
        >
          {isUser ? "你" : "Claude"}
        </div>

        {/* User message: right-aligned bubble */}
        {isUser ? (
          <div className="rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-2.5 text-sm leading-7 break-words whitespace-pre-wrap">
            {message.content}
          </div>
        ) : (
          /* Assistant message: Markdown rendering */
          <>
            {message.content && (
              <MarkdownRenderer content={message.content} />
            )}
            {/* Tool calls */}
            {message.toolCalls.length > 0 && (
              <div className="space-y-1">
                {message.toolCalls.map((tc, i) => (
                  <ToolCallBlock key={i} toolCall={tc} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
