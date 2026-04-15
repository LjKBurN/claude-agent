"use client";

import { useCallback } from "react";
import useSWR from "swr";
import {
  listChannels,
  getChannel,
  listChannelSessions,
} from "@/lib/api/channels";
import type { ChannelInfo, ChannelSessionInfo } from "@/lib/api/types";

export function useChannels() {
  const { data, error, isLoading, mutate } = useSWR<ChannelInfo[]>(
    "/api/channels",
    () => listChannels(),
    { revalidateOnFocus: true },
  );

  return {
    channels: data ?? [],
    error,
    isLoading,
    refresh: mutate,
  };
}

export function useChannel(channelId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ChannelInfo>(
    channelId ? `/api/channels/${channelId}` : null,
    () => (channelId ? getChannel(channelId) : undefined!),
  );

  return {
    channel: data ?? null,
    error,
    isLoading,
    refresh: mutate,
  };
}

export function useChannelSessions(channelId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ChannelSessionInfo[]>(
    channelId ? `/api/channels/${channelId}/sessions` : null,
    () => (channelId ? listChannelSessions(channelId) : []),
  );

  return {
    sessions: data ?? [],
    error,
    isLoading,
    refresh: mutate,
  };
}
