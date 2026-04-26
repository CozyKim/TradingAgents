import { api } from "./api";

export interface SchedulePreset {
  analysts: string[];
  debate_rounds: number;
  llm_provider?: string | null;
  llm_deep_model?: string | null;
  llm_quick_model?: string | null;
}

export interface Schedule {
  id: number;
  name: string;
  ticker: string;
  cron_expr: string;
  timezone: string;
  preset: SchedulePreset;
  active: boolean;
  last_run: string | null;
  next_run: string | null;
  source: "user" | "holding";
  holding_id: number | null;
  created_at: string;
}

export interface ScheduleListResponse {
  items: Schedule[];
}

export interface ScheduleCreatePayload {
  name: string;
  ticker: string;
  cron_expr: string;
  timezone?: string;
  preset: SchedulePreset;
  active?: boolean;
}

export interface ScheduleUpdatePayload {
  name?: string;
  cron_expr?: string;
  timezone?: string;
  preset?: SchedulePreset;
  active?: boolean;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function listSchedules(): Promise<ScheduleListResponse> {
  return api(`${BASE}/api/schedules`);
}

export async function createSchedule(p: ScheduleCreatePayload): Promise<Schedule> {
  return api(`${BASE}/api/schedules`, {
    method: "POST",
    body: JSON.stringify(p),
  });
}

export async function updateSchedule(
  id: number,
  p: ScheduleUpdatePayload,
): Promise<Schedule> {
  return api(`${BASE}/api/schedules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(p),
  });
}

export async function deleteSchedule(id: number): Promise<void> {
  return api(`${BASE}/api/schedules/${id}`, { method: "DELETE" });
}

export async function runScheduleNow(id: number): Promise<{ run_id: string }> {
  return api(`${BASE}/api/schedules/${id}/run`, { method: "POST" });
}
