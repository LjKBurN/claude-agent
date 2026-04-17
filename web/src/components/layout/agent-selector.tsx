"use client";

import { Bot, ChevronDown, Settings } from "lucide-react";
import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { useAgentConfigs } from "@/lib/hooks/use-agent-configs";
import { useChatStore } from "@/lib/store/chat-store";

export function AgentSelector() {
  const { configs, isLoading } = useAgentConfigs();
  const currentAgentId = useChatStore((s) => s.currentAgentId);
  const setCurrentAgentId = useChatStore((s) => s.setCurrentAgentId);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const currentConfig = configs.find((c) => c.id === currentAgentId);

  // 点击外部关闭
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative px-2 pb-1">
      <button
        className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm transition-colors hover:bg-accent"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <span className="text-base">
            {currentConfig?.avatar || <Bot className="h-3.5 w-3.5 text-muted-foreground" />}
          </span>
          <span className="truncate">
            {currentConfig?.name || "默认 Agent"}
          </span>
        </div>
        <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute left-2 right-2 top-full z-50 mt-1 rounded-md border bg-popover p-1 shadow-md">
          {/* 默认选项 */}
          <button
            className={`flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm transition-colors hover:bg-accent ${
              !currentAgentId ? "bg-accent" : ""
            }`}
            onClick={() => {
              setCurrentAgentId(null);
              setOpen(false);
            }}
          >
            <Bot className="h-3.5 w-3.5" />
            默认 Agent (全部工具)
          </button>

          {/* Agent 列表 */}
          {!isLoading && configs.map((config) => (
            <button
              key={config.id}
              className={`flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm transition-colors hover:bg-accent ${
                currentAgentId === config.id ? "bg-accent" : ""
              }`}
              onClick={() => {
                setCurrentAgentId(config.id);
                setOpen(false);
              }}
            >
              <span className="text-sm">{config.avatar || <Bot className="h-3.5 w-3.5" />}</span>
              <span className="truncate">{config.name}</span>
            </button>
          ))}

          {/* 管理入口 */}
          <div className="mt-1 border-t pt-1">
            <Link
              href="/agents"
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              onClick={() => setOpen(false)}
            >
              <Settings className="h-3.5 w-3.5" />
              管理 Agents
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
