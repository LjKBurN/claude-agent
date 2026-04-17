import { request } from "./client";
import type {
  AgentConfigInfo,
  AgentConfigList,
  CreateAgentConfigRequest,
  UpdateAgentConfigRequest,
} from "./types";

export function listAgentConfigs(signal?: AbortSignal) {
  return request<AgentConfigList>("GET", "/api/agent-configs", undefined, signal);
}

export function getAgentConfig(id: string, signal?: AbortSignal) {
  return request<AgentConfigInfo>("GET", `/api/agent-configs/${id}`, undefined, signal);
}

export function createAgentConfig(data: CreateAgentConfigRequest) {
  return request<AgentConfigInfo>("POST", "/api/agent-configs", data);
}

export function updateAgentConfig(id: string, data: UpdateAgentConfigRequest) {
  return request<AgentConfigInfo>("PUT", `/api/agent-configs/${id}`, data);
}

export function deleteAgentConfig(id: string) {
  return request<{ status: string; id: string }>("DELETE", `/api/agent-configs/${id}`);
}
