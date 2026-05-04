"use client";
import { useCurrency, formatPrice } from "@/lib/currency";
import { cn } from "@/lib/utils";

export function PnLCell({
  qty,
  avgCost,
  lastPrice,
}: {
  qty: number;
  avgCost: number;
  lastPrice: number | null;
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
      {formatPrice(pnl, ctx, { signed: true })} ({pct >= 0 ? "+" : ""}
      {pct.toFixed(1)}%)
    </span>
  );
}
