import { api } from "./api";

export type Decision = "BUY" | "OVERWEIGHT" | "HOLD" | "UNDERWEIGHT" | "SELL";
export type RunStatus = "running" | "completed" | "failed" | "cancelled";

export interface RunListItem {
  run_id: string;
  ticker: string;
  analysis_date: string;
  status: RunStatus;
  decision: Decision | null;
  confidence: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface RunDetail extends RunListItem {
  llm_provider: string;
  llm_deep_model: string;
  llm_quick_model: string;
  debate_rounds: number;
  analysts: string[];
  final_state: Record<string, unknown> | null;
  error: string | null;
  cost_usd: number | null;
}

export interface RunListResponse {
  items: RunListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateRunPayload {
  ticker: string;
  analysis_date: string;
  analysts: string[];
  debate_rounds: number;
  llm_provider?: string;
  llm_deep_model?: string;
  llm_quick_model?: string;
}

export const VALID_ANALYSTS = ["market", "social", "news", "fundamentals"] as const;
export type Analyst = (typeof VALID_ANALYSTS)[number];

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function createRun(payload: CreateRunPayload): Promise<{ run_id: string }> {
  return api(`${BASE}/api/runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listRuns(params: {
  ticker?: string;
  status?: RunStatus;
  decision?: Decision;
  page?: number;
  page_size?: number;
}): Promise<RunListResponse> {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const qs = usp.toString();
  return api(`${BASE}/api/runs${qs ? `?${qs}` : ""}`);
}

export async function getRun(runId: string): Promise<RunDetail> {
  return api(`${BASE}/api/runs/${runId}`);
}

export async function cancelRun(runId: string): Promise<{ ok: boolean }> {
  return api(`${BASE}/api/runs/${runId}`, { method: "DELETE" });
}
