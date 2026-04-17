import { create } from "zustand";
import type { ToolCall, MessageInfo } from "@/lib/api/types";

export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  createdAt: string;
}

interface ChatState {
  sessionId: string | null;
  messages: DisplayMessage[];
  isStreaming: boolean;
  streamingText: string;
  streamingToolCalls: ToolCall[];
  streamingToolName: string | null;
  error: string | null;
  needsApproval: boolean;
  approvalTools: { name: string; input: Record<string, unknown> }[];
  currentAgentId: string | null;

  // Actions
  setSessionId: (id: string | null) => void;
  setCurrentAgentId: (id: string | null) => void;
  addUserMessage: (content: string) => void;
  appendStreamText: (chunk: string) => void;
  addToolStart: (name: string) => void;
  addToolEnd: (call: ToolCall) => void;
  finalizeStream: () => void;
  startStreaming: () => void;
  stopStreaming: () => void;
  setError: (error: string | null) => void;
  loadMessages: (messages: MessageInfo[]) => void;
  reset: () => void;
  setApproval: (tools: { name: string; input: Record<string, unknown> }[]) => void;
  clearApproval: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  isStreaming: false,
  streamingText: "",
  streamingToolCalls: [],
  streamingToolName: null,
  error: null,
  needsApproval: false,
  approvalTools: [],
  currentAgentId: null,

  setSessionId: (id) => set({ sessionId: id }),

  setCurrentAgentId: (id) => set({ currentAgentId: id }),

  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: `user-${Date.now()}`,
          role: "user",
          content,
          toolCalls: [],
          createdAt: new Date().toISOString(),
        },
      ],
    })),

  appendStreamText: (chunk) =>
    set((state) => ({
      streamingText: state.streamingText + chunk,
    })),

  addToolStart: (name) => set({ streamingToolName: name }),

  addToolEnd: (call) =>
    set((state) => ({
      streamingToolCalls: [...state.streamingToolCalls, call],
      streamingToolName: null,
    })),

  finalizeStream: () =>
    set((state) => {
      if (!state.streamingText && state.streamingToolCalls.length === 0) {
        return { isStreaming: false, streamingText: "" };
      }

      return {
        messages: [
          ...state.messages,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: state.streamingText,
            toolCalls: state.streamingToolCalls,
            createdAt: new Date().toISOString(),
          },
        ],
        isStreaming: false,
        streamingText: "",
        streamingToolCalls: [],
        streamingToolName: null,
      };
    }),

  startStreaming: () =>
    set({ isStreaming: true, streamingText: "", streamingToolCalls: [], error: null, needsApproval: false, approvalTools: [] }),

  stopStreaming: () =>
    set((state) => {
      // If we have partial content, commit it as a message
      if (state.streamingText || state.streamingToolCalls.length > 0) {
        return {
          messages: [
            ...state.messages,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: state.streamingText,
              toolCalls: state.streamingToolCalls,
              createdAt: new Date().toISOString(),
            },
          ],
          isStreaming: false,
          streamingText: "",
          streamingToolCalls: [],
          streamingToolName: null,
        };
      }
      return { isStreaming: false, streamingText: "" };
    }),

  setApproval: (tools) =>
    set((state) => {
      // Commit current streaming text as a message, then set approval state
      const newMessages = state.streamingText
        ? [
            ...state.messages,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant" as const,
              content: state.streamingText,
              toolCalls: state.streamingToolCalls,
              createdAt: new Date().toISOString(),
            },
          ]
        : state.messages;
      return {
        messages: newMessages,
        isStreaming: false,
        streamingText: "",
        streamingToolCalls: [],
        streamingToolName: null,
        needsApproval: true,
        approvalTools: tools,
      };
    }),

  clearApproval: () => set({ needsApproval: false, approvalTools: [] }),

  setError: (error) => set({ error, isStreaming: false }),

  loadMessages: (messages) =>
    set({
      messages: messages.map((m) => ({
        id: String(m.id),
        role: m.role as "user" | "assistant",
        content: m.content,
        toolCalls: [],
        createdAt: m.created_at,
      })),
    }),

  reset: () =>
    set({
      sessionId: null,
      messages: [],
      isStreaming: false,
      streamingText: "",
      streamingToolCalls: [],
      streamingToolName: null,
      error: null,
      needsApproval: false,
      approvalTools: [],
    }),
}));
