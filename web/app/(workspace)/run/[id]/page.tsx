"use client";
import { useParams } from "next/navigation";

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
  const detail = useRun(runId);
  const stream = useRunStream(runId);
  const cancel = useCancelRun();

  const isRunning = detail.data?.status === "running" && !stream.done;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto grid gap-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-1">
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
            {stream.cancelled && (
              <p className="text-xs text-signal-hold">Cancelled</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agent stream</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 max-h-[60vh] overflow-y-auto">
            {stream.messages.length === 0 && (
              <p className="text-xs text-text-3">Waiting for agents…</p>
            )}
            {stream.messages.map((m) => (
              <AgentCard key={m.seq} role={m.role} text={m.text} />
            ))}
          </CardContent>
        </Card>
      </div>

      <VerdictCard
        decision={(stream.decision ?? detail.data?.decision ?? null) as RunDecision | null}
        confidence={stream.confidence ?? detail.data?.confidence ?? null}
        preliminary={!stream.done}
      />
    </div>
  );
}
