"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { PricePoint } from "@/lib/prices";
import type { SignalMarker } from "@/components/portfolio/price-chart";
import type { ChartSettings } from "@/lib/chart-settings";
import { sma } from "@/lib/indicators";
import { CHART } from "./series-config";
import { IntervalTabs } from "./interval-tabs";
import { OhlcHeader } from "./ohlc-header";
import { resample, bucketKey, type Interval } from "./resample";

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
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const volumeMaRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma5Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma60Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma120Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const [interval, setIntervalState] = useState<Interval>("1D");
  const [hovered, setHovered] = useState<PricePoint | null>(null);
  const savedRangeRef = useRef<{ from: Time; to: Time } | null>(null);

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
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.3 } });
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: CHART.volumeUp,
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.75, bottom: 0 },
    });
    const volumeMa = chart.addSeries(LineSeries, {
      priceScaleId: "vol",
      color: CHART.volumeMa,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma5 = chart.addSeries(LineSeries, {
      color: CHART.ma5,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma20 = chart.addSeries(LineSeries, {
      color: CHART.ma20,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma60 = chart.addSeries(LineSeries, {
      color: CHART.ma60,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma120 = chart.addSeries(LineSeries, {
      color: CHART.ma120,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chartRef.current = chart;
    candleRef.current = candle;
    volumeRef.current = volume;
    volumeMaRef.current = volumeMa;
    sma5Ref.current = sma5;
    sma20Ref.current = sma20;
    sma60Ref.current = sma60;
    sma120Ref.current = sma120;
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData.size) {
        setHovered(null);
        return;
      }
      const c = param.seriesData.get(candle) as
        | { time: Time; open: number; high: number; low: number; close: number }
        | undefined;
      if (!c) {
        setHovered(null);
        return;
      }
      setHovered({
        date: String(param.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: 0,
      });
    });
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      volumeMaRef.current = null;
      sma5Ref.current = null;
      sma20Ref.current = null;
      sma60Ref.current = null;
      sma120Ref.current = null;
    };
  }, []);

  const series = useMemo(() => resample(points, interval), [points, interval]);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current) return;
    if (!sma5Ref.current || !sma20Ref.current) return;
    if (!sma60Ref.current || !sma120Ref.current) return;
    if (!volumeMaRef.current) return;

    // 시리즈가 바뀌면(인터벌 변경/points 변경) 이전 hover는 더 이상 유효하지 않음
    setHovered(null);

    candleRef.current.setData(
      series.map((p) => ({
        time: p.date as Time,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );
    volumeRef.current.setData(
      series.map((p) => ({
        time: p.date as Time,
        value: p.volume,
        color: p.close >= p.open ? CHART.volumeUp : CHART.volumeDown,
      })),
    );
    const closes = series.map((p) => p.close);
    const volumes = series.map((p) => p.volume);
    const times = series.map((p) => p.date);
    const setLine = (
      ref: ISeriesApi<"Line">,
      values: (number | null)[],
      ts: string[],
    ) => {
      ref.setData(
        values
          .map((v, i) => (v == null ? null : { time: ts[i] as Time, value: v }))
          .filter((d): d is { time: Time; value: number } => d != null),
      );
    };
    setLine(sma5Ref.current, sma(closes, 5), times);
    setLine(sma20Ref.current, sma(closes, 20), times);
    setLine(sma60Ref.current, sma(closes, 60), times);
    setLine(sma120Ref.current, sma(closes, 120), times);
    setLine(volumeMaRef.current, sma(volumes, 20), times);

    if (savedRangeRef.current) {
      try {
        const range = savedRangeRef.current;
        const fromStr = typeof range.from === "string" ? range.from : String(range.from);
        const snapped = {
          from: bucketKey(fromStr, interval) as Time,
          to: range.to,
        };
        chartRef.current?.timeScale().setVisibleRange(snapped);
      } catch {
        chartRef.current?.timeScale().fitContent();
      }
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [series]);

  const handleIntervalChange = (next: Interval) => {
    const range = chartRef.current?.timeScale().getVisibleRange();
    if (range) savedRangeRef.current = { from: range.from, to: range.to };
    setIntervalState(next);
  };

  const headerCurrent = hovered ?? series[series.length - 1] ?? null;
  const headerPrev = (() => {
    if (!headerCurrent) return null;
    const idx = series.findIndex((p) => p.date === headerCurrent.date);
    if (idx <= 0) return null;
    return series[idx - 1].close;
  })();

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <OhlcHeader current={headerCurrent} prevClose={headerPrev} />
        <IntervalTabs value={interval} onChange={handleIntervalChange} />
      </div>
      <div ref={containerRef} style={{ height, width: "100%" }} />
    </div>
  );
}
