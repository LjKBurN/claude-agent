"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { MCPServerInfo, CreateMCPServerRequest } from "@/lib/api/types";

interface MCPServerFormProps {
  initialData?: MCPServerInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: CreateMCPServerRequest) => Promise<void>;
}

export function MCPServerForm({
  initialData,
  open,
  onOpenChange,
  onSubmit,
}: MCPServerFormProps) {
  const [name, setName] = useState(initialData?.name ?? "");
  const [transport, setTransport] = useState<"stdio" | "http">(
    initialData?.transport ?? "stdio"
  );
  const [command, setCommand] = useState(initialData?.command ?? "");
  const [args, setArgs] = useState(initialData?.args?.join(" ") ?? "");
  const [env, setEnv] = useState<{ key: string; value: string }[]>(
    initialData?.env
      ? Object.entries(initialData.env).map(([key, value]) => ({ key, value }))
      : []
  );
  const [url, setUrl] = useState(initialData?.url ?? "");
  const [headers, setHeaders] = useState<{ key: string; value: string }[]>(
    initialData?.headers
      ? Object.entries(initialData.headers).map(([key, value]) => ({ key, value }))
      : []
  );
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    if (transport === "stdio" && !command.trim()) return;
    if (transport === "http" && !url.trim()) return;

    setSubmitting(true);
    try {
      const data: CreateMCPServerRequest = {
        name: name.trim(),
        transport,
        description: description.trim(),
        ...(transport === "stdio"
          ? {
              command: command.trim(),
              args: args.trim() ? args.trim().split(/\s+/) : [],
              env: Object.fromEntries(
                env.filter((e) => e.key.trim()).map((e) => [e.key.trim(), e.value])
              ),
            }
          : {
              url: url.trim(),
              headers: Object.fromEntries(
                headers.filter((h) => h.key.trim()).map((h) => [h.key.trim(), h.value])
              ),
            }),
      };
      await onSubmit(data);
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">
            {initialData ? "编辑 MCP Server" : "添加 MCP Server"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">名称 *</label>
            <input
              className={inputClass}
              placeholder="例如：playwright"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!!initialData}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">传输类型</label>
            <div className="flex gap-2">
              {(["stdio", "http"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                    transport === t
                      ? "border-primary bg-primary/10"
                      : "border-input hover:bg-accent"
                  }`}
                  onClick={() => setTransport(t)}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {transport === "stdio" ? (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">Command *</label>
                <input
                  className={inputClass}
                  placeholder="例如：npx"
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Args</label>
                <input
                  className={inputClass}
                  placeholder="以空格分隔，例如：-y @playwright/mcp@latest"
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  环境变量
                  <span className="ml-1 text-xs font-normal text-muted-foreground">
                    支持 $&#123;VAR&#125; 语法
                  </span>
                </label>
                <KVEditor items={env} onChange={setEnv} />
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">URL *</label>
                <input
                  className={inputClass}
                  placeholder="例如：http://localhost:8080"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Headers</label>
                <KVEditor items={headers} onChange={setHeaders} />
              </div>
            </>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">描述</label>
            <input
              className={inputClass}
              placeholder="MCP Server 的用途说明"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={
                submitting ||
                !name.trim() ||
                (transport === "stdio" && !command.trim()) ||
                (transport === "http" && !url.trim())
              }
            >
              {initialData ? "保存" : "添加"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function KVEditor({
  items,
  onChange,
}: {
  items: { key: string; value: string }[];
  onChange: (items: { key: string; value: string }[]) => void;
}) {
  const inputClass =
    "flex h-7 w-full rounded-md border border-input bg-transparent px-2 py-0.5 text-xs";

  return (
    <div className="space-y-1.5">
      {items.map((item, i) => (
        <div key={i} className="flex gap-1.5">
          <input
            className={inputClass}
            placeholder="Key"
            value={item.key}
            onChange={(e) => {
              const next = [...items];
              next[i] = { ...next[i], key: e.target.value };
              onChange(next);
            }}
          />
          <input
            className={inputClass}
            placeholder="Value"
            value={item.value}
            onChange={(e) => {
              const next = [...items];
              next[i] = { ...next[i], value: e.target.value };
              onChange(next);
            }}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-1.5 text-xs text-destructive"
            onClick={() => onChange(items.filter((_, idx) => idx !== i))}
          >
            x
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 text-xs"
        onClick={() => onChange([...items, { key: "", value: "" }])}
      >
        + 添加
      </Button>
    </div>
  );
}
