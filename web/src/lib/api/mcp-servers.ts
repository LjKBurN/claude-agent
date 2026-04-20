import { request } from "./client";
import type {
  MCPServerInfo,
  MCPServerList,
  CreateMCPServerRequest,
  UpdateMCPServerRequest,
  MCPServerStatusInfo,
} from "./types";

export function listMCPServers(signal?: AbortSignal) {
  return request<MCPServerList>("GET", "/api/mcp-servers", undefined, signal);
}

export function getMCPServer(id: string, signal?: AbortSignal) {
  return request<MCPServerInfo>("GET", `/api/mcp-servers/${id}`, undefined, signal);
}

export function createMCPServer(data: CreateMCPServerRequest) {
  return request<MCPServerInfo>("POST", "/api/mcp-servers", data);
}

export function updateMCPServer(id: string, data: UpdateMCPServerRequest) {
  return request<MCPServerInfo>("PUT", `/api/mcp-servers/${id}`, data);
}

export function deleteMCPServer(id: string) {
  return request<{ status: string; id: string }>("DELETE", `/api/mcp-servers/${id}`);
}

export function connectMCPServer(id: string) {
  return request<{ status: string; name: string }>("POST", `/api/mcp-servers/${id}/connect`);
}

export function disconnectMCPServer(id: string) {
  return request<{ status: string; name: string }>("POST", `/api/mcp-servers/${id}/disconnect`);
}

export function getMCPServerStatus(id: string, signal?: AbortSignal) {
  return request<MCPServerStatusInfo>(
    "GET",
    `/api/mcp-servers/${id}/status`,
    undefined,
    signal
  );
}
