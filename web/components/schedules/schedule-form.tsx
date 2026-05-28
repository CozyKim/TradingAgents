"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { TickerCombobox } from "@/components/ui/ticker-combobox";
import { useCreateSchedule } from "@/hooks/use-schedules";
import { CronBuilder } from "./cron-builder";

const ANALYSTS = ["market", "social", "news", "fundamentals"] as const;

const TZ_OPTIONS: { value: string; label: string }[] = [
  { value: "Asia/Seoul", label: "한국 (KST, UTC+9)" },
  { value: "America/New_York", label: "미국 동부 (ET)" },
  { value: "UTC", label: "UTC" },
];

export function ScheduleForm() {
  const router = useRouter();
  // Bridge from /history: ?ticker=AAPL&from_run=<run_id> prefills the
  // ticker chip and shows a one-line breadcrumb back to the source run.
  const search = useSearchParams();
  const prefillTicker = (search.get("ticker") ?? "").toUpperCase();
  const fromRun = search.get("from_run");

  const [name, setName] = useState("");
  const [tickers, setTickers] = useState<string[]>(
    prefillTicker ? [prefillTicker] : [],
  );
  const [tickerDraft, setTickerDraft] = useState("");
  const [cron, setCron] = useState("30 9 * * *");
  const [tz, setTz] = useState("Asia/Seoul");
  const [rounds, setRounds] = useState(1);
  const [analysts, setAnalysts] = useState<string[]>([...ANALYSTS]);
  const m = useCreateSchedule();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (tickers.length === 0) return;
    for (const t of tickers) {
      await m.mutateAsync({
        name: tickers.length === 1 ? name : `${name} (${t})`,
        ticker: t,
        cron_expr: cron,
        timezone: tz,
        preset: { analysts, debate_rounds: rounds },
      });
    }
    router.push("/schedules");
  };

  // 칩 추가 후 항상 setTickerDraft를 통해 부모 value를 변경시켜 combobox key를 다르게
  // 만든다. 중복 티커도 동일 효과를 받도록 timestamp 기반 nonce 사용.
  const [resetNonce, setResetNonce] = useState(0);
  const addTicker = (t: string) => {
    if (!t) return;
    setTickers((cur) => (cur.includes(t) ? cur : [...cur, t]));
    setTickerDraft("");
    setResetNonce((n) => n + 1);
  };

  const removeTicker = (t: string) => {
    setTickers((cur) => cur.filter((x) => x !== t));
  };

  const toggleAnalyst = (a: string) => {
    setAnalysts((cur) =>
      cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a],
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 max-w-xl">
      {fromRun && (
        <div className="rounded-md border border-accent/30 bg-accent-muted px-3 py-2 text-xs text-text-1">
          분석{" "}
          <Link
            href={`/history/${fromRun}`}
            className="font-semibold text-accent hover:underline"
          >
            #{fromRun.slice(0, 8)}
          </Link>
          <span className="text-text-3">에서 시작</span>
        </div>
      )}
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
        <Label htmlFor="tickers">Tickers</Label>
        {tickers.length > 0 ? (
          <div className="mb-2 flex flex-wrap gap-2">
            {tickers.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 rounded-full bg-bg-2 px-3 py-1 text-xs font-bold"
              >
                {t}
                <button
                  type="button"
                  onClick={() => removeTicker(t)}
                  aria-label={`Remove ${t}`}
                  className="text-text-3 hover:text-text-1"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        {/* resetNonce를 매 칩 추가 시마다 증가시켜 remount → 내부 query/error/highlight를
            완전히 리셋. 중복 티커 추가도 동일 처리. setCustomValidity의 query!=value
            체크도 매 remount 시점에 value="", query="" 일치해 통과한다. */}
        <TickerCombobox
          key={`ticker-input-${resetNonce}`}
          id="tickers"
          value={tickerDraft}
          onChange={(t) => {
            if (t) addTicker(t);
            else setTickerDraft("");
          }}
          placeholder="AAPL 또는 애플 (확정 시 칩으로 추가)"
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
        <Label>스케줄</Label>
        <CronBuilder value={cron} timezone={tz} onChange={setCron} />
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
      <Button type="submit" disabled={m.isPending || tickers.length === 0}>
        {m.isPending ? "Creating…" : "Create schedule(s)"}
      </Button>
      {m.error ? <p className="text-xs text-neg">{(m.error as Error).message}</p> : null}
    </form>
  );
}
