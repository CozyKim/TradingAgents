"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

interface ChatInputProps {
  disabled: boolean;
  isStreaming: boolean;
  onSubmit: (text: string) => void;
  onCancel?: () => void;
}

export function ChatInput({
  disabled,
  isStreaming,
  onSubmit,
  onCancel,
}: ChatInputProps) {
  const [text, setText] = useState("");

  return (
    <form
      className="sticky bottom-0 grid gap-2 bg-bg-1 pt-2"
      onSubmit={(e) => {
        e.preventDefault();
        const v = text.trim();
        if (!v || disabled || isStreaming) return;
        onSubmit(v);
        setText("");
      }}
    >
      <textarea
        className="min-h-[60px] resize-y rounded-md border border-border-1 bg-bg-2 p-2 text-sm text-text-1 outline-none focus:border-accent disabled:opacity-50"
        maxLength={8000}
        disabled={disabled}
        placeholder={
          disabled
            ? "이 분석은 완료되지 않아 후속 대화를 할 수 없어요."
            : "어떤 점이 궁금하신가요? 가격 흐름·뉴스·근거를 다시 확인할 수 있어요."
        }
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            (e.currentTarget.form as HTMLFormElement).requestSubmit();
          }
        }}
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-text-3">⌘/Ctrl+Enter 로 전송</span>
        <div className="flex gap-2">
          {isStreaming && onCancel && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onCancel}
            >
              중지
            </Button>
          )}
          <Button
            type="submit"
            size="sm"
            disabled={disabled || isStreaming || !text.trim()}
          >
            보내기
          </Button>
        </div>
      </div>
    </form>
  );
}
