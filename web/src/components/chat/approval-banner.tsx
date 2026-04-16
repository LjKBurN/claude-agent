"use client";

import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ApprovalBannerProps {
  tools: { name: string; input: Record<string, unknown> }[];
  onApprove: () => void;
  onReject: () => void;
}

function formatToolInput(tool: { name: string; input: Record<string, unknown> }): string {
  const inputStr = Object.entries(tool.input)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return `\`${tool.name}\`(${inputStr || "..."})`;
}

export function ApprovalBanner({ tools, onApprove, onReject }: ApprovalBannerProps) {
  return (
    <div className="border-t bg-amber-50 dark:bg-amber-950/30 px-4 py-3">
      <div className="flex items-start gap-2 mb-3">
        <ShieldAlert className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-amber-800 dark:text-amber-300">
            需要确认执行以下操作：
          </div>
          <div className="mt-1 space-y-1">
            {tools.map((tool, i) => (
              <div key={i} className="text-sm text-amber-700 dark:text-amber-400 font-mono">
                {formatToolInput(tool)}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <Button variant="outline" size="sm" onClick={onReject}>
          拒绝
        </Button>
        <Button size="sm" onClick={onApprove}>
          确认执行
        </Button>
      </div>
    </div>
  );
}
