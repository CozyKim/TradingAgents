"use client";

import type { StreamingToolCall } from "@/hooks/use-chat-stream";

const STATUS_ICON: Record<StreamingToolCall["status"], string> = {
  running: "🌀",
  done: "✓",
  failed: "❌",
};

export function ChatToolCall({ call }: { call: StreamingToolCall }) {
  return (
    <details className="rounded-md border border-border-1 bg-bg-2 px-3 py-2 text-xs text-text-2">
      <summary className="cursor-pointer select-none flex items-center gap-2">
        <span className={call.status === "failed" ? "text-signal-sell" : ""}>
          {STATUS_ICON[call.status]}
        </span>
        <span className="font-mono">
          {call.name}({Object.keys(call.args).join(", ")})
        </span>
        {call.status === "running" && (
          <span className="text-text-3">실행 중…</span>
        )}
      </summary>
      <pre className="mt-2 whitespace-pre-wrap text-[11px] text-text-3">
{JSON.stringify({ args: call.args, result: call.result }, null, 2)}
      </pre>
    </details>
  );
}
