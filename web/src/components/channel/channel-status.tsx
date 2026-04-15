"use client";

import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { startChannel, stopChannel } from "@/lib/api/channels";
import { toast } from "sonner";

interface ChannelStatusProps {
  channelId: string;
  configured: boolean;
  running: boolean;
  onStatusChange: () => void;
}

export function ChannelStatus({
  channelId,
  configured,
  running,
  onStatusChange,
}: ChannelStatusProps) {
  async function handleToggle() {
    try {
      if (running) {
        await stopChannel(channelId);
        toast.success("Channel 已停止");
      } else {
        await startChannel(channelId);
        toast.success("Channel 已启动");
      }
      onStatusChange();
    } catch (err) {
      toast.error(`操作失败: ${(err as Error).message}`);
    }
  }

  const statusText = running
    ? "● 运行中"
    : configured
      ? "○ 已配置"
      : "○ 未配置";

  return (
    <div className="flex items-center gap-3">
      <Badge variant={running ? "default" : "secondary"}>
        {statusText}
      </Badge>
      <Button
        variant={running ? "destructive" : "default"}
        size="sm"
        onClick={handleToggle}
        className="gap-1.5"
        disabled={!configured || running === undefined}
      >
        {running ? (
          <>
            <Square className="h-3.5 w-3.5" />
            停止
          </>
        ) : (
          <>
            <Play className="h-3.5 w-3.5" />
            启动
          </>
        )}
      </Button>
    </div>
  );
}
