"use client";

import Link from "next/link";
import { MessageSquare, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useChannelSessions } from "@/lib/hooks/use-channels";
import type { ChannelSessionInfo } from "@/lib/api/types";

interface SessionListProps {
  channelId: string;
}

function isGroupChat(imId: string): boolean {
  return imId.includes("@chatroom") || imId.includes("@im.wechat");
}

function formatImId(imId: string): string {
  if (isGroupChat(imId)) {
    const parts = imId.split("@");
    return `群聊: ${parts[0]}@${parts.slice(1).join("@")}`;
  }
  return `私聊: ${imId}`;
}

function SessionItem({ session }: { session: ChannelSessionInfo }) {
  const group = isGroupChat(session.im_conversation_id);
  const Icon = group ? Users : MessageSquare;

  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2.5">
      <div className="flex items-center gap-2 min-w-0">
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <div className="text-sm truncate">
            {formatImId(session.im_conversation_id)}
          </div>
          <div className="text-xs text-muted-foreground font-mono">
            {session.agent_session_id.slice(0, 12)}...
          </div>
        </div>
      </div>
      <Link href={`/chat/${session.agent_session_id}`}>
        <Button variant="ghost" size="sm">
          查看对话
        </Button>
      </Link>
    </div>
  );
}

export function ChannelSessionList({ channelId }: SessionListProps) {
  const { sessions, isLoading } = useChannelSessions(channelId);

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium">关联会话 ({sessions.length})</h3>
      {sessions.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无关联会话</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <SessionItem key={s.id} session={s} />
          ))}
        </div>
      )}
    </div>
  );
}
