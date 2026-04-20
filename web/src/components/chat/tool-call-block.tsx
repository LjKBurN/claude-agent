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

/** 将 output 分离为文本部分和图片 data URL 部分。 */
function parseOutput(output: string): { textParts: string[]; imageParts: string[] } {
  const textParts: string[] = [];
  const imageParts: string[] = [];

  const lines = output.split("\n");
  for (const line of lines) {
    if (line.startsWith("data:image/") && line.includes(";base64,")) {
      imageParts.push(line);
    } else if (line.trim()) {
      textParts.push(line);
    }
  }

  return { textParts, imageParts };
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

  // 分离 output 中的文本和图片
  const { textParts, imageParts } = parseOutput(outputStr);

  const hasImages = imageParts.length > 0;
  // 有图片时默认展开
  const effectiveOpen = open || (hasImages && !defaultOpen ? false : open);

  return (
    <div className="my-2 rounded-lg border bg-card">
      {/* Header */}
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent/50"
        onClick={() => setOpen(!open)}
      >
        {effectiveOpen ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="font-medium">{toolCall.name}</span>
        {hasImages && (
          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">
            {imageParts.length} 张图片
          </span>
        )}
        {isRunning ? (
          <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-muted-foreground" />
        ) : (
          <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-green-500" />
        )}
      </button>

      {/* Body */}
      {effectiveOpen && (
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
          {textParts.length > 0 && (
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                Output
              </div>
              <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs">
                <code>{textParts.join("\n")}</code>
              </pre>
            </div>
          )}
          {imageParts.map((src, i) => (
            <div key={i} className="mt-2">
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                Screenshot{i > 0 ? ` ${i + 1}` : ""}
              </div>
              <img
                src={src}
                alt={`tool output ${i + 1}`}
                className="max-w-full rounded-md border"
                style={{ maxHeight: 400 }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
