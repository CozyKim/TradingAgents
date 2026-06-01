"use client";
import { useCurrency, formatPrice, type Currency } from "@/lib/currency";
import { cn } from "@/lib/utils";

export function PnLCell({
  qty,
  avgCost,
  lastPrice,
  sourceCurrency = "USD",
}: {
  qty: number;
  avgCost: number;
  lastPrice: number | null;
  /** 평단가·현재가의 원본 통화(종목 거래소 기준). 둘은 같은 종목이라 통화가 일치한다. */
  sourceCurrency?: Currency;
}) {
  const ctx = useCurrency();
  if (lastPrice == null)
    return <span className="text-text-3 font-mono text-xs">—</span>;
  const cost = qty * avgCost;
  const value = qty * lastPrice;
  const pnl = value - cost;
  const pct = cost > 0 ? (pnl / cost) * 100 : 0;
  const cls = pnl >= 0 ? "text-pos" : "text-neg";
  return (
    <span className={cn("font-mono text-xs tabular-nums", cls)}>
      {formatPrice(pnl, sourceCurrency, ctx, { signed: true })} ({pct >= 0 ? "+" : ""}
      {pct.toFixed(1)}%)
    </span>
  );
}
