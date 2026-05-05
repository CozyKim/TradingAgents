"use client";
import { useMemo } from "react";
import {
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PricePoint } from "@/lib/prices";
import { bollinger, ema, sma } from "@/lib/indicators";
import { ChartSettings } from "@/lib/chart-settings";
import { CHART_CHROME, INDICATOR_COLORS, SIGNAL_MARKER } from "./indicator-colors";
import { useCurrency, formatPrice, type CurrencyCtx } from "@/lib/currency";

export interface SignalMarker {
  date: string;
  decision: "BUY" | "SELL" | "HOLD" | "OVERWEIGHT" | "UNDERWEIGHT";
  close: number;
}

function fmtPriceCtx(
  n: number | null | undefined,
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">,
): string {
  return formatPrice(n, ctx);
}

const SERIES_LABELS: Record<string, string> = {
  close: "Close",
  sma: "SMA",
  ema: "EMA",
  bbMid: "BB mid",
  bbUp: "BB upper",
  bbLo: "BB lower",
};

const SERIES_COLORS: Record<string, string> = {
  close: INDICATOR_COLORS.price,
  sma: INDICATOR_COLORS.sma,
  ema: INDICATOR_COLORS.ema,
  bbMid: INDICATOR_COLORS.bbMid,
  bbUp: INDICATOR_COLORS.bbBand,
  bbLo: INDICATOR_COLORS.bbBand,
};

interface TooltipPayloadEntry {
  dataKey?: string | number;
  value?: number | string | null;
  payload?: Record<string, unknown>;
}

function PriceTooltip({
  active,
  payload,
  label,
  signalsByDate,
  ctx,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string | number;
  signalsByDate: Map<string, SignalMarker>;
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">;
}) {
  if (!active || !payload?.length) return null;
  const dateKey = typeof label === "string" ? label : String(label ?? "");
  const signal = signalsByDate.get(dateKey);
  return (
    <div
      className="rounded-md border border-border-2 bg-bg-1 px-2.5 py-2 text-xs shadow-lg"
      style={{ minWidth: 140 }}
    >
      <div className="mb-1 font-mono text-2xs uppercase tracking-widest text-text-3">
        {dateKey}
      </div>
      <ul className="flex flex-col gap-0.5">
        {payload.map((p) => {
          const key = String(p.dataKey ?? "");
          const value = typeof p.value === "number" ? p.value : null;
          if (value == null) return null;
          return (
            <li
              key={key}
              className="flex items-center justify-between gap-3 font-mono"
            >
              <span className="flex items-center gap-1.5 text-text-2">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: SERIES_COLORS[key] ?? "#a0a0a8" }}
                />
                {SERIES_LABELS[key] ?? key}
              </span>
              <span className="tabular-nums text-text-1">{fmtPriceCtx(value, ctx)}</span>
            </li>
          );
        })}
      </ul>
      {signal && (
        <div className="mt-1.5 flex items-center justify-between border-t border-border-1 pt-1.5">
          <span className="text-text-3 text-2xs uppercase tracking-widest">
            Signal
          </span>
          <span
            className="font-mono text-2xs font-semibold"
            style={{ color: SIGNAL_MARKER[signal.decision].color }}
          >
            {SIGNAL_MARKER[signal.decision].shape} {signal.decision}
          </span>
        </div>
      )}
    </div>
  );
}

function ActiveOverlayLabels({ overlays }: { overlays?: ChartSettings["overlays"] }) {
  const items: { key: string; label: string; color: string }[] = [];
  if (overlays?.sma.on)
    items.push({
      key: "sma",
      label: `SMA${overlays.sma.period}`,
      color: INDICATOR_COLORS.sma,
    });
  if (overlays?.ema.on)
    items.push({
      key: "ema",
      label: `EMA${overlays.ema.period}`,
      color: INDICATOR_COLORS.ema,
    });
  if (overlays?.bollinger.on)
    items.push({
      key: "bb",
      label: `BB${overlays.bollinger.period}/${overlays.bollinger.stddev}`,
      color: INDICATOR_COLORS.bbBand,
    });
  if (items.length === 0) return null;
  return (
    <div className="absolute left-12 top-2 z-10 flex flex-wrap items-center gap-2 font-mono text-2xs uppercase tracking-widest text-text-3">
      {items.map((it) => (
        <span key={it.key} className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: it.color }}
          />
          {it.label}
        </span>
      ))}
    </div>
  );
}

export function PriceChart({
  points,
  signals = [],
  avgCost,
  overlays,
  showXAxis = true,
}: {
  points: PricePoint[];
  signals?: SignalMarker[];
  avgCost?: number;
  overlays?: ChartSettings["overlays"];
  showXAxis?: boolean;
}) {
  const ctx = useCurrency();
  const data = useMemo(() => {
    const closes = points.map((p) => p.close);
    const smaSeries =
      overlays?.sma.on ? sma(closes, overlays.sma.period) : null;
    const emaSeries =
      overlays?.ema.on ? ema(closes, overlays.ema.period) : null;
    const bb = overlays?.bollinger.on
      ? bollinger(closes, overlays.bollinger.period, overlays.bollinger.stddev)
      : null;
    return points.map((p, i) => ({
      date: p.date,
      close: p.close,
      sma: smaSeries ? smaSeries[i] : null,
      ema: emaSeries ? emaSeries[i] : null,
      bbMid: bb ? bb.middle[i] : null,
      bbUp: bb ? bb.upper[i] : null,
      bbLo: bb ? bb.lower[i] : null,
    }));
  }, [points, overlays]);

  const signalsByDate = useMemo(
    () => new Map(signals.map((s) => [s.date, s])),
    [signals],
  );

  if (points.length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center gap-1 text-text-3">
        <span className="font-mono text-2xs uppercase tracking-widest">
          No price data
        </span>
        <span className="text-xs text-text-3/70">
          Try a different ticker or check back later.
        </span>
      </div>
    );
  }
  return (
    <div className="relative h-64">
      <ActiveOverlayLabels overlays={overlays} />
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="date"
            hide={!showXAxis}
            stroke={CHART_CHROME.axis}
            fontSize={10}
            tick={{ fill: CHART_CHROME.tick }}
            minTickGap={32}
          />
          <YAxis
            stroke={CHART_CHROME.axis}
            fontSize={10}
            tick={{ fill: CHART_CHROME.tick }}
            width={48}
            domain={["auto", "auto"]}
            tickFormatter={(v) =>
              typeof v === "number" ? formatPrice(v, ctx, { usdDecimals: 0 }) : String(v)
            }
          />
          <Tooltip
            cursor={{ stroke: CHART_CHROME.axis, strokeDasharray: "3 3" }}
            content={
              <PriceTooltip signalsByDate={signalsByDate} ctx={ctx} />
            }
          />
          <Line
            type="monotone"
            dataKey="close"
            name="Close"
            stroke={INDICATOR_COLORS.price}
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
          />
          {overlays?.sma.on && (
            <Line
              type="monotone"
              dataKey="sma"
              name={`SMA ${overlays.sma.period}`}
              stroke={INDICATOR_COLORS.sma}
              strokeWidth={1}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
          {overlays?.ema.on && (
            <Line
              type="monotone"
              dataKey="ema"
              name={`EMA ${overlays.ema.period}`}
              stroke={INDICATOR_COLORS.ema}
              strokeWidth={1}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
          {overlays?.bollinger.on && (
            <>
              <Line
                type="monotone"
                dataKey="bbMid"
                name="BB mid"
                stroke={INDICATOR_COLORS.bbMid}
                strokeWidth={1}
                strokeDasharray="2 2"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="bbUp"
                name="BB upper"
                stroke={INDICATOR_COLORS.bbBand}
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="bbLo"
                name="BB lower"
                stroke={INDICATOR_COLORS.bbBand}
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </>
          )}
          {avgCost != null && (
            <ReferenceLine
              y={avgCost}
              stroke={INDICATOR_COLORS.avgCost}
              strokeDasharray="4 3"
              label={{
                value: `Avg ${fmtPriceCtx(avgCost, ctx)}`,
                position: "insideTopRight",
                fill: INDICATOR_COLORS.avgCost,
                fontSize: 10,
              }}
            />
          )}
          {signals.map((s, i) => {
            const meta = SIGNAL_MARKER[s.decision];
            return (
              <ReferenceDot
                key={`${s.date}-${i}`}
                x={s.date}
                y={s.close}
                r={5}
                fill={meta.color}
                stroke="#FFFFFF"
                strokeWidth={1.5}
                ifOverflow="extendDomain"
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
