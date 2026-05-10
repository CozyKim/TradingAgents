"use client";
import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { PricePoint } from "@/lib/prices";
import type { SignalMarker } from "@/components/portfolio/price-chart";
import type { ChartSettings } from "@/lib/chart-settings";
import { CHART } from "./series-config";

export interface CandleChartProps {
  points: PricePoint[];
  signals?: SignalMarker[];
  avgCost?: number;
  settings: ChartSettings;
  onSettingsChange: (next: ChartSettings) => void;
  onSettingsReset: () => void;
  height?: number;
}

export function CandleChart({ points, height = 480 }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART.background },
        textColor: CHART.text,
      },
      grid: {
        vertLines: { color: CHART.grid },
        horzLines: { color: CHART.grid },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: CHART.axis },
      timeScale: { borderColor: CHART.axis, timeVisible: false },
      autoSize: true,
    });
    // Lightweight Charts v5: addCandlestickSeries는 deprecated.
    // chart.addSeries(CandlestickSeries, options) 패턴 사용.
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: CHART.up,
      downColor: CHART.down,
      borderUpColor: CHART.up,
      borderDownColor: CHART.down,
      wickUpColor: CHART.up,
      wickDownColor: CHART.down,
    });
    chartRef.current = chart;
    candleRef.current = candle;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!candleRef.current) return;
    candleRef.current.setData(
      points.map((p) => ({
        time: p.date as Time,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );
    chartRef.current?.timeScale().fitContent();
  }, [points]);

  return <div ref={containerRef} style={{ height, width: "100%" }} />;
}
