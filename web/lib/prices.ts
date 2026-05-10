import { api } from "./api";

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceHistoryResponse {
  ticker: string;
  points: PricePoint[];
  last_close: number | null;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function getPriceHistory(
  ticker: string,
  days: number = 90,
): Promise<PriceHistoryResponse> {
  return api(
    `${BASE}/api/prices/${encodeURIComponent(ticker)}/history?days=${days}`,
  );
}
