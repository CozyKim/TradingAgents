"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useCreateSchedule } from "@/hooks/use-schedules";
import { CronHelper } from "./cron-helper";

const ANALYSTS = ["market", "social", "news", "fundamentals"] as const;

const TZ_OPTIONS: { value: string; label: string }[] = [
  { value: "Asia/Seoul", label: "한국 (KST, UTC+9)" },
  { value: "America/New_York", label: "미국 동부 (ET)" },
  { value: "UTC", label: "UTC" },
];

export function ScheduleForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [tickers, setTickers] = useState("");
  const [cron, setCron] = useState("30 9 * * *");
  const [tz, setTz] = useState("Asia/Seoul");
  const [rounds, setRounds] = useState(1);
  const [analysts, setAnalysts] = useState<string[]>([...ANALYSTS]);
  const m = useCreateSchedule();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const tickerList = tickers
      .split(/[,\s]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    for (const t of tickerList) {
      await m.mutateAsync({
        name: tickerList.length === 1 ? name : `${name} (${t})`,
        ticker: t,
        cron_expr: cron,
        timezone: tz,
        preset: { analysts, debate_rounds: rounds },
      });
    }
    router.push("/schedules");
  };

  const toggleAnalyst = (a: string) => {
    setAnalysts((cur) =>
      cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a],
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 max-w-xl">
      <div>
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Semi-cap weekly"
        />
      </div>
      <div>
        <Label htmlFor="tickers">Tickers (comma or space separated)</Label>
        <Input
          id="tickers"
          required
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
          placeholder="AAPL, NVDA, AMD"
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="tz">Timezone</Label>
        <select
          id="tz"
          value={tz}
          onChange={(e) => setTz(e.target.value)}
          className="bg-bg-1 border border-border-1 rounded-md px-3 py-2 text-sm"
        >
          {TZ_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="cron">Cron ({tz})</Label>
        <Input
          id="cron"
          required
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          className="font-mono"
        />
        <CronHelper value={cron} timezone={tz} onChange={setCron} />
      </div>
      <div>
        <Label>Analysts</Label>
        <div className="flex gap-3 mt-1">
          {ANALYSTS.map((a) => (
            <label key={a} className="flex items-center gap-1 text-xs">
              <Checkbox
                checked={analysts.includes(a)}
                onCheckedChange={() => toggleAnalyst(a)}
              />
              {a}
            </label>
          ))}
        </div>
      </div>
      <div className="w-32">
        <Label htmlFor="rounds">Debate rounds</Label>
        <Input
          id="rounds"
          type="number"
          min="1"
          max="5"
          value={rounds}
          onChange={(e) => setRounds(Number(e.target.value))}
        />
      </div>
      <Button type="submit" disabled={m.isPending}>
        {m.isPending ? "Creating…" : "Create schedule(s)"}
      </Button>
      {m.error ? <p className="text-xs text-neg">{(m.error as Error).message}</p> : null}
    </form>
  );
}
