import { api } from "./api";

export interface NotificationSettings {
  telegram_bot_token_set: boolean;
  telegram_chat_id: string | null;
  alert_on_signal_change: boolean;
  alert_on_run_completed: boolean;
  alert_on_run_failed: boolean;
  alert_on_schedule_failed: boolean;
  confidence_change_threshold: number | null;
}

export type NotificationSettingsUpdate = Partial<{
  telegram_bot_token: string;
  telegram_chat_id: string;
  alert_on_signal_change: boolean;
  alert_on_run_completed: boolean;
  alert_on_run_failed: boolean;
  alert_on_schedule_failed: boolean;
  confidence_change_threshold: number;
}>;

export interface TelegramTestResponse {
  ok: boolean;
  bot_username: string | null;
  error: string | null;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function fetchNotificationSettings(): Promise<NotificationSettings> {
  return api<NotificationSettings>(`${BASE}/api/settings/notifications`);
}

export async function updateNotificationSettings(
  patch: NotificationSettingsUpdate,
): Promise<NotificationSettings> {
  return api<NotificationSettings>(`${BASE}/api/settings/notifications`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export async function testTelegram(payload: {
  telegram_bot_token?: string;
  telegram_chat_id?: string;
}): Promise<TelegramTestResponse> {
  return api<TelegramTestResponse>(`${BASE}/api/settings/notifications/test`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
