import { api } from "./api";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export type ChatRole = "user" | "assistant" | "tool";

export interface ChatContentBlock {
  type: "text" | "reasoning" | "tool_use" | "tool_result" | "image";
  text?: string;
  [k: string]: unknown;
}

export interface ChatToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ChatMessage {
  id: number;
  analysis_id: number;
  turn_id: string;
  sequence: number;
  role: ChatRole;
  content_blocks: ChatContentBlock[];
  tool_calls: ChatToolCall[] | null;
  tool_call_id: string | null;
  tool_name: string | null;
  partial: boolean;
  cancelled: boolean;
  error: string | null;
  cost_usd: number | null;
  model_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ChatMessageListResponse {
  items: ChatMessage[];
  total: number;
}

export async function listChatMessages(
  runId: string,
): Promise<ChatMessageListResponse> {
  return api(`${BASE}/api/runs/${encodeURIComponent(runId)}/chat/messages`);
}

export async function createChatTurn(
  runId: string,
  text: string,
): Promise<{ turn_id: string }> {
  return api(`${BASE}/api/runs/${encodeURIComponent(runId)}/chat/turns`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function cancelChatTurn(
  runId: string,
  turnId: string,
): Promise<{ ok: true }> {
  return api(
    `${BASE}/api/runs/${encodeURIComponent(runId)}/chat/turns/${encodeURIComponent(turnId)}`,
    { method: "DELETE" },
  );
}
