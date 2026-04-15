"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Smartphone, Trash2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ChannelStatus } from "@/components/channel/channel-status";
import { QRLogin } from "@/components/channel/qr-login";
import { SenderWhitelist } from "@/components/channel/sender-whitelist";
import { ChannelSessionList } from "@/components/channel/session-list";
import { useChannel } from "@/lib/hooks/use-channels";
import { deleteChannel, startChannel } from "@/lib/api/channels";
import { toast } from "sonner";

export default function ChannelDetailPage() {
  const { channelId } = useParams<{ channelId: string }>();
  const router = useRouter();
  const { channel, isLoading, refresh } = useChannel(channelId);

  async function handleLoginSuccess() {
    try {
      await startChannel(channelId);
      toast.success("微信登录成功，Channel 已启动");
    } catch (err) {
      toast.warning(`登录成功但启动失败: ${(err as Error).message}`);
    }
    refresh();
  }

  async function handleDelete() {
    if (!confirm("确定要删除此 Channel 吗？此操作不可恢复。")) return;
    try {
      await deleteChannel(channelId);
      toast.success("Channel 已删除");
      router.push("/channels");
    } catch (err) {
      toast.error(`删除失败: ${(err as Error).message}`);
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-6">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!channel) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-sm">Channel 不存在</p>
        <Link href="/channels">
          <Button variant="link" className="mt-2">
            返回列表
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/channels">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Smartphone className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">{channel.name}</h2>
        </div>
      </div>

      {/* Connection Status */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium">连接状态</h3>
        <ChannelStatus
          channelId={channel.id}
          configured={channel.configured}
          running={channel.running}
          onStatusChange={refresh}
        />
      </div>

      <Separator />

      {/* WeChat Login (only show if not configured) */}
      {!channel.configured && channel.platform === "wechat" && (
        <>
          <QRLogin channelId={channel.id} onLoginSuccess={handleLoginSuccess} />
          <Separator />
        </>
      )}

      {/* Whitelist */}
      <SenderWhitelist
        channelId={channel.id}
        senders={channel.allowed_senders ?? []}
        onChange={refresh}
      />

      <Separator />

      {/* Related Sessions */}
      <ChannelSessionList channelId={channel.id} />

      <Separator />

      {/* Danger Zone */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-destructive">危险操作</h3>
        <Button variant="destructive" size="sm" onClick={handleDelete}>
          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
          删除此 Channel
        </Button>
      </div>
    </div>
  );
}
