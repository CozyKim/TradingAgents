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
import { useCurrency, formatPrice, currencyForTicker } from "@/lib/currency";
import { CHART, PANE_HEIGHT } from "./series-config";
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
  /** 종목 심볼 — 가격축/헤더의 원본 통화를 판별하는 데 쓴다. */
  ticker?: string;
  points: PricePoint[];
  signals?: SignalMarker[];
  avgCost?: number;
  settings: ChartSettings;
  onSettingsChange: (next: ChartSettings) => void;
  onSettingsReset: () => void;
}

export function CandleChart({
  ticker,
  points,
  signals = [],
  avgCost,
  settings,
  onSettingsChange,
  onSettingsReset,
}: CandleChartProps) {
  const ctx = useCurrency();
  // 캔들 데이터는 거래소 원본 통화로 들어오므로, 축/헤더 포맷도 그 통화 기준으로
  // 환산한다. ticker가 없으면 USD로 가정(기존 동작 유지).
  const sourceCurrency = currencyForTicker(ticker ?? "");
  // 캔들·거래량·RSI·Stoch 각각이 별도 pane이며, 픽셀 높이로 stretch factor를 고정.
  // 컨테이너 높이를 ∑(켜진 pane)으로 맞추는 한 각 pane은 자기 픽셀 크기를 유지한다.
  const height =
    PANE_HEIGHT.candle +
    PANE_HEIGHT.volume +
    (settings.panels.rsi.on ? PANE_HEIGHT.rsi : 0) +
    (settings.panels.stoch.on ? PANE_HEIGHT.stoch : 0);
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
        // 11px → 좁은 모바일 폭에서 가격축이 차트 영역을 덜 잠식.
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CHART.grid },
        horzLines: { color: CHART.grid },
      },
      crosshair: { mode: CrosshairMode.Normal },
      // minimumWidth: 0으로 가격축이 실제 텍스트 폭에 딱 맞게 좁아지도록.
      rightPriceScale: { borderColor: CHART.axis, minimumWidth: 0 },
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
        formatter: (price: number) =>
          formatPrice(price, sourceCurrency, ctx, { usdDecimals: 0 }),
        minMove: 0.01,
      },
      // 우측 axis의 빨간 현재가 배지(lastValueVisible)를 끈다 — 좁은 모바일 폭에서
      // 배지가 캔들 영역을 덮어 가독성을 해쳤다. 종가는 OHLC 헤더에 항상 표시되므로
      // 정보 손실 없음.
      lastValueVisible: false,
      priceLineVisible: false,
    });
    // 캔들 pane(0): 좁은 위·아래 마진만 두고 자동 스케일이 visible 가격에 딱 맞도록.
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.05 } });
    // 거래량 pane(1): 별도 pane으로 분리해 캔들 Y축 자동 스케일에 영향을 주지 않게 한다.
    const volume = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: "volume" },
        color: CHART.volumeUp,
        priceLineVisible: false,
        // 거래량 축의 마지막 값 배지도 같은 이유로 숨김.
        lastValueVisible: false,
      },
      1,
    );
    const volumeMa = chart.addSeries(
      LineSeries,
      {
        color: CHART.volumeMa,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      },
      1,
    );
    chartRef.current = chart;
    candleRef.current = candle;
    volumeRef.current = volume;
    volumeMaRef.current = volumeMa;
    // 각 pane을 픽셀-비율 stretch factor로 고정.
    candle.getPane().setStretchFactor(PANE_HEIGHT.candle);
    volume.getPane().setStretchFactor(PANE_HEIGHT.volume);
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
    //   1D → 최근 45 거래일 (~2개월)
    //   1W → 최근 52 주 (~1년)
    //   1M → 전체 (보통 12~13개)
    const ts = chartRef.current?.timeScale();
    if (ts) {
      const limit = interval === "1D" ? 45 : interval === "1W" ? 52 : Infinity;
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
      // 우측 axis 라벨은 가격만 표시 (가로 폭 절약).
      title: "",
    });
  }, [avgCost, ctx.currency, ctx.fxRate]);

  // 통화/환율 변경 시 캔들 시리즈의 priceFormat 재적용 — chart 자체는 재생성하지 않음.
  // (글로벌 localization.priceFormatter는 거래량 축까지 덮어쓰므로 사용하지 않는다.)
  useEffect(() => {
    if (!candleRef.current) return;
    candleRef.current.applyOptions({
      priceFormat: {
        type: "custom",
        formatter: (price: number) =>
          formatPrice(price, sourceCurrency, ctx, { usdDecimals: 0 }),
        minMove: 0.01,
      },
    });
  }, [sourceCurrency, ctx.currency, ctx.fxRate]);

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
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <OhlcHeader
          current={headerCurrent}
          prevClose={headerPrev}
          sourceCurrency={sourceCurrency}
        />
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 min-w-0">
          <IntervalTabs value={interval} onChange={handleIntervalChange} />
          <IndicatorToolbar
            settings={settings}
            onChange={onSettingsChange}
            onReset={onSettingsReset}
          />
        </div>
      </div>
      <div className="relative" style={{ width: "100%" }}>
        <div ref={containerRef} style={{ height, width: "100%" }} />
        {/* RSI/Stoch pane 좌측 상단에 작은 범례 라벨.
            Lightweight Charts pane 자체에는 제목 슬롯이 없어서 chart 컨테이너 위에
            absolute로 띄운다. y 위치는 PANE_HEIGHT 합으로 계산. */}
        {settings.panels.rsi.on && (
          <PaneLabel
            top={PANE_HEIGHT.candle + PANE_HEIGHT.volume}
            text={`RSI ${settings.panels.rsi.period}`}
          />
        )}
        {settings.panels.stoch.on && (
          <PaneLabel
            top={
              PANE_HEIGHT.candle +
              PANE_HEIGHT.volume +
              (settings.panels.rsi.on ? PANE_HEIGHT.rsi : 0)
            }
            text={`Stoch ${settings.panels.stoch.k} ${settings.panels.stoch.slowing} ${settings.panels.stoch.d}`}
          />
        )}
      </div>
    </div>
  );
}

function PaneLabel({ top, text }: { top: number; text: string }) {
  return (
    <div
      className="pointer-events-none absolute z-10 rounded-sm bg-bg-1/85 px-1.5 py-0.5 font-mono text-2xs text-text-2"
      style={{ top: top + 4, left: 8 }}
    >
      {text}
    </div>
  );
}
