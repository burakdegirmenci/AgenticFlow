import { apiClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface AgentSession {
  id: number;
  title: string;
  workflow_id: number | null;
  created_at: string;
}

export interface AgentMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_use: Record<string, unknown> | null;
  created_at: string;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  supports_tools: boolean;
  supports_streaming: boolean;
  available: boolean;
  reason: string;
}

export interface WorkflowProposal {
  name: string;
  description: string;
  nodes: {
    id: string;
    type: string;
    position?: { x: number; y: number };
    data?: { label?: string; config?: Record<string, unknown> };
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
  }[];
}

// SSE event payloads coming from POST /api/agent/chat
export type AgentEvent =
  | { type: "session"; session_id: number }
  | { type: "text_delta"; text: string }
  | { type: "tool_use"; name: string; input: Record<string, unknown> }
  | { type: "workflow_proposal"; proposal: WorkflowProposal }
  | { type: "warning"; message: string }
  | { type: "error"; message: string }
  | { type: "done" };

// ---------------------------------------------------------------------------
// REST endpoints
// ---------------------------------------------------------------------------
export async function listProviders(): Promise<ProviderInfo[]> {
  const { data } = await apiClient.get<ProviderInfo[]>("/agent/providers");
  return data;
}

export async function createSession(
  title?: string,
  workflowId?: number | null,
): Promise<AgentSession> {
  const { data } = await apiClient.post<AgentSession>("/agent/sessions", {
    title: title ?? null,
    workflow_id: workflowId ?? null,
  });
  return data;
}

export async function listSessions(workflowId?: number | null): Promise<AgentSession[]> {
  const { data } = await apiClient.get<AgentSession[]>("/agent/sessions", {
    params: workflowId != null ? { workflow_id: workflowId } : undefined,
  });
  return data;
}

export async function getSessionMessages(sessionId: number): Promise<AgentMessage[]> {
  const { data } = await apiClient.get<AgentMessage[]>(`/agent/sessions/${sessionId}/messages`);
  return data;
}

export async function deleteSession(sessionId: number): Promise<void> {
  await apiClient.delete(`/agent/sessions/${sessionId}`);
}

// ---------------------------------------------------------------------------
// SSE streaming chat
// ---------------------------------------------------------------------------
export interface StreamChatParams {
  message: string;
  sessionId?: number | null;
  workflowId?: number | null;
  provider?: string | null;
  model?: string | null;
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
}

/**
 * Stream a chat turn from the agent. Reads the SSE stream from
 * POST /api/agent/chat and dispatches each parsed event to onEvent.
 *
 * The stream ends after a {type: "done"} event or when the underlying
 * ReadableStream closes. Errors throw.
 */
export async function streamChat(params: StreamChatParams): Promise<void> {
  const {
    message,
    sessionId = null,
    workflowId = null,
    provider = null,
    model = null,
    signal,
    onEvent,
  } = params;

  const res = await fetch("/api/agent/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      workflow_id: workflowId,
      provider,
      model,
    }),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line ("\n\n")
      let sepIndex: number;
      while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const parsed = parseSSEBlock(rawEvent);
        if (parsed) {
          onEvent(parsed);
          if (parsed.type === "done") return;
        }
      }
    }
    // Flush any trailing partial event
    if (buffer.trim()) {
      const parsed = parseSSEBlock(buffer);
      if (parsed) onEvent(parsed);
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* ignore */
    }
  }
}

function parseSSEBlock(block: string): AgentEvent | null {
  // A block is one or more lines like "data: {...}". We only care about data:
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  const payload = dataLines.join("\n");
  try {
    return JSON.parse(payload) as AgentEvent;
  } catch {
    return null;
  }
}
