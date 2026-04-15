import { create } from "zustand";

import type { WorkflowProposal } from "@/api/agent";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: number;
  // Optional structured payloads attached to an assistant message
  proposal?: WorkflowProposal | null;
  toolCalls?: { name: string; input: Record<string, unknown> }[];
  error?: string | null;
}

interface ChatState {
  open: boolean;
  sessionId: number | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  pendingProposal: WorkflowProposal | null;
  selectedProvider: string | null;

  // Panel
  toggle: () => void;
  setOpen: (open: boolean) => void;

  // Session
  setSessionId: (id: number | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  resetSession: () => void;

  // Streaming helpers
  addMessage: (message: ChatMessage) => void;
  appendDeltaToLast: (delta: string) => void;
  attachProposalToLast: (proposal: WorkflowProposal) => void;
  attachToolUseToLast: (name: string, input: Record<string, unknown>) => void;
  attachErrorToLast: (message: string) => void;
  setStreaming: (streaming: boolean) => void;

  // Proposal apply queue
  setPendingProposal: (p: WorkflowProposal | null) => void;
  clearPendingProposal: () => void;

  // Provider preference
  setSelectedProvider: (name: string | null) => void;
}

function genId(): string {
  return `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useChatStore = create<ChatState>((set) => ({
  open: false,
  sessionId: null,
  messages: [],
  isStreaming: false,
  pendingProposal: null,
  selectedProvider: null,

  toggle: () => set((s) => ({ open: !s.open })),
  setOpen: (open) => set({ open }),

  setSessionId: (sessionId) => set({ sessionId }),
  setMessages: (messages) => set({ messages }),
  resetSession: () =>
    set({
      sessionId: null,
      messages: [],
      pendingProposal: null,
      isStreaming: false,
    }),

  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),

  appendDeltaToLast: (delta) =>
    set((s) => {
      if (s.messages.length === 0) return s;
      const last = s.messages[s.messages.length - 1];
      if (last.role !== "assistant") return s;
      const updated = { ...last, content: last.content + delta };
      return { messages: [...s.messages.slice(0, -1), updated] };
    }),

  attachProposalToLast: (proposal) =>
    set((s) => {
      if (s.messages.length === 0) return { pendingProposal: proposal };
      const last = s.messages[s.messages.length - 1];
      if (last.role !== "assistant") return { ...s, pendingProposal: proposal };
      const updated = { ...last, proposal };
      return {
        messages: [...s.messages.slice(0, -1), updated],
        pendingProposal: proposal,
      };
    }),

  attachToolUseToLast: (name, input) =>
    set((s) => {
      if (s.messages.length === 0) return s;
      const last = s.messages[s.messages.length - 1];
      if (last.role !== "assistant") return s;
      const calls = last.toolCalls ? [...last.toolCalls] : [];
      calls.push({ name, input });
      const updated = { ...last, toolCalls: calls };
      return { messages: [...s.messages.slice(0, -1), updated] };
    }),

  attachErrorToLast: (errorMsg) =>
    set((s) => {
      if (s.messages.length === 0) return s;
      const last = s.messages[s.messages.length - 1];
      if (last.role !== "assistant") return s;
      const updated = { ...last, error: errorMsg };
      return { messages: [...s.messages.slice(0, -1), updated] };
    }),

  setStreaming: (isStreaming) => set({ isStreaming }),

  setPendingProposal: (pendingProposal) => set({ pendingProposal }),
  clearPendingProposal: () => set({ pendingProposal: null }),

  setSelectedProvider: (selectedProvider) => set({ selectedProvider }),
}));

export function newAssistantMessage(): ChatMessage {
  return {
    id: genId(),
    role: "assistant",
    content: "",
    createdAt: Date.now(),
    proposal: null,
    toolCalls: [],
    error: null,
  };
}

export function newUserMessage(content: string): ChatMessage {
  return {
    id: genId(),
    role: "user",
    content,
    createdAt: Date.now(),
  };
}
