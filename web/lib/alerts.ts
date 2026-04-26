import { api } from "./api";

export type AlertType =
  | "signal_change"
  | "confidence_change"
  | "run_completed"
  | "run_failed"
  | "schedule_failed";

export interface Alert {
  id: number;
  type: AlertType;
  ticker: string | null;
  analysis_id: number | null;
  schedule_id: number | null;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string;
}

export interface AlertListResponse {
  items: Alert[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertFilter {
  type?: AlertType;
  ticker?: string;
  read?: boolean;
  page?: number;
  page_size?: number;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function listAlerts(
  filter: AlertFilter = {},
): Promise<AlertListResponse> {
  const params = new URLSearchParams();
  if (filter.type) params.set("type", filter.type);
  if (filter.ticker) params.set("ticker", filter.ticker);
  if (filter.read !== undefined) params.set("read", String(filter.read));
  params.set("page", String(filter.page ?? 1));
  params.set("page_size", String(filter.page_size ?? 20));
  return api<AlertListResponse>(`${BASE}/api/alerts?${params.toString()}`);
}

export async function fetchUnreadCount(): Promise<{ unread: number }> {
  return api<{ unread: number }>(`${BASE}/api/alerts/unread-count`);
}

export async function markAlertRead(id: number): Promise<void> {
  await api<{ ok: boolean }>(`${BASE}/api/alerts/${id}/read`, {
    method: "POST",
  });
}

export async function markAllAlertsRead(): Promise<{ marked: number }> {
  return api<{ marked: number }>(`${BASE}/api/alerts/read-all`, {
    method: "POST",
  });
}
