"use client";

import { useCallback } from "react";
import useSWR from "swr";
import {
  listAgentConfigs,
  getAgentConfig as getAgentConfigApi,
} from "@/lib/api/agent-configs";
import type { AgentConfigInfo } from "@/lib/api/types";

export function useAgentConfigs() {
  const { data, error, isLoading, mutate } = useSWR(
    "/api/agent-configs",
    () => listAgentConfigs(),
    { revalidateOnFocus: false },
  );

  return {
    configs: data?.configs ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate,
  };
}

export function useAgentConfig(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<AgentConfigInfo>(
    id ? `/api/agent-configs/${id}` : null,
    () => getAgentConfigApi(id!),
  );

  return {
    config: data ?? null,
    isLoading,
    error,
    mutate,
  };
}
