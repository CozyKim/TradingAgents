"use client";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AgentCard } from "@/components/analysis/agent-card";
import { ProgressGauge } from "@/components/analysis/progress-gauge";
import { VerdictCard } from "@/components/analysis/verdict-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCancelRun, useRun } from "@/hooks/use-runs";
import { useRunStream } from "@/hooks/use-run-stream";
import type { Decision as RunDecision } from "@/lib/runs";

const STATUS_LABEL: Record<string, string> = {
  running: "분석 중",
  completed: "완료",
  failed: "실패",
  cancelled: "취소됨",
  pending: "대기 중",
};

const STATUS_TONE: Record<string, string> = {
  running: "bg-accent-muted text-accent",
  completed: "bg-signal-buy/10 text-signal-buy",
  failed: "bg-signal-sell/10 text-signal-sell",
  cancelled: "bg-text-3/15 text-text-2",
  pending: "bg-bg-2 text-text-3",
};

export default function RunLivePage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const [streamRenderMode, setStreamRenderMode] = useState<
    "markdown" | "plain"
  >("markdown");
  const detail = useRun(runId);
  const terminalStatus =
    detail.data?.status === "completed" ||
    detail.data?.status === "failed" ||
    detail.data?.status === "cancelled";
  const stream = useRunStream(runId);
  const cancel = useCancelRun();

  const isRunning = detail.data?.status === "running" && !stream.done;
  const streamDone = stream.done || terminalStatus;
  const status = detail.data?.status ?? "pending";

  return (
    <div className="mx-auto grid w-full max-w-screen-xl gap-4 px-4 py-5 md:px-8 md:py-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-num text-[26px] font-extrabold leading-none tracking-[-0.03em] text-text-1 md:text-[30px]">
              {detail.data?.ticker ?? "…"}
            </h1>
            <span className="text-[14px] font-semibold tracking-[-0.01em] text-text-3">
              {detail.data?.analysis_date}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] font-bold ${
                STATUS_TONE[status] ?? STATUS_TONE.pending
              }`}
            >
              {status === "running" && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              )}
              {STATUS_LABEL[status] ?? status}
            </span>
            <span className="font-num text-[11.5px] tracking-[-0.01em] text-text-3">
              run · {runId.slice(0, 8)}
            </span>
          </div>
        </div>
        {isRunning && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancel.mutate(runId)}
            disabled={cancel.isPending}
          >
            취소
          </Button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>진행 상태</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <ProgressGauge
              step={stream.step}
              total={stream.total}
              phase={stream.phase}
              phaseLabel={stream.phaseLabel}
            />
            {stream.error && (
              <p className="text-[12.5px] font-semibold text-signal-sell">
                {stream.error}
              </p>
            )}
            {detail.data?.error && (
              <p className="text-[12.5px] font-semibold text-signal-sell">
                {detail.data.error}
              </p>
            )}
            {(stream.cancelled || detail.data?.status === "cancelled") && (
              <p className="text-[12.5px] font-semibold text-text-3">
                분석이 취소되었습니다.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle>에이전트 스트림</CardTitle>
            <select
              aria-label="에이전트 스트림 보기 형식"
              className="h-9 rounded-lg bg-bg-2 px-3 text-[12.5px] font-semibold text-text-2 ring-1 ring-inset ring-transparent transition-colors focus:bg-bg-1 focus:outline-none focus:ring-accent/40"
              value={streamRenderMode}
              onChange={(event) =>
                setStreamRenderMode(
                  event.target.value === "plain" ? "plain" : "markdown",
                )
              }
            >
              <option value="markdown">마크다운</option>
              <option value="plain">일반 텍스트</option>
            </select>
          </CardHeader>
          <CardContent className="grid max-h-[60vh] min-w-0 gap-2.5 overflow-y-auto overflow-x-hidden">
            {stream.messages.length === 0 &&
              (terminalStatus ? (
                <p className="text-[13px] text-text-3">분석이 완료되었어요.</p>
              ) : (
                <p className="text-[13px] text-text-3">
                  에이전트가 작업을 시작하기를 기다리는 중…
                </p>
              ))}
            {stream.messages.map((m) => (
              <AgentCard
                key={m.seq}
                role={m.role}
                text={m.text}
                renderMode={streamRenderMode}
              />
            ))}
          </CardContent>
        </Card>
      </div>

      <VerdictCard
        decision={(stream.decision ?? detail.data?.decision ?? null) as RunDecision | null}
        confidence={stream.confidence ?? detail.data?.confidence ?? null}
        preliminary={!streamDone}
      />
    </div>
  );
}
