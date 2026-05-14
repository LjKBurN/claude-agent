import type { ToolCall } from "@/lib/api/types";

export type SSEEvent =
  | { type: "session_id"; session_id: string }
  | { type: "text"; content: string }
  | { type: "tool_start"; name: string }
  | { type: "tool_end"; name: string; output: string }
  | { type: "skill_load"; name: string; message: string }
  | { type: "approval_needed"; message: string; tools: { name: string; input: Record<string, unknown> }[] }
  | { type: "sub_agent_start"; task: string; context?: string }
  | { type: "sub_agent_end"; task: string; result_length?: number; error?: string }
  | { type: "done"; tool_calls?: ToolCall[]; status?: string };

export async function parseSSEStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SSEEvent) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by \n\n
      const parts = buffer.split("\n\n");
      // Keep the last (potentially incomplete) part in the buffer
      buffer = parts.pop() || "";

      for (const part of parts) {
        const event = parseSSEEvent(part);
        if (event) {
          onEvent(event);
        }
      }
    }

    // Process any remaining data in buffer
    if (buffer.trim()) {
      const event = parseSSEEvent(buffer);
      if (event) {
        onEvent(event);
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSSEEvent(raw: string): SSEEvent | null {
  let eventType = "";
  let data = "";

  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      data = line.slice(6);
    }
  }

  if (!eventType || !data) return null;

  try {
    const parsed = JSON.parse(data);

    switch (eventType) {
      case "session_id":
        return {
          type: "session_id",
          session_id: parsed.session_id,
        };
      case "text":
        return { type: "text", content: parsed.content };
      case "tool_start":
        return { type: "tool_start", name: parsed.name };
      case "tool_end":
        return { type: "tool_end", name: parsed.name, output: parsed.output };
      case "skill_load":
        return {
          type: "skill_load",
          name: parsed.name,
          message: parsed.message,
        };
      case "approval_needed":
        return {
          type: "approval_needed",
          message: parsed.message || "",
          tools: parsed.tools || [],
        };
      case "sub_agent_start":
        return {
          type: "sub_agent_start",
          task: parsed.task || "",
          context: parsed.context || "",
        };
      case "sub_agent_end":
        return {
          type: "sub_agent_end",
          task: parsed.task || "",
          result_length: parsed.result_length,
          error: parsed.error,
        };
      case "done":
        return { type: "done", tool_calls: parsed.tool_calls, status: parsed.status };
      default:
        return null;
    }
  } catch {
    return null;
  }
}
