import { request } from "./client";
import type {
  ChannelInfo,
  CreateChannelRequest,
  ChannelStartStopResponse,
  UpdateSendersRequest,
  UpdateSendersResponse,
  WeChatQRCodeResponse,
  WeChatLoginStatus,
  ChannelSessionInfo,
  SessionList,
} from "./types";

export function listChannels(signal?: AbortSignal) {
  return request<ChannelInfo[]>("GET", "/api/channels", undefined, signal);
}

export function getChannel(channelId: string, signal?: AbortSignal) {
  return request<ChannelInfo>(
    "GET",
    `/api/channels/${channelId}`,
    undefined,
    signal,
  );
}

export function createChannel(data: CreateChannelRequest) {
  return request<ChannelInfo>("POST", "/api/channels", data);
}

export function deleteChannel(channelId: string) {
  return request<{ success: boolean }>("DELETE", `/api/channels/${channelId}`);
}

export function startChannel(channelId: string) {
  return request<ChannelStartStopResponse>(
    "POST",
    `/api/channels/${channelId}/start`,
  );
}

export function stopChannel(channelId: string) {
  return request<ChannelStartStopResponse>(
    "POST",
    `/api/channels/${channelId}/stop`,
  );
}

export function updateSenders(channelId: string, data: UpdateSendersRequest) {
  return request<UpdateSendersResponse>(
    "PUT",
    `/api/channels/${channelId}/senders`,
    data,
  );
}

export function getWeChatQRCode(channelId: string) {
  return request<WeChatQRCodeResponse>(
    "POST",
    `/api/channels/wechat/${channelId}/qrcode`,
  );
}

export function getWeChatLoginStatus(
  channelId: string,
  qrcode: string,
  signal?: AbortSignal,
) {
  return request<WeChatLoginStatus>(
    "GET",
    `/api/channels/wechat/${channelId}/status?qrcode=${encodeURIComponent(qrcode)}`,
    undefined,
    signal,
  );
}

export function listChannelSessions(channelId: string, signal?: AbortSignal) {
  return request<ChannelSessionInfo[]>(
    "GET",
    `/api/channels/${channelId}/sessions`,
    undefined,
    signal,
  );
}

export function getChannelSessionMessages(
  sessionId: string,
  params?: { limit?: number; offset?: number; signal?: AbortSignal },
) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const qs = searchParams.toString();
  return request<SessionList>(
    "GET",
    `/api/sessions/${sessionId}/messages${qs ? `?${qs}` : ""}`,
    undefined,
    params?.signal,
  );
}
