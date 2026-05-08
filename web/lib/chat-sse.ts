export type ChatSseHandlers = {
  onEvent?: (type: string, data: unknown) => void;
  onError?: (err: Event) => void;
  onClose?: () => void;
};

const TYPES = [
  "token",
  "tool_call",
  "tool_result",
  "done",
  "error",
  "cancelled",
  "close",
] as const;

export function openChatStream(
  runId: string,
  turnId: string,
  handlers: ChatSseHandlers,
): () => void {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const url = `${base}/api/runs/${encodeURIComponent(runId)}/chat/turns/${encodeURIComponent(turnId)}/stream`;
  const es = new EventSource(url, { withCredentials: true });

  for (const t of TYPES) {
    es.addEventListener(t, (raw) => {
      let parsed: unknown = null;
      try {
        parsed = JSON.parse((raw as MessageEvent).data);
      } catch {
        parsed = (raw as MessageEvent).data;
      }
      handlers.onEvent?.(t, parsed);
      if (t === "close") {
        es.close();
        handlers.onClose?.();
      }
    });
  }
  es.onerror = (e) => handlers.onError?.(e);

  return () => es.close();
}
