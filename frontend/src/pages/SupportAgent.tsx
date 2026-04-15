import {
  AlertCircle,
  Bot,
  CheckCircle,
  Edit3,
  Headphones,
  Image,
  Loader2,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldCheck,
  User,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getExecution } from "@/api/executions";
import {
  generateReply,
  getTicketMessages,
  listTickets,
  sendReply,
  type SupportTicket,
  type TicketMessage,
} from "@/api/support";
import type { ExecutionDetail } from "@/types/execution";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Tab = "new" | "answered" | "all";
const TAB_DURUM: Record<Tab, number> = { new: 1, answered: 2, all: -1 };
const TAB_LABELS: Record<Tab, string> = {
  new: "Yeni",
  answered: "Cevaplanan",
  all: "Tümü",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const formatDate = (d: string | null) => (d ? new Date(d).toLocaleDateString("tr-TR") : "—");

const formatDateTime = (d: string | null) =>
  d
    ? new Date(d).toLocaleString("tr-TR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

const durumLabel = (d: number) =>
  d === 1 ? "Yeni" : d === 2 ? "Cevaplandı" : d === 3 ? "Çözüldü" : String(d);

const durumColor = (d: number) =>
  d === 1
    ? "bg-blue-100 text-blue-700"
    : d === 2
      ? "bg-amber-100 text-amber-700"
      : "bg-green-100 text-green-700";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function SupportAgent() {
  // Ticket list
  const [tab, setTab] = useState<Tab>("new");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);

  // Selected ticket
  const [selected, setSelected] = useState<SupportTicket | null>(null);

  // Message history
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  // Workflow execution
  const [generating, setGenerating] = useState(false);
  const [executionId, setExecutionId] = useState<number | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Draft reply
  const [draftReply, setDraftReply] = useState("");
  const [editMode, setEditMode] = useState(false);

  // Send
  const [sending, setSending] = useState(false);
  const [sentOk, setSentOk] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // ---------------------------------------------------------------------------
  // Fetch tickets
  // ---------------------------------------------------------------------------
  const loadTickets = useCallback(async () => {
    setTicketsLoading(true);
    try {
      const { tickets: data } = await listTickets(2, TAB_DURUM[tab], 100);
      setTickets(data);
    } catch (e) {
      console.error("Ticket yükleme hatası:", e);
      setTickets([]);
    } finally {
      setTicketsLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, draftReply, generating]);

  // ---------------------------------------------------------------------------
  // Fetch messages for selected ticket
  // ---------------------------------------------------------------------------
  const loadMessages = useCallback(async (ticket: SupportTicket) => {
    setMessagesLoading(true);
    try {
      const { messages: data } = await getTicketMessages(ticket.ID, ticket.UyeID);
      setMessages(data);
    } catch (e) {
      console.error("Mesaj yükleme hatası:", e);
      setMessages([]);
    } finally {
      setMessagesLoading(false);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Select a ticket
  // ---------------------------------------------------------------------------
  const handleSelect = (t: SupportTicket) => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setSelected(t);
    setMessages([]);
    setDraftReply("");
    setEditMode(false);
    setSentOk(false);
    setExecutionId(null);
    setExecutionError(null);
    setGenerating(false);
    loadMessages(t);
  };

  // ---------------------------------------------------------------------------
  // Extract draft text from execution
  // ---------------------------------------------------------------------------
  const extractDraft = (exec: ExecutionDetail): string | null => {
    const aiStep = exec.steps?.find((s) => s.node_type === "ai.prompt");
    if (aiStep?.status === "SUCCESS" && aiStep.output_data) {
      const text = aiStep.output_data.text;
      if (typeof text === "string") return text;
    }
    return null;
  };

  // ---------------------------------------------------------------------------
  // Run workflow
  // ---------------------------------------------------------------------------
  const runGenerate = async () => {
    if (!selected || generating) return;

    setGenerating(true);
    setDraftReply("");
    setEditMode(false);
    setSentOk(false);
    setExecutionError(null);

    try {
      const exec = await generateReply(selected.ID, selected.UyeID);
      setExecutionId(exec.id);

      pollRef.current = setInterval(async () => {
        try {
          const detail = await getExecution(exec.id);

          if (detail.status === "SUCCESS") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setGenerating(false);

            const draft = extractDraft(detail);
            if (draft) {
              setDraftReply(draft);
            } else {
              setExecutionError("AI yanıt üretemedi.");
            }
          } else if (detail.status === "ERROR") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setGenerating(false);
            setExecutionError(detail.error || "Workflow hatası.");
          }
        } catch (e) {
          console.error("Polling error:", e);
        }
      }, 2000);
    } catch (e) {
      setGenerating(false);
      setExecutionError(String(e));
    }
  };

  // ---------------------------------------------------------------------------
  // Send reply
  // ---------------------------------------------------------------------------
  const handleSend = async () => {
    if (!selected || !draftReply.trim() || sending) return;
    setSending(true);
    try {
      await sendReply({
        ticketId: selected.ID,
        uyeId: selected.UyeID,
        message: draftReply,
      });
      setSentOk(true);
      setEditMode(false);
      // Refresh messages and ticket list
      loadMessages(selected);
      loadTickets();
    } catch (e) {
      console.error("Gönderme hatası:", e);
      alert("Yanıt gönderilemedi: " + String(e));
    } finally {
      setSending(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="flex h-full">
      {/* ---- Left panel: Ticket list ---- */}
      <div className="flex w-80 shrink-0 flex-col border-r border-neutral-200 bg-white">
        <div className="flex items-center gap-1 border-b border-neutral-200 px-3 py-2">
          <Headphones className="mr-1 h-4 w-4 text-accent" strokeWidth={1.75} />
          <span className="text-[13px] font-semibold">Destek</span>
          <div className="ml-auto flex gap-1">
            {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={[
                  "rounded px-2 py-0.5 text-[11px] font-medium transition-colors",
                  tab === t ? "bg-neutral-900 text-white" : "text-neutral-500 hover:bg-neutral-100",
                ].join(" ")}
              >
                {TAB_LABELS[t]}
              </button>
            ))}
          </div>
          <button
            onClick={loadTickets}
            disabled={ticketsLoading}
            className="ml-1 rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${ticketsLoading ? "animate-spin" : ""}`}
              strokeWidth={1.75}
            />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {tickets.length === 0 && !ticketsLoading && (
            <p className="px-4 py-8 text-center text-[12px] text-neutral-400">Ticket bulunamadı.</p>
          )}
          {tickets.map((t) => (
            <button
              key={t.ID}
              onClick={() => handleSelect(t)}
              className={[
                "flex w-full flex-col gap-0.5 border-b border-neutral-100 px-3 py-2.5 text-left transition-colors",
                selected?.ID === t.ID
                  ? "border-l-2 border-l-accent bg-neutral-50"
                  : "border-l-2 border-l-transparent hover:bg-neutral-50",
              ].join(" ")}
            >
              <div className="flex items-center gap-2">
                <span className="line-clamp-1 text-[12px] font-medium text-neutral-900">
                  #{t.ID}
                </span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${durumColor(t.DurumID)}`}
                >
                  {durumLabel(t.DurumID)}
                </span>
              </div>
              <span className="line-clamp-1 text-[11px] text-neutral-500">
                {t.Konu || "Konu belirtilmemiş"}
              </span>
              <div className="flex items-center gap-2 text-[10px] text-neutral-400">
                <span>{t.UyeAdi || "—"}</span>
                <span>•</span>
                <span>{formatDate(t.EklemeTarihi)}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ---- Right panel ---- */}
      <div className="flex flex-1 flex-col bg-paper">
        {!selected ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center text-neutral-400">
              <MessageSquare className="mx-auto mb-2 h-8 w-8" strokeWidth={1.25} />
              <p className="text-[13px]">Soldaki listeden bir ticket seçin</p>
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 border-b border-neutral-200 bg-white px-5 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-semibold text-neutral-900">#{selected.ID}</span>
                  <span className="truncate text-[13px] text-neutral-600">
                    {selected.Konu || "Konu belirtilmemiş"}
                  </span>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${durumColor(selected.DurumID)}`}
                  >
                    {durumLabel(selected.DurumID)}
                  </span>
                </div>
                <p className="text-[11px] text-neutral-400">
                  {selected.UyeAdi || "—"} • ID: {selected.UyeID} •{" "}
                  {formatDateTime(selected.EklemeTarihi)}
                </p>
              </div>
              <button
                onClick={runGenerate}
                disabled={generating}
                className={[
                  "flex shrink-0 items-center gap-2 rounded px-4 py-2 text-[13px] font-medium text-white transition-colors",
                  generating
                    ? "cursor-not-allowed bg-neutral-400"
                    : "bg-neutral-900 hover:bg-neutral-800",
                ].join(" ")}
              >
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
                ) : (
                  <Bot className="h-4 w-4" strokeWidth={2} />
                )}
                {generating ? "Oluşturuluyor…" : "Yanıt Oluştur"}
              </button>
            </div>

            {/* ---- Conversation thread ---- */}
            <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
              {messagesLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-neutral-400" strokeWidth={2} />
                  <span className="ml-2 text-[12px] text-neutral-400">Mesajlar yükleniyor…</span>
                </div>
              )}

              {!messagesLoading && messages.length === 0 && selected.Mesaj && (
                /* Fallback: only initial message available */
                <MessageBubble
                  sender={selected.UyeAdi || "Müşteri"}
                  date={selected.EklemeTarihi}
                  text={selected.Mesaj}
                  isStaff={false}
                />
              )}

              {!messagesLoading &&
                messages.map((m) => (
                  <MessageBubble
                    key={m.ID}
                    sender={m.UyeAdi || m.CevaplayanStr}
                    date={m.KonusmaTarihi}
                    text={m.Cevap}
                    isStaff={m.Cevaplayan === 1}
                    fileUrl={m.FileUrl}
                  />
                ))}

              {/* Generating indicator inside conversation */}
              {generating && (
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-900">
                    <Bot className="h-3.5 w-3.5 text-white" strokeWidth={2} />
                  </div>
                  <div className="rounded-lg border border-neutral-200 bg-white px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-accent" strokeWidth={2} />
                      <span className="text-[12px] text-neutral-500">Yanıt oluşturuluyor…</span>
                    </div>
                    <p className="mt-1 text-[11px] text-neutral-400">
                      Ticket verileri çekiliyor, AI analiz ediyor
                      {executionId && (
                        <span className="ml-1 text-neutral-300">(#{executionId})</span>
                      )}
                    </p>
                  </div>
                </div>
              )}

              {/* Error */}
              {executionError && !generating && (
                <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                  <AlertCircle className="h-4 w-4 shrink-0 text-red-500" strokeWidth={2} />
                  <p className="text-[12px] text-red-600">{executionError}</p>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* ---- Bottom: Draft reply ---- */}
            {draftReply && (
              <div className="border-t border-neutral-200 bg-white px-5 py-4">
                {sentOk ? (
                  <div className="flex items-center gap-2 rounded bg-green-50 px-4 py-3">
                    <CheckCircle className="h-5 w-5 text-green-600" strokeWidth={2} />
                    <span className="text-[13px] font-medium text-green-700">
                      Yanıt başarıyla gönderildi!
                    </span>
                  </div>
                ) : editMode ? (
                  <textarea
                    value={draftReply}
                    onChange={(e) => setDraftReply(e.target.value)}
                    className="w-full rounded border border-neutral-300 px-3 py-2 text-[12px] leading-relaxed text-neutral-800 focus:border-accent focus:outline-none"
                    rows={6}
                  />
                ) : (
                  <div className="rounded border border-neutral-200 bg-neutral-50 px-4 py-3">
                    <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-neutral-400">
                      Taslak Yanıt
                    </p>
                    <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-neutral-800">
                      {draftReply}
                    </p>
                  </div>
                )}

                {!sentOk && (
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      onClick={() => setEditMode(!editMode)}
                      className="flex items-center gap-1.5 rounded border border-neutral-300 px-3 py-1.5 text-[12px] font-medium text-neutral-600 hover:bg-neutral-50"
                    >
                      <Edit3 className="h-3.5 w-3.5" strokeWidth={1.75} />
                      {editMode ? "Önizle" : "Düzenle"}
                    </button>
                    <button
                      onClick={handleSend}
                      disabled={sending || !draftReply.trim()}
                      className={[
                        "flex items-center gap-1.5 rounded px-4 py-1.5 text-[12px] font-medium text-white transition-colors",
                        sending
                          ? "cursor-not-allowed bg-neutral-400"
                          : "bg-neutral-900 hover:bg-neutral-800",
                      ].join(" ")}
                    >
                      {sending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
                      ) : (
                        <Send className="h-3.5 w-3.5" strokeWidth={2} />
                      )}
                      {sending ? "Gönderiliyor…" : "Onayla & Gönder"}
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble sub-component
// ---------------------------------------------------------------------------
function MessageBubble({
  sender,
  date,
  text,
  isStaff,
  fileUrl,
}: {
  sender: string;
  date: string | null;
  text: string;
  isStaff: boolean;
  fileUrl?: string | null;
}) {
  return (
    <div className={`flex items-start gap-3 ${isStaff ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          isStaff ? "bg-neutral-900" : "bg-blue-100"
        }`}
      >
        {isStaff ? (
          <ShieldCheck className="h-3.5 w-3.5 text-white" strokeWidth={2} />
        ) : (
          <User className="h-3.5 w-3.5 text-blue-600" strokeWidth={2} />
        )}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[75%] rounded-lg px-4 py-2.5 ${
          isStaff
            ? "bg-neutral-900 text-neutral-100"
            : "border border-neutral-200 bg-white text-neutral-800"
        }`}
      >
        <div
          className={`mb-1 flex items-center gap-2 text-[10px] ${
            isStaff ? "text-neutral-400" : "text-neutral-400"
          }`}
        >
          <span className="font-medium">{sender}</span>
          <span>•</span>
          <span>{formatDateTime(date)}</span>
        </div>
        <p
          className={`whitespace-pre-wrap text-[12px] leading-relaxed ${
            isStaff ? "text-neutral-100" : "text-neutral-800"
          }`}
        >
          {text}
        </p>
        {fileUrl && (
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={`mt-2 inline-flex items-center gap-1 text-[11px] underline ${
              isStaff ? "text-blue-300" : "text-blue-600"
            }`}
          >
            <Image className="h-3 w-3" strokeWidth={2} />
            Ek dosya
          </a>
        )}
      </div>
    </div>
  );
}
