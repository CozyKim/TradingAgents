"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  LineStyle,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from "lightweight-charts";
import type { PricePoint } from "@/lib/prices";
import type { SignalMarker } from "./types";
import type { ChartSettings } from "@/lib/chart-settings";
import { sma } from "@/lib/indicators";
import { useCurrency, formatPrice } from "@/lib/currency";
import { CHART } from "./series-config";
import { IntervalTabs } from "./interval-tabs";
import { OhlcHeader } from "./ohlc-header";
import { IndicatorToolbar } from "@/components/portfolio/indicator-toolbar";
import { resample, alignSignals, type Interval } from "./resample";
import {
  syncOptionalSeries,
  type OptionalSeries,
  EMPTY_OPTIONAL,
} from "./series-builder";

const MARKER_STYLE: Record<
  SignalMarker["decision"],
  {
    position: "aboveBar" | "belowBar" | "inBar";
    shape: "arrowUp" | "arrowDown" | "circle";
    color: string;
  }
> = {
  // 텍스트는 일부러 비워둔다 — 한 봉에 여러 신호가 몰리면 라벨이 겹쳐 가독성을
  // 망친다. 모양과 색으로 의미가 충분히 전달되고, 상세는 hover 또는
  // Analysis history 섹션에서 본다.
  BUY:         { position: "belowBar", shape: "arrowUp",   color: CHART.up   },
  OVERWEIGHT:  { position: "belowBar", shape: "arrowUp",   color: CHART.up   },
  SELL:        { position: "aboveBar", shape: "arrowDown", color: CHART.down },
  UNDERWEIGHT: { position: "aboveBar", shape: "arrowDown", color: CHART.down },
  HOLD:        { position: "inBar",    shape: "circle",    color: CHART.hold },
};

export interface CandleChartProps {
  points: PricePoint[];
  signals?: SignalMarker[];
  avgCost?: number;
  settings: ChartSettings;
  onSettingsChange: (next: ChartSettings) => void;
  onSettingsReset: () => void;
  height?: number;
}

export function CandleChart({
  points,
  signals = [],
  avgCost,
  settings,
  onSettingsChange,
  onSettingsReset,
  height = 480,
}: CandleChartProps) {
  const ctx = useCurrency();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const volumeMaRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const avgCostLineRef = useRef<IPriceLine | null>(null);
  const optionalRef = useRef<OptionalSeries>({ ...EMPTY_OPTIONAL });

  const [interval, setIntervalState] = useState<Interval>("1D");
  const [hovered, setHovered] = useState<PricePoint | null>(null);

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
    // priceFormat을 series에 적용해 거래량 등 별도 priceScale은 영향받지 않게 한다.
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: CHART.up,
      downColor: CHART.down,
      borderUpColor: CHART.up,
      borderDownColor: CHART.down,
      wickUpColor: CHART.up,
      wickDownColor: CHART.down,
      priceFormat: {
        type: "custom",
        formatter: (price: number) => formatPrice(price, ctx, { usdDecimals: 0 }),
        minMove: 0.01,
      },
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
    chartRef.current = chart;
    candleRef.current = candle;
    volumeRef.current = volume;
    volumeMaRef.current = volumeMa;
    // v5: setMarkers는 ISeriesApi에서 제거되어 createSeriesMarkers 플러그인으로 분리됨.
    markersRef.current = createSeriesMarkers(candle, []);
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
      try {
        markersRef.current?.detach();
      } catch {
        // chart.remove()가 먼저 일어나면 detach가 throw할 수 있음 — 무시.
      }
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      volumeMaRef.current = null;
      markersRef.current = null;
      avgCostLineRef.current = null;
      optionalRef.current = { ...EMPTY_OPTIONAL };
    };
    // ctx는 의존성에서 제외 — chart 재생성을 막고, 별도 effect에서 applyOptions로 갱신.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const series = useMemo(() => resample(points, interval), [points, interval]);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current) return;
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
    const volumes = series.map((p) => p.volume);
    const times = series.map((p) => p.date);
    const setLine = (
      ref: ISeriesApi<"Line">,
      values: (number | null)[],
      ts: string[],
    ) => {
      ref.setData(
        values
          .map((v, i) =>
            v == null || !Number.isFinite(v)
              ? null
              : { time: ts[i] as Time, value: v },
          )
          .filter((d): d is { time: Time; value: number } => d != null),
      );
    };
    setLine(volumeMaRef.current, sma(volumes, 20), times);

    // 초기 보이는 구간을 인터벌별로 적절히 제한해 첫 화면이 너무 빽빽하지 않게 한다.
    // 사용자는 휠로 확대/축소해 더 넓은 범위를 볼 수 있다.
    //   1D → 최근 90 거래일 (~4개월)
    //   1W → 최근 52 주 (~1년)
    //   1M → 전체 (보통 12~13개)
    const ts = chartRef.current?.timeScale();
    if (ts) {
      const limit = interval === "1D" ? 90 : interval === "1W" ? 52 : Infinity;
      const total = series.length;
      if (total > 0 && total > limit) {
        ts.setVisibleLogicalRange({ from: total - limit, to: total - 1 });
      } else {
        ts.fitContent();
      }
    }
  }, [series, interval]);

  // 신호 마커 — 데이터 effect에서 분리하여 signals 변경이 viewport(time scale)를 리셋하지 않도록 함.
  // v5 series-markers 플러그인은 time에 대한 binary search를 사용하므로 ASC 정렬이 필수.
  useEffect(() => {
    if (!markersRef.current) return;
    const aligned = alignSignals(signals, interval);
    const sorted = [...aligned].sort((a, b) =>
      a.date < b.date ? -1 : a.date > b.date ? 1 : 0,
    );
    markersRef.current.setMarkers(
      sorted.map((s) => ({
        time: s.date as Time,
        position: MARKER_STYLE[s.decision].position,
        shape: MARKER_STYLE[s.decision].shape,
        color: MARKER_STYLE[s.decision].color,
      })),
    );
  }, [signals, interval]);

  // 평단가 가격 라인 — avgCost가 바뀔 때마다 제거 후 재생성.
  useEffect(() => {
    if (!candleRef.current) return;
    if (avgCostLineRef.current) {
      try {
        candleRef.current.removePriceLine(avgCostLineRef.current);
      } catch {
        // 시리즈가 이미 destroyed면 무시.
      }
      avgCostLineRef.current = null;
    }
    if (avgCost == null || !Number.isFinite(avgCost)) return;
    avgCostLineRef.current = candleRef.current.createPriceLine({
      price: avgCost,
      color: CHART.avgCost,
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      axisLabelVisible: true,
      title: `Avg ${formatPrice(avgCost, ctx)}`,
    });
  }, [avgCost, ctx.currency, ctx.fxRate]);

  // 통화/환율 변경 시 캔들 시리즈의 priceFormat 재적용 — chart 자체는 재생성하지 않음.
  // (글로벌 localization.priceFormatter는 거래량 축까지 덮어쓰므로 사용하지 않는다.)
  useEffect(() => {
    if (!candleRef.current) return;
    candleRef.current.applyOptions({
      priceFormat: {
        type: "custom",
        formatter: (price: number) => formatPrice(price, ctx, { usdDecimals: 0 }),
        minMove: 0.01,
      },
    });
  }, [ctx.currency, ctx.fxRate]);

  // 옵션 시리즈(SMA/EMA/Bollinger/RSI/Stoch) — settings 토글에 따라 add/remove.
  // 캔들·거래량·거래량 MA는 본 effect와 무관하므로 깜빡이지 않음.
  useEffect(() => {
    if (!chartRef.current) return;
    optionalRef.current = syncOptionalSeries(
      chartRef.current,
      series,
      settings,
      optionalRef.current,
    );
  }, [series, settings]);

  const handleIntervalChange = (next: Interval) => {
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
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <OhlcHeader current={headerCurrent} prevClose={headerPrev} />
        <div className="flex items-center gap-2">
          <IntervalTabs value={interval} onChange={handleIntervalChange} />
          <IndicatorToolbar
            settings={settings}
            onChange={onSettingsChange}
            onReset={onSettingsReset}
          />
        </div>
      </div>
      <div ref={containerRef} style={{ height, width: "100%" }} />
    </div>
  );
}
