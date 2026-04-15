"use client";

import { Bot } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 text-muted-foreground">
      <Bot className="h-12 w-12" />
      <div className="text-center">
        <h2 className="text-lg font-medium">开始新对话</h2>
        <p className="text-sm">发送消息与 Claude Agent 交互</p>
      </div>
    </div>
  );
}
