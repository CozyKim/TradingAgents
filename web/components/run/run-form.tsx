"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TickerCombobox } from "@/components/ui/ticker-combobox";
import { useCreateRun } from "@/hooks/use-runs";
import { Analyst, VALID_ANALYSTS } from "@/lib/runs";
import { todayKST } from "@/lib/datetime";
import { cn } from "@/lib/utils";

const today = () => todayKST();

const ANALYST_LABELS: Record<Analyst, string> = {
  market: "시장",
  social: "소셜",
  news: "뉴스",
  fundamentals: "펀더멘털",
};

export function RunForm() {
  const router = useRouter();
  const create = useCreateRun();

  const [ticker, setTicker] = useState("");
  const [analysisDate, setAnalysisDate] = useState(today());
  const [analysts, setAnalysts] = useState<Analyst[]>([...VALID_ANALYSTS]);
  const [debateRounds, setDebateRounds] = useState(1);

  const toggle = (a: Analyst) =>
    setAnalysts((cur) => (cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a]));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim() || analysts.length === 0) return;
    const { run_id } = await create.mutateAsync({
      ticker: ticker.trim().toUpperCase(),
      analysis_date: analysisDate,
      analysts,
      debate_rounds: debateRounds,
    });
    router.push(`/run/${run_id}`);
  };

  return (
    <form onSubmit={onSubmit} className="grid gap-4">
      <section className="rounded-2xl bg-bg-1 p-5 shadow-card">
        <div className="grid gap-2">
          <Label htmlFor="ticker">티커</Label>
          <TickerCombobox
            id="ticker"
            value={ticker}
            onChange={setTicker}
            placeholder="예: AAPL 또는 애플"
            required
          />
        </div>

        <div className="mt-4 grid gap-2">
          <Label htmlFor="date">분석 기준일</Label>
          <Input
            id="date"
            type="date"
            value={analysisDate}
            onChange={(e) => setAnalysisDate(e.target.value)}
            required
          />
        </div>
      </section>

      <section className="rounded-2xl bg-bg-1 p-5 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <Label>애널리스트</Label>
          <span className="text-[12px] font-semibold text-text-3">
            {analysts.length}/{VALID_ANALYSTS.length} 선택
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {VALID_ANALYSTS.map((a) => {
            const on = analysts.includes(a);
            return (
              <button
                key={a}
                type="button"
                onClick={() => toggle(a)}
                className={cn(
                  "toss-press flex items-center justify-between rounded-xl px-4 py-3 text-left text-[14px] font-bold tracking-[-0.01em] transition-colors",
                  on
                    ? "bg-accent-muted text-accent ring-1 ring-inset ring-accent/30"
                    : "bg-bg-2 text-text-2 ring-1 ring-inset ring-transparent hover:bg-bg-0",
                )}
                aria-pressed={on}
              >
                <span>{ANALYST_LABELS[a]}</span>
                <span
                  className={cn(
                    "inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold",
                    on ? "bg-accent text-white" : "bg-bg-1 text-text-3",
                  )}
                  aria-hidden
                >
                  {on ? "✓" : ""}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl bg-bg-1 p-5 shadow-card">
        <Label htmlFor="rounds">토론 라운드</Label>
        <div className="mt-3 flex items-center justify-between gap-4">
          <button
            type="button"
            onClick={() => setDebateRounds((n) => Math.max(1, n - 1))}
            className="toss-press flex h-11 w-11 items-center justify-center rounded-xl bg-bg-2 text-[20px] font-bold text-text-1 hover:bg-bg-0"
            aria-label="감소"
          >
            −
          </button>
          <div className="flex flex-1 flex-col items-center">
            <span className="font-num text-[28px] font-extrabold tracking-[-0.03em] text-text-1">
              {debateRounds}
            </span>
            <span className="text-[11.5px] font-semibold text-text-3">
              1 ~ 5 라운드
            </span>
          </div>
          <button
            type="button"
            onClick={() => setDebateRounds((n) => Math.min(5, n + 1))}
            className="toss-press flex h-11 w-11 items-center justify-center rounded-xl bg-bg-2 text-[20px] font-bold text-text-1 hover:bg-bg-0"
            aria-label="증가"
          >
            +
          </button>
        </div>
        <input
          id="rounds"
          type="hidden"
          value={debateRounds}
          readOnly
        />
      </section>

      {create.error && (
        <div className="rounded-xl bg-signal-sell/10 px-4 py-3 text-[13px] font-semibold text-signal-sell">
          {(create.error as Error).message}
        </div>
      )}

      <Button
        type="submit"
        size="lg"
        disabled={create.isPending || !ticker.trim() || analysts.length === 0}
        className="w-full"
      >
        {create.isPending ? "분석 시작 중…" : "분석 실행하기"}
      </Button>
    </form>
  );
}
