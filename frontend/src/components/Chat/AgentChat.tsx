import { useQuery } from "@tanstack/react-query";
import { RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { listProviders, streamChat, type WorkflowProposal } from "@/api/agent";
import { newAssistantMessage, newUserMessage, useChatStore } from "@/store/chatStore";

import MessageInput from "./MessageInput";
import MessageList from "./MessageList";

interface Props {
  workflowId: number | null;
  onApplyProposal: (proposal: WorkflowProposal) => void;
  onClose: () => void;
}

export default function AgentChat({ workflowId, onApplyProposal, onClose }: Props) {
  const sessionId = useChatStore((s) => s.sessionId);
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const selectedProvider = useChatStore((s) => s.selectedProvider);

  const setSessionId = useChatStore((s) => s.setSessionId);
  const addMessage = useChatStore((s) => s.addMessage);
  const appendDeltaToLast = useChatStore((s) => s.appendDeltaToLast);
  const attachProposalToLast = useChatStore((s) => s.attachProposalToLast);
  const attachToolUseToLast = useChatStore((s) => s.attachToolUseToLast);
  const attachErrorToLast = useChatStore((s) => s.attachErrorToLast);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const resetSession = useChatStore((s) => s.resetSession);
  const setSelectedProvider = useChatStore((s) => s.setSelectedProvider);

  const abortRef = useRef<AbortController | null>(null);

  // Cancel the in-flight stream when the panel unmounts (e.g. user navigates away)
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const providers = useQuery({
    queryKey: ["agent", "providers"],
    queryFn: listProviders,
    staleTime: 60_000,
  });

  // Auto-pick the first available provider once we know the list
  useEffect(() => {
    if (selectedProvider || !providers.data) return;
    const firstAvailable = providers.data.find((p) => p.available);
    if (firstAvailable) setSelectedProvider(firstAvailable.name);
  }, [providers.data, selectedProvider, setSelectedProvider]);

  const handleSend = async (text: string) => {
    if (isStreaming) return;

    addMessage(newUserMessage(text));
    addMessage(newAssistantMessage());
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat({
        message: text,
        sessionId,
        workflowId,
        provider: selectedProvider,
        signal: controller.signal,
        onEvent: (event) => {
          switch (event.type) {
            case "session":
              if (sessionId == null) setSessionId(event.session_id);
              break;
            case "text_delta":
              appendDeltaToLast(event.text);
              break;
            case "tool_use":
              attachToolUseToLast(event.name, event.input);
              break;
            case "workflow_proposal":
              attachProposalToLast(event.proposal);
              break;
            case "warning":
              // Surface warnings inline as a small inline note
              appendDeltaToLast(`\n\n[uyarı] ${event.message}`);
              break;
            case "error":
              attachErrorToLast(event.message);
              break;
            case "done":
              // handled by stream end
              break;
          }
        },
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Bilinmeyen hata";
      // If user aborted, do not surface as error
      if (controller.signal.aborted) {
        attachErrorToLast("Akış durduruldu.");
      } else {
        attachErrorToLast(msg);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const handleAbort = () => {
    abortRef.current?.abort();
  };

  const handleNewSession = () => {
    abortRef.current?.abort();
    resetSession();
  };

  return (
    <aside className="flex h-full w-[360px] shrink-0 flex-col border-l border-neutral-200 bg-white">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-neutral-200 px-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-accent" strokeWidth={2} />
          <span className="text-[12.5px] font-semibold">Agent</span>
          {sessionId != null && (
            <span className="border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 font-mono text-[10px] text-neutral-500">
              #{sessionId}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewSession}
            disabled={isStreaming}
            className="flex h-7 w-7 items-center justify-center text-neutral-500 hover:bg-neutral-50 hover:text-ink disabled:opacity-40"
            title="Yeni sohbet"
          >
            <RotateCcw className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center text-neutral-500 hover:bg-neutral-50 hover:text-ink"
            title="Kapat"
          >
            <X className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>
      </header>

      <div className="flex shrink-0 items-center gap-2 border-b border-neutral-200 bg-neutral-50 px-3 py-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
          Provider
        </span>
        <select
          value={selectedProvider ?? ""}
          onChange={(e) => setSelectedProvider(e.target.value || null)}
          disabled={isStreaming || providers.isLoading}
          className="flex-1 border border-neutral-300 bg-white px-1.5 py-1 text-[11px] outline-none focus:border-accent disabled:opacity-50"
        >
          <option value="">Otomatik</option>
          {providers.data?.map((p) => (
            <option key={p.name} value={p.name} disabled={!p.available}>
              {p.display_name} {p.available ? "" : "(yok)"}
            </option>
          ))}
        </select>
      </div>

      <MessageList
        messages={messages}
        isStreaming={isStreaming}
        onApplyProposal={onApplyProposal}
      />

      <MessageInput
        isStreaming={isStreaming}
        onSend={handleSend}
        onAbort={handleAbort}
        disabled={
          (providers.data && !providers.data.some((p) => p.available)) || providers.isLoading
        }
        placeholder={
          providers.data && !providers.data.some((p) => p.available)
            ? "Önce Settings'ten bir provider yapılandırın…"
            : undefined
        }
      />
    </aside>
  );
}
