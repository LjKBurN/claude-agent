import { request, requestStream } from "./client";
import type { ChatRequest, ChatResponse } from "./types";

export function sendMessage(req: ChatRequest, signal?: AbortSignal) {
  return request<ChatResponse>("POST", "/api/chat", req, signal);
}

export function sendMessageStream(req: ChatRequest, signal?: AbortSignal) {
  return requestStream("/api/chat/stream", req, signal);
}
