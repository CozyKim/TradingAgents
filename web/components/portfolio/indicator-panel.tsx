"use client";
import { useMemo } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { rsi, stochasticSlow } from "@/lib/indicators";
import { PanelRsi, PanelStoch } from "@/lib/chart-settings";
import { PricePoint } from "@/lib/prices";
import { CHART_CHROME, INDICATOR_COLORS } from "./indicator-colors";

const TOOLTIP_STYLE = {
  background: CHART_CHROME.tooltipBg,
  border: `1px solid ${CHART_CHROME.tooltipBorder}`,
  borderRadius: 12,
  fontSize: 12,
  padding: "8px 12px",
  boxShadow:
    "0 8px 24px -4px rgba(17, 24, 28, 0.12), 0 2px 6px 0 rgba(17, 24, 28, 0.06)",
};

const TOOLTIP_LABEL_STYLE = {
  color: CHART_CHROME.tooltipLabel,
  fontFamily:
    "'Pretendard Variable', 'Pretendard', system-ui, sans-serif",
  fontSize: 11,
  fontWeight: 600 as const,
  letterSpacing: "-0.01em",
};

const fmtPct = (v: number | string | null | undefined) =>
  typeof v === "number" && Number.isFinite(v) ? v.toFixed(1) : "—";

export function RsiPanel({
  points,
  config,
  showXAxis,
}: {
  points: PricePoint[];
  config: PanelRsi;
  showXAxis: boolean;
}) {
  const data = useMemo(() => {
    const closes = points.map((p) => p.close);
    const series = rsi(closes, config.period);
    return points.map((p, i) => ({ date: p.date, rsi: series[i] }));
  }, [points, config.period]);

  return (
    <PanelShell label={`RSI ${config.period}`} showXAxis={showXAxis} data={data}>
      <YAxis
        domain={[0, 100]}
        ticks={[30, 50, 70]}
        stroke={CHART_CHROME.axis}
        fontSize={10}
        tick={{ fill: CHART_CHROME.tick }}
        width={36}
      />
      <ReferenceLine y={70} stroke={INDICATOR_COLORS.threshold} strokeDasharray="2 2" />
      <ReferenceLine y={30} stroke={INDICATOR_COLORS.threshold} strokeDasharray="2 2" />
      <Tooltip
        cursor={{ stroke: CHART_CHROME.axis, strokeDasharray: "3 3" }}
        contentStyle={TOOLTIP_STYLE}
        labelStyle={TOOLTIP_LABEL_STYLE}
        itemStyle={{ color: "#191F28", fontFamily: "'Pretendard Variable', 'Pretendard', system-ui, sans-serif" }}
        formatter={(value: number | string, name: string) => [fmtPct(value), name]}
      />
      <Line
        type="monotone"
        dataKey="rsi"
        stroke={INDICATOR_COLORS.rsi}
        strokeWidth={1.25}
        dot={false}
        connectNulls={false}
        isAnimationActive={false}
      />
    </PanelShell>
  );
}

export function StochPanel({
  points,
  config,
  showXAxis,
}: {
  points: PricePoint[];
  config: PanelStoch;
  showXAxis: boolean;
}) {
  const data = useMemo(() => {
    const closes = points.map((p) => p.close);
    const { k, d } = stochasticSlow(
      closes,
      config.k,
      config.slowing,
      config.d,
    );
    return points.map((p, i) => ({ date: p.date, k: k[i], d: d[i] }));
  }, [points, config.k, config.slowing, config.d]);

  return (
    <PanelShell
      label={`Stoch ${config.k}/${config.slowing}/${config.d}`}
      showXAxis={showXAxis}
      data={data}
    >
      <YAxis
        domain={[0, 100]}
        ticks={[20, 50, 80]}
        stroke={CHART_CHROME.axis}
        fontSize={10}
        tick={{ fill: CHART_CHROME.tick }}
        width={36}
      />
      <ReferenceLine y={80} stroke={INDICATOR_COLORS.threshold} strokeDasharray="2 2" />
      <ReferenceLine y={20} stroke={INDICATOR_COLORS.threshold} strokeDasharray="2 2" />
      <Tooltip
        cursor={{ stroke: CHART_CHROME.axis, strokeDasharray: "3 3" }}
        contentStyle={TOOLTIP_STYLE}
        labelStyle={TOOLTIP_LABEL_STYLE}
        itemStyle={{ color: "#191F28", fontFamily: "'Pretendard Variable', 'Pretendard', system-ui, sans-serif" }}
        formatter={(value: number | string, name: string) => [fmtPct(value), name]}
      />
      <Line
        type="monotone"
        dataKey="k"
        name="%K"
        stroke={INDICATOR_COLORS.stochK}
        strokeWidth={1.25}
        dot={false}
        connectNulls={false}
        isAnimationActive={false}
      />
      <Line
        type="monotone"
        dataKey="d"
        name="%D"
        stroke={INDICATOR_COLORS.stochD}
        strokeWidth={1}
        strokeDasharray="3 2"
        dot={false}
        connectNulls={false}
        isAnimationActive={false}
      />
    </PanelShell>
  );
}

function PanelShell({
  label,
  showXAxis,
  data,
  children,
}: {
  label: string;
  showXAxis: boolean;
  data: { date: string }[];
  children: React.ReactNode;
}) {
  return (
    <div className="relative">
      <span className="absolute left-2 top-1 z-10 text-2xs font-mono uppercase tracking-widest text-text-3">
        {label}
      </span>
      <div className={showXAxis ? "h-24" : "h-20"}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="date"
              hide={!showXAxis}
              stroke={CHART_CHROME.axis}
              fontSize={10}
              tick={{ fill: CHART_CHROME.tick }}
              minTickGap={32}
            />
            {children}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
