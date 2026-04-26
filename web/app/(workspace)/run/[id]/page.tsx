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
  const stream = useRunStream(terminalStatus ? undefined : runId);
  const cancel = useCancelRun();

  const isRunning = detail.data?.status === "running" && !stream.done;
  const streamDone = stream.done || terminalStatus;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto grid gap-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-1">
            <span className="font-num">{detail.data?.ticker ?? "…"}</span>{" "}
            <span className="text-text-3 text-sm">
              {detail.data?.analysis_date}
            </span>
          </h1>
          <p className="text-xs text-text-3 mt-1">
            {detail.data?.status ?? "loading"} · run {runId.slice(0, 8)}
          </p>
        </div>
        {isRunning && (
          <Button
            variant="outline"
            onClick={() => cancel.mutate(runId)}
            disabled={cancel.isPending}
          >
            Cancel
          </Button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <ProgressGauge step={stream.step} total={stream.total} />
            {stream.error && (
              <p className="text-xs text-signal-sell">{stream.error}</p>
            )}
            {detail.data?.error && (
              <p className="text-xs text-signal-sell">{detail.data.error}</p>
            )}
            {(stream.cancelled || detail.data?.status === "cancelled") && (
              <p className="text-xs text-signal-hold">Cancelled</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle>Agent stream</CardTitle>
            <select
              aria-label="Agent stream view format"
              className="h-8 rounded-md border border-border-1 bg-bg-1 px-2 text-xs text-text-2 outline-none focus:border-accent"
              value={streamRenderMode}
              onChange={(event) =>
                setStreamRenderMode(
                  event.target.value === "plain" ? "plain" : "markdown",
                )
              }
            >
              <option value="markdown">Markdown</option>
              <option value="plain">Plain</option>
            </select>
          </CardHeader>
          <CardContent className="grid gap-2 max-h-[60vh] overflow-y-auto">
            {stream.messages.length === 0 &&
              (terminalStatus ? (
                <p className="text-xs text-text-3">Analysis finished.</p>
              ) : (
                <p className="text-xs text-text-3">Waiting for agents…</p>
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
