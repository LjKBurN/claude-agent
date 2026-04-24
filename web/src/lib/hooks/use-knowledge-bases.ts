"use client";

import useSWR from "swr";
import { listKnowledgeBases } from "@/lib/api/knowledge-base";

export function useKnowledgeBases() {
  const { data, error, isLoading, mutate } = useSWR(
    "/api/knowledge-bases",
    () => listKnowledgeBases(),
    { revalidateOnFocus: false }
  );

  return {
    knowledgeBases: data?.knowledge_bases ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate,
  };
}
