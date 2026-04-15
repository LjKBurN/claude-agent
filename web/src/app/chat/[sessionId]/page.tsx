"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { ChatView } from "@/components/chat/chat-view";
import { useChatStore } from "@/lib/store/chat-store";
import { getSessionMessages } from "@/lib/api/sessions";

export default function SessionChatPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const { setSessionId, loadMessages, reset } = useChatStore();

  useEffect(() => {
    async function load() {
      reset();
      setSessionId(sessionId);
      try {
        const result = await getSessionMessages(sessionId, { limit: 100 });
        loadMessages(result.messages);
      } catch (err) {
        console.error("Failed to load session messages:", err);
      }
    }
    load();
  }, [sessionId, setSessionId, loadMessages, reset]);

  return <ChatView sessionId={sessionId} />;
}
