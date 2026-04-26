"use client";
import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PortfolioSignals } from "@/components/dashboard/portfolio-signals";
import { useHoldings } from "@/hooks/use-holdings";
import { useRunList } from "@/hooks/use-runs";
import { useSchedules } from "@/hooks/use-schedules";
import { getPriceHistory } from "@/lib/prices";
import { RunListItem } from "@/lib/runs";

export default function DashboardPage() {
  const { data: holdings } = useHoldings();
  const { data: schedules } = useSchedules();
  const { data: runs } = useRunList(
    { page_size: 100 },
    { refetchInterval: 5000, staleTime: 0 },
  );
  const [prices, setPrices] = useState<Record<string, number | null>>({});

  useEffect(() => {
    if (!holdings?.items) return;
    let cancelled = false;
    (async () => {
      const out: Record<string, number | null> = {};
      await Promise.all(
        holdings.items.map(async (h) => {
          try {
            const r = await getPriceHistory(h.ticker, 5);
            out[h.ticker] = r.last_close;
          } catch {
            out[h.ticker] = null;
          }
        }),
      );
      if (!cancelled) setPrices(out);
    })();
    return () => {
      cancelled = true;
    };
  }, [holdings?.items]);

  const totals = useMemo(() => {
    let value = 0;
    let cost = 0;
    let priced = 0;
    for (const h of holdings?.items ?? []) {
      cost += h.qty * h.avg_cost;
      const last = prices[h.ticker];
      if (last != null) {
        value += h.qty * last;
        priced += 1;
      }
    }
    const positions = holdings?.items.length ?? 0;
    const fullyPriced = priced === positions && positions > 0;
    const pnl = fullyPriced ? value - cost : null;
    return {
      value: fullyPriced ? value : null,
      cost,
      pnl,
      positions,
    };
  }, [holdings?.items, prices]);

  const latestByTicker = useMemo(() => {
    const out: Record<string, RunListItem | undefined> = {};
    for (const r of runs?.items ?? []) {
      if (!out[r.ticker]) out[r.ticker] = r;
    }
    return out;
  }, [runs?.items]);

  const runningRuns = (runs?.items ?? []).filter((r) => r.status === "running");

  const fmtMoney = (n: number | null) =>
    n == null ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 2 });

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-1 mb-1">Dashboard</h1>
        <p className="text-xs text-text-3">Personal workbench</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="Portfolio value"
          value={fmtMoney(totals.value)}
          delta={`cost basis ${fmtMoney(totals.cost)}`}
        />
        <MetricCard
          label="Unrealized P&L"
          value={
            totals.pnl == null
              ? "—"
              : `${totals.pnl >= 0 ? "+" : ""}${totals.pnl.toFixed(2)}`
          }
          tone={totals.pnl == null ? "neutral" : totals.pnl >= 0 ? "pos" : "neg"}
        />
        <MetricCard
          label="Positions / Schedules"
          value={`${totals.positions} / ${schedules?.items.length ?? 0}`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Holdings signals</CardTitle>
        </CardHeader>
        <CardContent>
          <PortfolioSignals
            holdings={holdings?.items ?? []}
            latestByTicker={latestByTicker}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Running</CardTitle>
        </CardHeader>
        <CardContent>
          {runningRuns.length === 0 ? (
            <div className="flex flex-col items-start gap-3 py-2">
              <p className="text-sm text-text-2">No analyses running.</p>
              <Link
                href="/run"
                className="inline-flex items-center gap-1 rounded-md border border-border-1 bg-bg-2 px-3 py-1.5 text-xs text-text-1 hover:bg-bg-1 hover:border-border-2"
              >
                + Start a new run
              </Link>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {runningRuns.map((r) => (
                <li
                  key={r.run_id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono">{r.ticker}</span>
                    <span className="text-text-3 text-xs">{r.analysis_date}</span>
                  </div>
                  <Link href={`/run/${r.run_id}`} className="text-accent text-xs">
                    Watch →
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
