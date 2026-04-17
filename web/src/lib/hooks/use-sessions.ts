"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { listSessions, deleteSession } from "@/lib/api/sessions";
import type { SessionInfo } from "@/lib/api/types";

export function useSessions() {
  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWR<{ sessions: SessionInfo[]; total: number }>(
    "/api/sessions",
    () => listSessions({ limit: 30 }),
    { revalidateOnFocus: false },
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteSession(id);
      mutate();
    },
    [mutate],
  );

  return {
    sessions: data?.sessions ?? [],
    total: data?.total ?? 0,
    error,
    isLoading,
    refresh: mutate,
    remove,
  };
}
