"use client";

import { MarkdownText } from "@/components/analysis/markdown-text";
import { Card, CardContent } from "@/components/ui/card";
import type { StreamingToolCall } from "@/hooks/use-chat-stream";
import type { ChatMessage as ChatMessageT } from "@/lib/chat";

import { ChatToolCall } from "./chat-tool-call";

interface ChatMessageCardProps {
  msg: ChatMessageT;
  streamingToolCalls?: StreamingToolCall[];
  streamingText?: string;
  cost?: number | null;
  model?: string | null;
}

export function ChatMessageCard({
  msg,
  streamingToolCalls,
  streamingText,
  cost,
  model,
}: ChatMessageCardProps) {
  const text =
    streamingText !== undefined
      ? streamingText
      : (msg.content_blocks.find((b) => b.type === "text")?.text ?? "");

  const toolCalls: StreamingToolCall[] =
    streamingToolCalls ??
    (msg.tool_calls ?? []).map((tc) => ({
      id: tc.id,
      name: tc.name,
      args: tc.args,
      status: "done" as const,
    }));

  const displayCost = cost ?? msg.cost_usd;
  const displayModel = model ?? msg.model_id;

  return (
    <Card>
      <CardContent className="grid gap-2 py-3">
        <div className="text-[11px] font-semibold text-text-3">
          {msg.role === "user" ? "🧑 사용자" : "🤖 어시스턴트"}
        </div>
        {toolCalls.length > 0 && (
          <div className="grid gap-1.5">
            {toolCalls.map((tc) => (
              <ChatToolCall key={tc.id} call={tc} />
            ))}
          </div>
        )}
        {text && (
          <MarkdownText className="text-[13px] text-text-2" text={text} />
        )}
        {msg.partial && msg.error && (
          <p className="text-xs text-signal-sell">
            응답이 중간에 끊겼어요 · {msg.error}
          </p>
        )}
        {msg.cancelled && (
          <p className="text-xs text-text-3">중지됨</p>
        )}
        {displayModel && (
          <p className="text-[10px] text-text-3">
            {displayModel}
            {displayCost != null ? ` · $${displayCost.toFixed(4)}` : ""}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
