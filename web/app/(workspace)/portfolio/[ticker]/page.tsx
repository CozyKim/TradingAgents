"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHoldings } from "@/hooks/use-holdings";
import { useRunList } from "@/hooks/use-runs";
import { usePriceHistory } from "@/hooks/use-price-history";
import { useChartSettings } from "@/hooks/use-chart-settings";
import { CandleChart, type SignalMarker } from "@/components/portfolio/candle-chart";
import { QtyCell, AvgCostCell } from "@/components/portfolio/qty-cell";
import { SignalBadge } from "@/components/shared/signal-badge";
import { useCurrency, formatPrice } from "@/lib/currency";

export default function PortfolioDetail() {
  const params = useParams<{ ticker: string }>();
  const ticker = params.ticker.toUpperCase();
  const { data: holdings } = useHoldings();
  const { data: history } = useRunList({ ticker, page_size: 50 });
  const { data: price, isLoading: priceLoading } = usePriceHistory(ticker, 365);
  const { settings, setSettings, reset } = useChartSettings();
  const ctx = useCurrency();

  const holding = holdings?.items.find((h) => h.ticker === ticker);

  const signals: SignalMarker[] = useMemo(() => {
    if (!history?.items || !price?.points) return [];
    const closeByDate = new Map(price.points.map((p) => [p.date, p.close]));
    const out: SignalMarker[] = [];
    // history.items는 created_at DESC 정렬 — 같은 analysis_date에 대해
    // 가장 먼저 만나는 항목이 최신이므로, 그 이후 중복은 스킵해 최신만 표시한다.
    const seenDates = new Set<string>();
    for (const r of history.items) {
      if (!r.decision) continue;
      if (seenDates.has(r.analysis_date)) continue;
      const c = closeByDate.get(r.analysis_date);
      if (c == null) continue;
      seenDates.add(r.analysis_date);
      out.push({ date: r.analysis_date, decision: r.decision, close: c });
    }
    return out;
  }, [history?.items, price?.points]);

  const last = price?.last_close ?? null;
  const cost = holding ? holding.qty * holding.avg_cost : 0;
  const value = holding && last != null ? holding.qty * last : null;
  const pnl = value != null ? value - cost : null;

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto space-y-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
        <Link href="/portfolio" className="text-xs text-text-3 hover:underline">
          ← back to portfolio
        </Link>
      </div>

      {holding ? (
        <Card>
          <CardContent className="py-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-2xs uppercase tracking-widest text-text-3">
                Quantity
              </div>
              <QtyCell holdingId={holding.id} qty={holding.qty} />

            </div>
            <div>
              <div className="text-2xs uppercase tracking-widest text-text-3">
                Avg cost
              </div>
              <AvgCostCell holdingId={holding.id} avgCost={holding.avg_cost} />
            </div>
            <div>
              <div className="text-2xs uppercase tracking-widest text-text-3">
                Last
              </div>
              <div className="font-mono tabular-nums">
                {formatPrice(last, ctx)}
              </div>
            </div>
            <div>
              <div className="text-2xs uppercase tracking-widest text-text-3">
                P&amp;L
              </div>
              <div
                className={`font-mono tabular-nums ${
                  pnl == null ? "" : pnl >= 0 ? "text-pos" : "text-neg"
                }`}
              >
                {formatPrice(pnl, ctx, { signed: true })}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-text-3">
          Not in portfolio. <Link className="underline" href="/portfolio">Add it</Link>.
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Price</CardTitle>
        </CardHeader>
        {/* 가격축이 카드 우측 패딩 안쪽에 같이 있으면 차트가 좁아 보인다.
            우측 패딩을 줄여 캔들 그림 영역을 가로로 확장. */}
        <CardContent className="pr-1">
          {priceLoading ? (
            <div
              className="h-64 animate-pulse rounded-md border border-border-1 bg-bg-2/40"
              role="status"
              aria-label="Loading prices"
            />
          ) : (
            <CandleChart
              points={price?.points ?? []}
              signals={signals}
              avgCost={holding?.avg_cost}
              settings={settings}
              onSettingsChange={setSettings}
              onSettingsReset={reset}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Analysis history</CardTitle>
        </CardHeader>
        <CardContent>
          {history?.items.length === 0 ? (
            <p className="text-sm text-text-3">No analyses yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {history?.items.map((r) => (
                <li
                  key={r.run_id}
                  className="flex items-center justify-between border border-border-1 rounded-md px-3 py-2"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-text-3 font-mono">
                      {r.analysis_date}
                    </span>
                    {r.decision ? (
                      <SignalBadge decision={r.decision} />
                    ) : (
                      <span className="text-xs text-text-3">{r.status}</span>
                    )}
                    {r.confidence != null && (
                      <span className="text-xs text-text-3 font-mono">
                        conf {r.confidence.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/history/${r.run_id}`}
                    className="text-xs text-accent hover:underline"
                  >
                    Open →
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
