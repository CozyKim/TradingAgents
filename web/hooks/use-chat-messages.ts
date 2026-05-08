"use client";
import { useQuery } from "@tanstack/react-query";

import { listChatMessages, type ChatMessageListResponse } from "@/lib/chat";

export function useChatMessages(runId: string) {
  return useQuery<ChatMessageListResponse>({
    queryKey: ["chat-messages", runId],
    queryFn: () => listChatMessages(runId),
    enabled: !!runId,
  });
}
