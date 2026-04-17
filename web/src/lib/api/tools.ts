import { request } from "./client";
import type { ToolsListResponse } from "./types";

export function listTools(signal?: AbortSignal) {
  return request<ToolsListResponse>("GET", "/api/tools", undefined, signal);
}
