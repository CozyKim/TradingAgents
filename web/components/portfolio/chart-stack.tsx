"use client";
import { ChartSettings } from "@/lib/chart-settings";
import { PricePoint } from "@/lib/prices";
import { IndicatorToolbar } from "./indicator-toolbar";
import { RsiPanel, StochPanel } from "./indicator-panel";
import { PriceChart, SignalMarker } from "./price-chart";

export function ChartStack({
  points,
  signals,
  avgCost,
  settings,
  onChange,
  onReset,
}: {
  points: PricePoint[];
  signals: SignalMarker[];
  avgCost?: number;
  settings: ChartSettings;
  onChange: (next: ChartSettings) => void;
  onReset: () => void;
}) {
  const rsiOn = settings.panels.rsi.on;
  const stochOn = settings.panels.stoch.on;

  // X-axis labels appear only on the bottom-most chart to avoid duplication.
  const lastPanel = stochOn ? "stoch" : rsiOn ? "rsi" : "price";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-end">
        <IndicatorToolbar
          settings={settings}
          onChange={onChange}
          onReset={onReset}
        />
      </div>
      <PriceChart
        points={points}
        signals={signals}
        avgCost={avgCost}
        overlays={settings.overlays}
        showXAxis={lastPanel === "price"}
      />
      {rsiOn && (
        <RsiPanel
          points={points}
          config={settings.panels.rsi}
          showXAxis={lastPanel === "rsi"}
        />
      )}
      {stochOn && (
        <StochPanel
          points={points}
          config={settings.panels.stoch}
          showXAxis={lastPanel === "stoch"}
        />
      )}
    </div>
  );
}
