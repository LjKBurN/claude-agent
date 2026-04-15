import { request } from "./client";
import type { SessionList, MessageList } from "./types";

export function listSessions(params?: {
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
}) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const qs = searchParams.toString();
  return request<SessionList>(
    "GET",
    `/api/sessions${qs ? `?${qs}` : ""}`,
    undefined,
    params?.signal,
  );
}

export function getSessionMessages(
  sessionId: string,
  params?: { limit?: number; offset?: number; signal?: AbortSignal },
) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const qs = searchParams.toString();
  return request<MessageList>(
    "GET",
    `/api/sessions/${sessionId}/messages${qs ? `?${qs}` : ""}`,
    undefined,
    params?.signal,
  );
}

export function deleteSession(sessionId: string) {
  return request<void>("DELETE", `/api/sessions/${sessionId}`);
}
