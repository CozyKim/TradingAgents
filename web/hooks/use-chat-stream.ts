"use client";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { openChatStream } from "@/lib/chat-sse";

export interface StreamingToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done" | "failed";
  result?: unknown;
}

export interface ChatStreamState {
  tokensByBlock: Record<number, string>;
  toolCalls: StreamingToolCall[];
  done: boolean;
  cancelled: boolean;
  error: string | null;
  cost: number | null;
  model: string | null;
}

const EMPTY: ChatStreamState = {
  tokensByBlock: {},
  toolCalls: [],
  done: false,
  cancelled: false,
  error: null,
  cost: null,
  model: null,
};

export function useChatStream(runId: string, turnId: string | null) {
  const qc = useQueryClient();
  const [state, setState] = useState<ChatStreamState>(EMPTY);
  const closeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!turnId) {
      setState(EMPTY);
      return;
    }
    setState(EMPTY);
    closeRef.current = openChatStream(runId, turnId, {
      onEvent: (type, data) => {
        setState((s) => {
          if (type === "token") {
            const d = data as { text: string; block_index: number };
            const next = { ...s.tokensByBlock };
            next[d.block_index] = (next[d.block_index] ?? "") + d.text;
            return { ...s, tokensByBlock: next };
          }
          if (type === "tool_call") {
            const d = data as {
              id: string;
              name: string;
              args: Record<string, unknown>;
            };
            return {
              ...s,
              toolCalls: [...s.toolCalls, { ...d, status: "running" }],
            };
          }
          if (type === "tool_result") {
            const d = data as {
              tool_call_id: string;
              ok: boolean;
              content_blocks: unknown;
            };
            return {
              ...s,
              toolCalls: s.toolCalls.map((t) =>
                t.id === d.tool_call_id
                  ? {
                      ...t,
                      status: d.ok ? "done" : "failed",
                      result: d.content_blocks,
                    }
                  : t,
              ),
            };
          }
          if (type === "done") {
            const d = data as { cost_usd: number | null; model: string | null };
            return { ...s, done: true, cost: d.cost_usd, model: d.model };
          }
          if (type === "error") {
            const d = data as { message: string };
            return { ...s, done: true, error: d.message };
          }
          if (type === "cancelled") {
            return { ...s, done: true, cancelled: true };
          }
          return s;
        });
      },
      onClose: () =>
        qc.invalidateQueries({ queryKey: ["chat-messages", runId] }),
    });
    return () => closeRef.current?.();
  }, [runId, turnId, qc]);

  return state;
}
