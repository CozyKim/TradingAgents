"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateRun } from "@/hooks/use-runs";
import { Analyst, VALID_ANALYSTS } from "@/lib/runs";

const today = () => new Date().toISOString().slice(0, 10);

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
    <Card>
      <CardHeader>
        <CardTitle>New Analysis</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="ticker">Ticker</Label>
            <Input
              id="ticker"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="AAPL"
              className="font-num uppercase"
              required
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="date">Analysis date</Label>
            <Input
              id="date"
              type="date"
              value={analysisDate}
              onChange={(e) => setAnalysisDate(e.target.value)}
              required
            />
          </div>

          <div className="grid gap-1.5">
            <Label>Analysts</Label>
            <div className="grid grid-cols-2 gap-2">
              {VALID_ANALYSTS.map((a) => (
                <label
                  key={a}
                  className="flex items-center gap-2 rounded-md border border-border-1 bg-bg-1 px-3 py-2 cursor-pointer hover:bg-bg-2"
                >
                  <input
                    type="checkbox"
                    checked={analysts.includes(a)}
                    onChange={() => toggle(a)}
                    className="accent-accent"
                  />
                  <span className="text-xs capitalize">{a}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="rounds">Debate rounds</Label>
            <Input
              id="rounds"
              type="number"
              min={1}
              max={5}
              value={debateRounds}
              onChange={(e) => setDebateRounds(Number(e.target.value))}
            />
          </div>

          {create.error && (
            <p className="text-xs text-signal-sell">
              {(create.error as Error).message}
            </p>
          )}

          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Starting…" : "Run"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
