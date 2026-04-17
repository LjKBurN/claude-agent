"use client";

import { useState } from "react";
import { Plus, Sparkles, ChevronRight, ChevronDown, Radio } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "./theme-toggle";
import { SidebarSessions } from "./sidebar-sessions";
import { AgentSelector } from "./agent-selector";
import { SkillsPanel } from "@/components/chat/skills-panel";

export function Sidebar() {
  const [skillsOpen, setSkillsOpen] = useState(false);

  return (
    <div className="flex h-full w-64 flex-col border-r bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <h1 className="text-sm font-semibold">Claude Agent</h1>
        <ThemeToggle />
      </div>

      <Separator />

      {/* New Chat */}
      <div className="p-2">
        <Link href="/chat">
          <Button variant="outline" className="w-full justify-start gap-2">
            <Plus className="h-4 w-4" />
            新对话
          </Button>
        </Link>
      </div>

      {/* Agent Selector */}
      <AgentSelector />

      <Separator />

      {/* Sessions */}
      <ScrollArea className="flex-1">
        <SidebarSessions />
      </ScrollArea>

      <Separator />

      {/* Skills section */}
      <div>
        <button
          className="flex w-full items-center gap-2 px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
          onClick={() => setSkillsOpen(!skillsOpen)}
        >
          {skillsOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          <Sparkles className="h-4 w-4" />
          Skills
        </button>
        {skillsOpen && (
          <ScrollArea className="max-h-64">
            <SkillsPanel />
          </ScrollArea>
        )}
      </div>

      <Separator />

      {/* Channel management */}
      <div className="p-2">
        <Link href="/channels">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-muted-foreground"
          >
            <Radio className="h-4 w-4" />
            Channel 管理
          </Button>
        </Link>
      </div>
    </div>
  );
}
