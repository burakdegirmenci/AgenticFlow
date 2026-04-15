import { AlertCircle, Bot, Sparkles, User, Wrench } from "lucide-react";
import { useEffect, useRef } from "react";

import type { WorkflowProposal } from "@/api/agent";
import type { ChatMessage } from "@/store/chatStore";

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  onApplyProposal: (proposal: WorkflowProposal) => void;
}

export default function MessageList({ messages, isStreaming, onApplyProposal }: Props) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <div className="mb-3 flex h-10 w-10 items-center justify-center border border-neutral-200 bg-white">
          <Sparkles className="h-4 w-4 text-accent" strokeWidth={1.75} />
        </div>
        <div className="text-[13px] font-medium text-ink">Workflow Asistanı</div>
        <p className="mt-1 text-[12px] leading-relaxed text-neutral-500">
          İş sürecinizi anlatın, size uygun bir workflow önereyim.
          <br />
          Örn:{" "}
          <span className="text-neutral-700">
            "Yeni siparişleri her 5 dk tara, fatura no'su olmayanları CSV'ye yaz."
          </span>
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="flex flex-col gap-3 px-3 py-3">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onApplyProposal={onApplyProposal} />
        ))}
        {isStreaming && (
          <div className="flex items-center gap-2 px-2 text-[11px] text-neutral-500">
            <div className="flex gap-0.5">
              <span className="h-1 w-1 animate-pulse bg-accent" />
              <span className="h-1 w-1 animate-pulse bg-accent [animation-delay:120ms]" />
              <span className="h-1 w-1 animate-pulse bg-accent [animation-delay:240ms]" />
            </div>
            <span>Asistan düşünüyor…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  onApplyProposal,
}: {
  message: ChatMessage;
  onApplyProposal: (proposal: WorkflowProposal) => void;
}) {
  const isUser = message.role === "user";
  const Icon = isUser ? User : Bot;

  return (
    <div className="flex gap-2">
      <div
        className={[
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center border",
          isUser
            ? "border-neutral-300 bg-neutral-100 text-neutral-600"
            : "border-accent bg-white text-accent",
        ].join(" ")}
      >
        <Icon className="h-3 w-3" strokeWidth={2} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
          {isUser ? "Sen" : "Asistan"}
        </div>
        <div className="mt-0.5 whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink">
          {message.content || <span className="text-neutral-400">…</span>}
        </div>

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {message.toolCalls.map((tc, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 border border-neutral-200 bg-neutral-50 px-2 py-1.5"
              >
                <Wrench className="mt-0.5 h-3 w-3 shrink-0 text-neutral-500" strokeWidth={2} />
                <div className="min-w-0 flex-1 font-mono text-[11px] text-neutral-600">
                  <span className="font-semibold text-ink">{tc.name}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {(() => {
          const proposal = message.proposal;
          if (!proposal) return null;
          return (
            <ProposalCard
              proposal={proposal}
              onApply={() => {
                onApplyProposal(proposal);
              }}
            />
          );
        })()}

        {message.error && (
          <div className="mt-2 flex items-start gap-2 border border-red-200 bg-red-50 px-2 py-1.5">
            <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-red-500" strokeWidth={2} />
            <div className="min-w-0 flex-1 text-[11px] text-red-700">{message.error}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function ProposalCard({ proposal, onApply }: { proposal: WorkflowProposal; onApply: () => void }) {
  return (
    <div className="mt-2 border border-accent/40 bg-white">
      <div className="flex items-center justify-between border-b border-neutral-100 bg-accent/5 px-2.5 py-1.5">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-accent">
          <Sparkles className="h-3 w-3" strokeWidth={2} />
          Workflow Önerisi
        </div>
        <span className="font-mono text-[10px] text-neutral-500">
          {proposal.nodes.length} node • {proposal.edges.length} bağlantı
        </span>
      </div>
      <div className="px-2.5 py-2">
        <div className="text-[12px] font-medium text-ink">{proposal.name}</div>
        {proposal.description && (
          <div className="mt-0.5 text-[11px] text-neutral-500">{proposal.description}</div>
        )}
        <div className="mt-2 max-h-24 overflow-y-auto">
          <ul className="space-y-0.5 font-mono text-[10.5px] text-neutral-600">
            {proposal.nodes.slice(0, 8).map((n) => (
              <li key={n.id} className="truncate">
                <span className="text-neutral-400">{n.id}</span>{" "}
                <span className="text-ink">{n.type}</span>
              </li>
            ))}
            {proposal.nodes.length > 8 && (
              <li className="text-neutral-400">+{proposal.nodes.length - 8} daha…</li>
            )}
          </ul>
        </div>
        <button
          onClick={onApply}
          className="mt-2 w-full border border-accent bg-accent px-2 py-1.5 text-[11px] font-medium text-white hover:bg-accent-hover"
        >
          Canvas'a Uygula
        </button>
      </div>
    </div>
  );
}
