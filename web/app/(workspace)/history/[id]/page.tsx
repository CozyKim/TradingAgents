"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  MarkdownText,
  type TextRenderMode,
} from "@/components/analysis/markdown-text";
import { VerdictCard } from "@/components/analysis/verdict-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRun } from "@/hooks/use-runs";
import { getReportSections } from "@/lib/analysis-reports";
$1\nimport { ChatSection } from \"@/components/chat/chat-section\";

export default function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [reportRenderMode, setReportRenderMode] =
    useState<TextRenderMode>("markdown");
  const q = useRun(id);

  useEffect(() => {
    if (q.data?.status === "running") {
      router.replace(`/run/${id}`);
    }
  }, [q.data?.status, id, router]);

  if (q.isLoading) return <p className="p-6 text-xs text-text-3">Loading…</p>;
  if (q.error || !q.data)
    return (
      <p className="p-6 text-xs text-signal-sell">
        {(q.error as Error)?.message ?? "Run not found"}
      </p>
    );
  if (q.data.status === "running")
    return <p className="p-6 text-xs text-text-3">Redirecting to live view…</p>;

  const a = q.data;
  const sections = getReportSections(a.final_state);

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto grid gap-4">
      <div>
        <h1 className="text-2xl font-bold text-text-1">
          <span className="font-num">{a.ticker}</span>{" "}
          <span className="text-text-3 text-sm">{a.analysis_date}</span>
        </h1>
        <p className="text-xs text-text-3 mt-1">
          {a.status} · {a.llm_provider} · deep={a.llm_deep_model} · quick={a.llm_quick_model}
        </p>
      </div>

      <VerdictCard
        decision={a.decision as RunDecision | null}
        confidence={a.confidence}
      />

      {a.error && (
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs text-signal-sell whitespace-pre-wrap">{a.error}</pre>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3">
        {sections.length > 0 && (
          <div className="flex justify-end">
            <select
              aria-label="Saved reports view format"
              className="h-8 rounded-md border border-border-1 bg-bg-1 px-2 text-xs text-text-2 outline-none focus:border-accent"
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
              <p className="text-xs text-text-3">
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
                className="text-xs text-text-2"
                mode={reportRenderMode}
                text={value}
              />
            </CardContent>
          </Card>
        ))}\n      </div>\n\n      {a.status === \"completed\" ? (\n        <ChatSection runId={id} />\n      ) : (\n        <Card>\n          <CardHeader>\n            <CardTitle>후속 대화</CardTitle>\n          </CardHeader>\n          <CardContent>\n            <p className=\"text-xs text-text-3\">\n              이 분석은 완료되지 않아 후속 대화를 할 수 없어요.\n            </p>\n          </CardContent>\n        </Card>\n      )}\n    </div>
  );
}
