"use client";
import {
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PricePoint } from "@/lib/prices";

export interface SignalMarker {
  date: string;
  decision: "BUY" | "SELL" | "HOLD" | "OVERWEIGHT" | "UNDERWEIGHT";
  close: number;
}

const decisionColor: Record<string, string> = {
  BUY: "var(--pos)",
  OVERWEIGHT: "var(--pos)",
  SELL: "var(--neg)",
  UNDERWEIGHT: "var(--neg)",
  HOLD: "var(--warn)",
};

export function PriceChart({
  points,
  signals = [],
}: {
  points: PricePoint[];
  signals?: SignalMarker[];
}) {
  if (points.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-text-3 text-sm">
        No price data
      </div>
    );
  }
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="date"
            stroke="#6b6b74"
            fontSize={10}
            tick={{ fill: "#6b6b74" }}
          />
          <YAxis
            stroke="#6b6b74"
            fontSize={10}
            tick={{ fill: "#6b6b74" }}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              background: "#111114",
              border: "1px solid #25252b",
              fontSize: 12,
            }}
            labelStyle={{ color: "#a0a0a8" }}
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#4f8cff"
            strokeWidth={1.5}
            dot={false}
          />
          {signals.map((s, i) => (
            <ReferenceDot
              key={`${s.date}-${i}`}
              x={s.date}
              y={s.close}
              r={4}
              fill={decisionColor[s.decision] ?? "#a0a0a8"}
              stroke="none"
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
