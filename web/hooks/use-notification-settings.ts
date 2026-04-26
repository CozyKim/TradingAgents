"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NotificationSettings,
  NotificationSettingsUpdate,
  fetchNotificationSettings,
  testTelegram,
  updateNotificationSettings,
} from "@/lib/notification-settings";

export function useNotificationSettings() {
  return useQuery<NotificationSettings>({
    queryKey: ["settings", "notifications"],
    queryFn: fetchNotificationSettings,
  });
}

export function useUpdateNotificationSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: NotificationSettingsUpdate) =>
      updateNotificationSettings(patch),
    onSuccess: (data) => {
      qc.setQueryData(["settings", "notifications"], data);
    },
  });
}

export function useTestTelegram() {
  return useMutation({
    mutationFn: (payload: {
      telegram_bot_token?: string;
      telegram_chat_id?: string;
    }) => testTelegram(payload),
  });
}
