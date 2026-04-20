"use client";

import { useState } from "react";
import {
  Loader2,
  Plus,
  Trash2,
  Plug,
  ChevronDown,
  ChevronRight,
  Pencil,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMCPServers } from "@/lib/hooks/use-mcp-servers";
import {
  createMCPServer,
  updateMCPServer,
  deleteMCPServer,
  connectMCPServer,
  disconnectMCPServer,
  getMCPServerStatus,
} from "@/lib/api/mcp-servers";
import { toast } from "sonner";
import { MCPServerForm } from "@/components/mcp/mcp-server-form";
import { MCPResourceViewer } from "@/components/mcp/mcp-resource-viewer";
import type { MCPServerInfo, CreateMCPServerRequest } from "@/lib/api/types";

export default function MCPPage() {
  const { servers, isLoading, mutate } = useMCPServers();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<MCPServerInfo | undefined>();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [operating, setOperating] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  // 记录已知的连接状态 { serverId: connected }
  const [connectMap, setConnectMap] = useState<Record<string, boolean>>({});

  async function refreshConnectStatus() {
    const map: Record<string, boolean> = {};
    await Promise.all(
      servers.map(async (s) => {
        try {
          const status = await getMCPServerStatus(s.id);
          map[s.id] = status.connected;
        } catch {
          map[s.id] = false;
        }
      })
    );
    setConnectMap(map);
  }

  async function handleCreate(data: CreateMCPServerRequest) {
    await createMCPServer(data);
    toast.success(`已添加 "${data.name}"`);
    mutate();
  }

  async function handleEdit(data: CreateMCPServerRequest) {
    if (!editing) return;
    await updateMCPServer(editing.id, data);
    toast.success(`已更新 "${data.name}"`);
    setEditing(undefined);
    mutate();
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`确定要删除 "${name}" 吗？`)) return;
    setDeleting(id);
    try {
      await deleteMCPServer(id);
      toast.success(`已删除 "${name}"`);
      mutate();
    } catch (err) {
      toast.error(`删除失败: ${(err as Error).message}`);
    } finally {
      setDeleting(null);
    }
  }

  async function handleToggleConnect(server: MCPServerInfo) {
    setOperating(server.id);
    try {
      const status = await getMCPServerStatus(server.id);
      if (status.connected) {
        await disconnectMCPServer(server.id);
        toast.success(`已断开 "${server.name}"`);
      } else {
        await connectMCPServer(server.id);
        toast.success(`已连接 "${server.name}"`);
      }
      setConnectMap((prev) => ({
        ...prev,
        [server.id]: !status.connected,
      }));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setOperating(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          管理 MCP Server 连接，配置工具扩展
        </p>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => {
            setEditing(undefined);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" />
          添加 Server
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      ) : servers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Plug className="mb-3 h-10 w-10" />
          <p className="text-sm">暂无 MCP Server</p>
          <p className="text-xs">点击上方按钮添加一个</p>
        </div>
      ) : (
        <div className="space-y-3">
          {servers.map((server) => {
            const connected = connectMap[server.id] ?? false;
            return (
              <Card key={server.id} className="transition-colors hover:bg-accent/50">
                <CardContent className="py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{server.name}</span>
                        <Badge variant="outline" className="text-[10px]">
                          {server.transport.toUpperCase()}
                        </Badge>
                        <Badge
                          variant={connected ? "default" : "secondary"}
                          className="text-[10px]"
                        >
                          {connected ? "已连接" : "未连接"}
                        </Badge>
                        {!server.enabled && (
                          <Badge variant="destructive" className="text-[10px]">
                            已禁用
                          </Badge>
                        )}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {server.description || (
                          server.transport === "stdio"
                            ? server.command +
                              (server.args?.length ? ` ${server.args.join(" ")}` : "")
                            : server.url
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => handleToggleConnect(server)}
                        disabled={operating === server.id}
                        title={connected ? "断开连接" : "连接"}
                      >
                        {operating === server.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : connected ? (
                          <Plug className="h-3.5 w-3.5 text-green-500" />
                        ) : (
                          <Plug className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => {
                          setEditing(server);
                          setFormOpen(true);
                        }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive"
                        onClick={(e) => {
                          e.preventDefault();
                          handleDelete(server.id, server.name);
                        }}
                        disabled={deleting === server.id}
                      >
                        {deleting === server.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() =>
                          setExpanded(expanded === server.id ? null : server.id)
                        }
                      >
                        {expanded === server.id ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>
                  {expanded === server.id && (
                    <div className="mt-3 border-t pt-3">
                      <MCPResourceViewer
                        serverId={server.id}
                        serverName={server.name}
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <MCPServerForm
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(undefined);
        }}
        initialData={editing}
        onSubmit={editing ? handleEdit : handleCreate}
      />
    </div>
  );
}
