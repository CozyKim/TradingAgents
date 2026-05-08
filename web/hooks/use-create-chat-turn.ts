"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { cancelChatTurn, createChatTurn } from "@/lib/chat";

export function useCreateChatTurn(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => createChatTurn(runId, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-messages", runId] }),
  });
}

export function useCancelChatTurn(runId: string) {
  return useMutation({
    mutationFn: (turnId: string) => cancelChatTurn(runId, turnId),
  });
}
