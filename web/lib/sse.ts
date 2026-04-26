import { resolveRunStreamUrl } from "@/lib/sse-url";

export type SseHandlers = {
  onEvent?: (type: string, data: unknown, raw: MessageEvent) => void;
  onError?: (err: Event) => void;
  onClose?: () => void;
};

const TYPES = ["agent_message", "progress", "done", "error", "cancelled", "close"] as const;

export function openRunStream(runId: string, handlers: SseHandlers): () => void {
  const url = resolveRunStreamUrl(runId);
  const es = new EventSource(url, { withCredentials: true });

  for (const t of TYPES) {
    es.addEventListener(t, (raw) => {
      let parsed: unknown = null;
      try {
        parsed = JSON.parse((raw as MessageEvent).data);
      } catch {
        parsed = (raw as MessageEvent).data;
      }
      handlers.onEvent?.(t, parsed, raw as MessageEvent);
      if (t === "close") {
        es.close();
        handlers.onClose?.();
      }
    });
  }
  es.onerror = (e) => handlers.onError?.(e);

  return () => es.close();
}
