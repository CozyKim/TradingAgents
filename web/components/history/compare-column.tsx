"use client";
import { useState } from "react";

import {
  MarkdownText,
  type TextRenderMode,
} from "@/components/analysis/markdown-text";
import { VerdictCard } from "@/components/analysis/verdict-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRun } from "@/hooks/use-runs";
import { getReportSections } from "@/lib/analysis-reports";
import type { Decision as RunDecision } from "@/lib/runs";

export function CompareColumn({ runId }: { runId: string }) {
  const [reportRenderMode, setReportRenderMode] =
    useState<TextRenderMode>("markdown");
  const q = useRun(runId);
  if (q.isLoading) return <p className="text-xs text-text-3">Loading…</p>;
  if (q.error || !q.data)
    return (
      <p className="text-xs text-signal-sell">
        {(q.error as Error)?.message ?? "Run not found"}
      </p>
    );
  const a = q.data;
  const sections = getReportSections(a.final_state);
  return (
    <div className="space-y-3 min-w-0">
      <div>
        <h2 className="text-base font-bold text-text-1">
          <span className="font-num">{a.ticker}</span>{" "}
          <span className="text-text-3 text-xs">{a.analysis_date}</span>
        </h2>
        <p className="text-[11px] text-text-3">
          {a.status} · deep={a.llm_deep_model} · quick={a.llm_quick_model}
        </p>
      </div>
      <VerdictCard
        decision={a.decision as RunDecision | null}
        confidence={a.confidence}
      />
      {sections.length > 0 && (
        <div className="flex justify-end">
          <select
            aria-label="Saved reports view format"
            className="h-8 rounded-md border border-border-1 bg-bg-1 px-2 text-[11px] text-text-2 outline-none focus:border-accent"
            value={reportRenderMode}
            onChange={(event) =>
              setReportRenderMode(
                event.target.value === "plain" ? "plain" : "markdown",
              )
            }
          >
            <option value="markdown">Markdown</option>
            <option value="plain">Plain</option>
          </select>
        </div>
      )}
      {sections.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Saved Reports</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[11px] text-text-3">
              No saved report content for this run yet.
            </p>
          </CardContent>
        </Card>
      )}
      {sections.map(({ key, label, value }) => (
        <Card key={key}>
          <CardHeader>
            <CardTitle>{label}</CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownText
              className="text-[11px] text-text-2"
              mode={reportRenderMode}
              text={value}
            />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
