"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useSessions } from "@/lib/hooks/use-sessions";
import { useState } from "react";

export function SidebarSessions() {
  const { sessions, isLoading, remove } = useSessions();
  const pathname = usePathname();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-1 px-2">
      <div className="px-2 py-1 text-xs font-medium text-muted-foreground">
        会话记录
      </div>
      {isLoading ? (
        <div className="space-y-2 px-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : sessions.length === 0 ? (
        <div className="px-2 py-4 text-center text-xs text-muted-foreground">
          暂无会话
        </div>
      ) : (
        <ScrollArea className="max-h-[calc(100vh-280px)]">
          <div className="space-y-0.5">
            {sessions.map((session) => {
              const isActive = pathname === `/chat/${session.id}`;
              return (
                <div
                  key={session.id}
                  className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  }`}
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                  <Link
                    href={`/chat/${session.id}`}
                    className="flex-1 truncate"
                  >
                    {session.id.slice(0, 8)}...
                    <span className="ml-2 text-xs opacity-50">
                      {session.message_count}条消息
                    </span>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.preventDefault();
                      setDeleteId(session.id);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                  <Dialog
                    open={deleteId === session.id}
                    onOpenChange={(open) => !open && setDeleteId(null)}
                  >
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>删除会话</DialogTitle>
                        <DialogDescription>
                          确定要删除该会话吗？此操作不可撤销。
                        </DialogDescription>
                      </DialogHeader>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setDeleteId(null)}
                        >
                          取消
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={async () => {
                            await remove(session.id);
                            setDeleteId(null);
                            if (isActive) {
                              window.location.href = "/chat";
                            }
                          }}
                        >
                          删除
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
