"use client";

import { useState } from "react";
import useSWR from "swr";
import { Loader2, ChevronRight, ChevronDown, Wrench, FileText, MessageSquare } from "lucide-react";
import { getMCPServerStatus } from "@/lib/api/mcp-servers";
import type { MCPServerStatusInfo } from "@/lib/api/types";

export function MCPResourceViewer({
  serverId,
  serverName,
}: {
  serverId: string;
  serverName: string;
}) {
  const { data, error, isLoading } = useSWR<MCPServerStatusInfo>(
    `/api/mcp-servers/${serverId}/status`,
    () => getMCPServerStatus(serverId),
    { revalidateOnFocus: false }
  );

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        加载资源...
      </div>
    );
  }

  if (error || !data) {
    return <div className="py-1 text-xs text-destructive">加载失败</div>;
  }

  if (!data.connected) {
    return <div className="py-1 text-xs text-muted-foreground">未连接</div>;
  }

  const tools = data.tools ?? [];
  const resources = data.resources ?? [];
  const prompts = data.prompts ?? [];

  if (tools.length === 0 && resources.length === 0 && prompts.length === 0) {
    return <div className="py-1 text-xs text-muted-foreground">暂无资源</div>;
  }

  return (
    <div className="space-y-2">
      {tools.length > 0 && (
        <CollapsibleSection
          icon={<Wrench className="h-3 w-3" />}
          title={`Tools (${tools.length})`}
          items={tools.map((t) => ({
            name: t.name,
            description: t.description,
          }))}
        />
      )}
      {resources.length > 0 && (
        <CollapsibleSection
          icon={<FileText className="h-3 w-3" />}
          title={`Resources (${resources.length})`}
          items={resources.map((r) => ({
            name: r.name,
            description: r.uri,
          }))}
        />
      )}
      {prompts.length > 0 && (
        <CollapsibleSection
          icon={<MessageSquare className="h-3 w-3" />}
          title={`Prompts (${prompts.length})`}
          items={prompts.map((p) => ({
            name: p.name,
            description: p.description,
          }))}
        />
      )}
    </div>
  );
}

function CollapsibleSection({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  items: { name: string; description: string }[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        {icon}
        {title}
      </button>
      {open && (
        <div className="mt-1 ml-6 space-y-0.5">
          {items.map((item) => (
            <div key={item.name} className="text-xs">
              <span className="font-medium">{item.name}</span>
              {item.description && (
                <span className="ml-1 text-muted-foreground">
                  — {item.description}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
