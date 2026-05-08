"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useChatMessages } from "@/hooks/use-chat-messages";
import { useChatStream } from "@/hooks/use-chat-stream";
import {
  useCancelChatTurn,
  useCreateChatTurn,
} from "@/hooks/use-create-chat-turn";

import { ChatInput } from "./chat-input";
import { ChatMessageCard } from "./chat-message";

const STREAMING_PLACEHOLDER_ID = -1;

export function ChatSection({ runId }: { runId: string }) {
  const messagesQ = useChatMessages(runId);
  const create = useCreateChatTurn(runId);
  const cancel = useCancelChatTurn(runId);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const stream = useChatStream(runId, activeTurnId);

  const isStreaming = !!activeTurnId && !stream.done;

  const submitNew = (text: string) => {
    create.mutate(text, {
      onSuccess: ({ turn_id }) => setActiveTurnId(turn_id),
    });
  };

  const cancelNow = () => {
    if (activeTurnId) cancel.mutate(activeTurnId);
  };

  const streamingText = Object.values(stream.tokensByBlock).join("");

  return (
    <Card>
      <CardHeader>
        <CardTitle>이 분석에 대해 묻기</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid max-h-[60vh] gap-2 overflow-y-auto">
          {messagesQ.data?.items.map((m) => (
            <ChatMessageCard key={m.id} msg={m} />
          ))}
          {isStreaming && activeTurnId && (
            <ChatMessageCard
              msg={{
                id: STREAMING_PLACEHOLDER_ID,
                analysis_id: 0,
                turn_id: activeTurnId,
                sequence: Number.MAX_SAFE_INTEGER,
                role: "assistant",
                content_blocks: [],
                tool_calls: null,
                tool_call_id: null,
                tool_name: null,
                partial: false,
                cancelled: false,
                error: null,
                cost_usd: null,
                model_id: null,
                created_at: new Date().toISOString(),
                completed_at: null,
              }}
              streamingToolCalls={stream.toolCalls}
              streamingText={streamingText}
              cost={stream.cost}
              model={stream.model}
            />
          )}
          {stream.error && !isStreaming && (
            <p className="text-xs text-signal-sell">
              응답이 중간에 끊겼어요 · {stream.error}
            </p>
          )}
        </div>
        <ChatInput
          disabled={false}
          isStreaming={isStreaming}
          onSubmit={submitNew}
          onCancel={cancelNow}
        />
      </CardContent>
    </Card>
  );
}
