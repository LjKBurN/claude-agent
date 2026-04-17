"use client";

import Link from "next/link";
import { Bot, Loader2, Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAgentConfigs } from "@/lib/hooks/use-agent-configs";
import { deleteAgentConfig } from "@/lib/api/agent-configs";
import { toast } from "sonner";
import { useState } from "react";

export default function AgentsPage() {
  const { configs, isLoading, mutate } = useAgentConfigs();
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleDelete(id: string, name: string) {
    if (!confirm(`确定要删除 Agent "${name}" 吗？`)) return;
    setDeleting(id);
    try {
      await deleteAgentConfig(id);
      toast.success(`已删除 "${name}"`);
      mutate();
    } catch (err) {
      toast.error(`删除失败: ${(err as Error).message}`);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          创建和管理自定义 Agent，配置工具、模型和行为
        </p>
        <Link href="/agents/new">
          <Button size="sm" className="gap-1.5">
            <Plus className="h-4 w-4" />
            新建 Agent
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      ) : configs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Bot className="mb-3 h-10 w-10" />
          <p className="text-sm">暂无自定义 Agent</p>
          <p className="text-xs">点击上方按钮创建一个</p>
        </div>
      ) : (
        <div className="space-y-3">
          {configs.map((agent) => (
            <Card key={agent.id} className="transition-colors hover:bg-accent/50">
              <CardContent className="flex items-center justify-between py-4">
                <Link href={`/agents/${agent.id}`} className="flex-1">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-lg">
                      {agent.avatar || <Bot className="h-4 w-4 text-primary" />}
                    </div>
                    <div>
                      <div className="text-sm font-medium">{agent.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {agent.description || `${agent.model_id}`}
                      </div>
                      <div className="mt-1 flex gap-1">
                        <Badge variant="outline" className="text-[10px]">
                          {agent.builtin_tools.length > 0
                            ? `${agent.builtin_tools.length} 工具`
                            : "全部工具"}
                        </Badge>
                        {agent.include_skills && (
                          <Badge variant="outline" className="text-[10px]">
                            Skills
                          </Badge>
                        )}
                        {agent.include_mcp && (
                          <Badge variant="outline" className="text-[10px]">
                            MCP
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
                <div className="flex gap-1">
                  <Link href={`/agents/${agent.id}`}>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    onClick={(e) => {
                      e.preventDefault();
                      handleDelete(agent.id, agent.name);
                    }}
                    disabled={deleting === agent.id}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
