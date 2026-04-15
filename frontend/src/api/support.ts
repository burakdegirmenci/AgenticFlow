import type { Execution } from "@/types/execution";

import { apiClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface SupportTicket {
  ID: number;
  Konu: string | null;
  Mesaj: string | null;
  UyeAdi: string | null;
  UyeID: number;
  DurumID: number;
  EklemeTarihi: string | null;
  KonuID: number | null;
}

export interface TicketMessage {
  ID: number;
  TalepID: number;
  Cevap: string;
  Cevaplayan: number; // 0 = müşteri, 1 = yönetici
  CevaplayanStr: string;
  UyeAdi: string;
  UyeID: number;
  KonusmaTarihi: string;
  FileUrl: string | null;
}

// ---------------------------------------------------------------------------
// REST endpoints
// ---------------------------------------------------------------------------
export async function listTickets(
  siteId = 2,
  durumId = -1,
  kayitSayisi = 50,
): Promise<{ tickets: SupportTicket[]; count: number }> {
  const { data } = await apiClient.get("/support/tickets", {
    params: { site_id: siteId, durum_id: durumId, kayit_sayisi: kayitSayisi },
  });
  return data;
}

export async function getTicketMessages(
  ticketId: number,
  uyeId = -1,
  siteId = 2,
): Promise<{ messages: TicketMessage[] }> {
  const { data } = await apiClient.get(`/support/tickets/${ticketId}/messages`, {
    params: { uye_id: uyeId, site_id: siteId },
  });
  return data;
}

export async function sendReply(params: {
  ticketId: number;
  uyeId: number;
  message: string;
  siteId?: number;
}): Promise<{ status: string; result: unknown }> {
  const { data } = await apiClient.post("/support/send", {
    ticket_id: params.ticketId,
    uye_id: params.uyeId,
    message: params.message,
    site_id: params.siteId ?? 2,
  });
  return data;
}

// ---------------------------------------------------------------------------
// Workflow-based reply generation
// ---------------------------------------------------------------------------
export async function generateReply(ticketId: number, uyeId: number): Promise<Execution> {
  const { data } = await apiClient.post<Execution>(`/support/tickets/${ticketId}/generate`, null, {
    params: { uye_id: uyeId },
  });
  return data;
}
