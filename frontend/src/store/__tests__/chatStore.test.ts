import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { WorkflowProposal } from "@/api/agent";

import type { ChatMessage } from "../chatStore";
import { useChatStore } from "../chatStore";

const makeUserMsg = (content: string): ChatMessage => ({
  id: `u_${content}`,
  role: "user",
  content,
  createdAt: Date.now(),
});

const makeAssistantMsg = (content: string): ChatMessage => ({
  id: `a_${content}`,
  role: "assistant",
  content,
  createdAt: Date.now(),
});

const makeProposal = (): WorkflowProposal =>
  ({
    name: "Test Proposal",
    description: "fixture",
    graph_json: { nodes: [], edges: [] },
  }) as unknown as WorkflowProposal;

describe("useChatStore", () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().resetSession();
      useChatStore.getState().setOpen(false);
    });
  });

  it("has sensible initial state", () => {
    const s = useChatStore.getState();
    expect(s.open).toBe(false);
    expect(s.sessionId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.isStreaming).toBe(false);
    expect(s.pendingProposal).toBeNull();
  });

  it("toggle flips open state", () => {
    expect(useChatStore.getState().open).toBe(false);
    act(() => useChatStore.getState().toggle());
    expect(useChatStore.getState().open).toBe(true);
    act(() => useChatStore.getState().toggle());
    expect(useChatStore.getState().open).toBe(false);
  });

  it("setOpen writes the raw value", () => {
    act(() => useChatStore.getState().setOpen(true));
    expect(useChatStore.getState().open).toBe(true);
  });

  it("addMessage appends to the list", () => {
    act(() => {
      useChatStore.getState().addMessage(makeUserMsg("hello"));
      useChatStore.getState().addMessage(makeAssistantMsg("hi there"));
    });
    const msgs = useChatStore.getState().messages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0]?.role).toBe("user");
    expect(msgs[1]?.role).toBe("assistant");
  });

  it("setMessages replaces the list", () => {
    act(() => {
      useChatStore.getState().addMessage(makeUserMsg("first"));
      useChatStore.getState().setMessages([makeAssistantMsg("replaced")]);
    });
    const msgs = useChatStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0]?.content).toBe("replaced");
  });

  it("appendDeltaToLast concatenates into the last assistant message", () => {
    act(() => {
      useChatStore.getState().addMessage(makeAssistantMsg("Hello"));
      useChatStore.getState().appendDeltaToLast(", ");
      useChatStore.getState().appendDeltaToLast("world!");
    });
    expect(useChatStore.getState().messages[0]?.content).toBe("Hello, world!");
  });

  it("appendDeltaToLast is a no-op on empty messages", () => {
    act(() => useChatStore.getState().appendDeltaToLast("lost text"));
    expect(useChatStore.getState().messages).toEqual([]);
  });

  it("appendDeltaToLast is a no-op when last message is from user", () => {
    act(() => {
      useChatStore.getState().addMessage(makeUserMsg("question"));
      useChatStore.getState().appendDeltaToLast("should not stick");
    });
    expect(useChatStore.getState().messages[0]?.content).toBe("question");
  });

  it("attachProposalToLast decorates an assistant message", () => {
    const proposal = makeProposal();
    act(() => {
      useChatStore.getState().addMessage(makeAssistantMsg("proposing..."));
      useChatStore.getState().attachProposalToLast(proposal);
    });
    expect(useChatStore.getState().messages[0]?.proposal).toBe(proposal);
  });

  it("attachToolUseToLast records tool calls", () => {
    act(() => {
      useChatStore.getState().addMessage(makeAssistantMsg("thinking"));
      useChatStore.getState().attachToolUseToLast("ticimax.urun.select", { aktif: 1 });
      useChatStore.getState().attachToolUseToLast("transform.filter", { field: "stok" });
    });
    const last = useChatStore.getState().messages[0];
    expect(last?.toolCalls).toHaveLength(2);
    expect(last?.toolCalls?.[0]?.name).toBe("ticimax.urun.select");
  });

  it("attachErrorToLast records the error on the last message", () => {
    act(() => {
      useChatStore.getState().addMessage(makeAssistantMsg("oops"));
      useChatStore.getState().attachErrorToLast("provider unavailable");
    });
    expect(useChatStore.getState().messages[0]?.error).toBe("provider unavailable");
  });

  it("setStreaming toggles the flag", () => {
    act(() => useChatStore.getState().setStreaming(true));
    expect(useChatStore.getState().isStreaming).toBe(true);
    act(() => useChatStore.getState().setStreaming(false));
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("setPendingProposal / clearPendingProposal", () => {
    const proposal = makeProposal();
    act(() => useChatStore.getState().setPendingProposal(proposal));
    expect(useChatStore.getState().pendingProposal).toBe(proposal);
    act(() => useChatStore.getState().clearPendingProposal());
    expect(useChatStore.getState().pendingProposal).toBeNull();
  });

  it("setSelectedProvider / setSessionId", () => {
    act(() => {
      useChatStore.getState().setSelectedProvider("anthropic_api");
      useChatStore.getState().setSessionId(42);
    });
    expect(useChatStore.getState().selectedProvider).toBe("anthropic_api");
    expect(useChatStore.getState().sessionId).toBe(42);
  });

  it("resetSession clears session state but keeps panel open/provider", () => {
    act(() => {
      useChatStore.getState().setOpen(true);
      useChatStore.getState().setSelectedProvider("google_genai");
      useChatStore.getState().setSessionId(7);
      useChatStore.getState().addMessage(makeUserMsg("hi"));
      useChatStore.getState().setPendingProposal(makeProposal());
      useChatStore.getState().resetSession();
    });
    const s = useChatStore.getState();
    expect(s.sessionId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.pendingProposal).toBeNull();
    expect(s.isStreaming).toBe(false);
    // open + selectedProvider are preserved
    expect(s.open).toBe(true);
    expect(s.selectedProvider).toBe("google_genai");
  });
});
