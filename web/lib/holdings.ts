import { api } from "./api";

export interface Holding {
  id: number;
  ticker: string;
  qty: number;
  avg_cost: number;
  monitor_enabled: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface HoldingListResponse {
  items: Holding[];
}

export interface HoldingCreatePayload {
  ticker: string;
  qty: number;
  avg_cost: number;
  notes?: string;
}

export interface HoldingUpdatePayload {
  qty?: number;
  avg_cost?: number;
  monitor_enabled?: boolean;
  notes?: string;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function listHoldings(): Promise<HoldingListResponse> {
  return api(`${BASE}/api/holdings`);
}

export async function createHolding(p: HoldingCreatePayload): Promise<Holding> {
  return api(`${BASE}/api/holdings`, {
    method: "POST",
    body: JSON.stringify(p),
  });
}

export async function updateHolding(
  id: number,
  p: HoldingUpdatePayload,
): Promise<Holding> {
  return api(`${BASE}/api/holdings/${id}`, {
    method: "PATCH",
    body: JSON.stringify(p),
  });
}

export async function deleteHolding(id: number): Promise<void> {
  return api(`${BASE}/api/holdings/${id}`, { method: "DELETE" });
}
