"use client";

import { cn } from "@/lib/utils";

interface StreamingTextProps {
  text: string;
  className?: string;
}

export function StreamingText({ text, className }: StreamingTextProps) {
  if (!text) return null;

  return (
    <span className={cn(className)}>
      {text}
      <span className="inline-block h-4 w-0.5 animate-pulse bg-foreground ml-0.5 align-text-bottom" />
    </span>
  );
}
