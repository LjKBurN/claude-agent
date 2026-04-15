"use client";

import { useEffect } from "react";
import { ChatView } from "@/components/chat/chat-view";
import { useChatStore } from "@/lib/store/chat-store";

export default function ChatPage() {
  const reset = useChatStore((s) => s.reset);

  useEffect(() => {
    reset();
  }, [reset]);

  return <ChatView />;
}
