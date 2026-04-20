"use client";

import useSWR from "swr";
import { listMCPServers } from "@/lib/api/mcp-servers";

export function useMCPServers() {
  const { data, error, isLoading, mutate } = useSWR(
    "/api/mcp-servers",
    () => listMCPServers(),
    { revalidateOnFocus: false }
  );

  return {
    servers: data?.servers ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate,
  };
}
