"use client";
import { useParams } from "next/navigation";

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

export default function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const q = useRun(id);

  if (q.isLoading) return <p className="p-6 text-xs text-text-3">Loading…</p>;
  if (q.error || !q.data)
    return (
      <p className="p-6 text-xs text-signal-sell">
        {(q.error as Error)?.message ?? "Run not found"}
      </p>
    );

  const a = q.data;
  const state = (a.final_state ?? {}) as Record<string, string | undefined>;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto grid gap-4">
      <div>
        <h1 className="text-xl font-bold text-text-1">
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
        {REPORT_FIELDS.map(([key, label]) => {
          const value = state[key];
          if (!value) return null;
          return (
            <Card key={key}>
              <CardHeader>
                <CardTitle>{label}</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs text-text-2 whitespace-pre-wrap font-sans leading-relaxed">
                  {value}
                </pre>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
