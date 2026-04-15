"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Smartphone, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useChannels } from "@/lib/hooks/use-channels";
import { createChannel } from "@/lib/api/channels";
import { toast } from "sonner";

export default function ChannelsPage() {
  const { channels, isLoading, refresh } = useChannels();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  async function handleCreate() {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await createChannel({ name: name.trim(), platform: "wechat" });
      toast.success("Channel 创建成功");
      setDialogOpen(false);
      setName("");
      refresh();
    } catch (err) {
      toast.error(`创建失败: ${(err as Error).message}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          管理 IM Channel，连接微信等平台
        </p>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger
            render={
              <Button size="sm" className="gap-1.5" />
            }
          >
            <Plus className="h-4 w-4" />
            添加 Channel
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>创建 Channel</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">名称</label>
                <input
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="例如：我的微信 Bot"
                  value={name}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setName(e.target.value)
                  }
                  onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) =>
                    e.key === "Enter" && handleCreate()
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">平台</label>
                <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground">
                  <Smartphone className="h-4 w-4" />
                  微信 (WeChat)
                </div>
              </div>
              <Button
                className="w-full"
                onClick={handleCreate}
                disabled={creating || !name.trim()}
              >
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                创建
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      ) : channels.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Smartphone className="mb-3 h-10 w-10" />
          <p className="text-sm">暂无 Channel</p>
          <p className="text-xs">点击上方按钮添加一个</p>
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map((ch) => (
            <Link key={ch.id} href={`/channels/${ch.id}`}>
              <Card className="transition-colors hover:bg-accent/50">
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    <Smartphone className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-medium">{ch.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {ch.platform === "wechat" ? "微信" : ch.platform}
                      </div>
                    </div>
                  </div>
                  <Badge variant={ch.running ? "default" : "secondary"}>
                    {ch.running ? "运行中" : ch.configured ? "已配置" : "未配置"}
                  </Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
