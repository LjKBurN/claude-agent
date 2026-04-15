"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  Terminal,
  FileText,
  Globe,
  Wrench,
  Puzzle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolCall } from "@/lib/api/types";

interface ToolCallBlockProps {
  toolCall: ToolCall;
  isRunning?: boolean;
  defaultOpen?: boolean;
}

function getToolIcon(name: string) {
  if (name === "bash") return Terminal;
  if (name.startsWith("read_") || name.startsWith("write_") || name.startsWith("edit_") || name === "list_dir") return FileText;
  if (name.startsWith("http")) return Globe;
  if (name === "Skill") return Wrench;
  return Puzzle;
}

export function ToolCallBlock({
  toolCall,
  isRunning = false,
  defaultOpen = false,
}: ToolCallBlockProps) {
  const [open, setOpen] = useState(defaultOpen);
  const Icon = getToolIcon(toolCall.name);

  const inputStr = JSON.stringify(toolCall.input, null, 2);
  const outputStr = toolCall.output;
  const isLongOutput = outputStr.length > 500;

  return (
    <div className="my-2 rounded-lg border bg-card">
      {/* Header */}
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent/50"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="font-medium">{toolCall.name}</span>
        {isRunning ? (
          <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-muted-foreground" />
        ) : (
          <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-green-500" />
        )}
      </button>

      {/* Body */}
      {open && (
        <div className="border-t px-3 py-2 text-sm">
          {inputStr !== "{}" && (
            <div className="mb-2">
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                Input
              </div>
              <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs">
                <code>{inputStr}</code>
              </pre>
            </div>
          )}
          {outputStr && (
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                Output
              </div>
              <pre
                className={cn(
                  "overflow-x-auto rounded-md bg-muted p-2 text-xs",
                  isLongOutput && !open && "max-h-32",
                )}
              >
                <code>{outputStr}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
