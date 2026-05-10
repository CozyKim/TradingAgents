"use client";
import { formatPrice, useCurrency, type CurrencyCtx } from "@/lib/currency";
import { cn } from "@/lib/utils";
import type { PricePoint } from "@/lib/prices";

interface OhlcHeaderProps {
  current: PricePoint | null;
  prevClose: number | null;
}

function pctText(value: number, base: number): string {
  if (!base) return "0.00%";
  return (((value - base) / base) * 100).toFixed(2) + "%";
}

function pctClass(value: number, base: number): string {
  if (!base || value === base) return "text-text-3";
  return value > base ? "text-signal-buy" : "text-signal-sell";
}

function Field({
  label,
  value,
  base,
  ctx,
}: {
  label: string;
  value: number;
  base: number | null;
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">;
}) {
  const hasBase = base != null;
  return (
    <div className="flex items-baseline gap-1.5 font-mono text-2xs">
      <span className="text-text-3">{label}</span>
      <span className="tabular-nums text-text-1">
        {formatPrice(value, ctx)}
      </span>
      {hasBase && (
        <span className={cn("tabular-nums", pctClass(value, base!))}>
          ({value >= base! ? "+" : ""}
          {pctText(value, base!)})
        </span>
      )}
    </div>
  );
}

export function OhlcHeader({ current, prevClose }: OhlcHeaderProps) {
  const ctx = useCurrency();
  if (!current) return <div className="h-6" />;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <Field label="시가" value={current.open} base={prevClose} ctx={ctx} />
      <Field label="고가" value={current.high} base={prevClose} ctx={ctx} />
      <Field label="저가" value={current.low} base={prevClose} ctx={ctx} />
      <Field label="종가" value={current.close} base={prevClose} ctx={ctx} />
    </div>
  );
}
