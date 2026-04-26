"use client";
import { VerdictCard } from "@/components/analysis/verdict-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRun } from "@/hooks/use-runs";
import type { Decision as RunDecision } from "@/lib/runs";

const REPORT_FIELDS = [
  ["market_report", "Market"],
  ["sentiment_report", "Sentiment"],
  ["news_report", "News"],
  ["fundamentals_report", "Fundamentals"],
  ["investment_plan", "Researcher Verdict"],
  ["trader_investment_plan", "Trader Plan"],
  ["final_trade_decision", "Final Decision"],
] as const;

export function CompareColumn({ runId }: { runId: string }) {
  const q = useRun(runId);
  if (q.isLoading) return <p className="text-xs text-text-3">Loading…</p>;
  if (q.error || !q.data)
    return (
      <p className="text-xs text-signal-sell">
        {(q.error as Error)?.message ?? "Run not found"}
      </p>
    );
  const a = q.data;
  const state = (a.final_state ?? {}) as Record<string, string | undefined>;
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
      {REPORT_FIELDS.map(([key, label]) => {
        const value = state[key];
        if (!value) return null;
        return (
          <Card key={key}>
            <CardHeader>
              <CardTitle>{label}</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-[11px] text-text-2 whitespace-pre-wrap font-sans leading-relaxed">
                {value}
              </pre>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
