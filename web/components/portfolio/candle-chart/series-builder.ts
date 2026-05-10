import {
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { ChartSettings } from "@/lib/chart-settings";
import type { PricePoint } from "@/lib/prices";
import { sma, ema, bollinger, rsi, stochasticSlow } from "@/lib/indicators";
import { CHART } from "./series-config";

/**
 * settings 토글에 따라 차트에 추가/제거되는 옵션 시리즈들을 관리.
 * SMA(4종 단일 토글)·EMA·Bollinger·RSI·Stoch가 모두 여기서 관리된다.
 * 캔들·거래량·거래량 MA만 candle-chart.tsx 본체에서 항상 그린다.
 */
export interface OptionalSeries {
  sma5: ISeriesApi<"Line"> | null;
  sma20: ISeriesApi<"Line"> | null;
  sma60: ISeriesApi<"Line"> | null;
  sma120: ISeriesApi<"Line"> | null;
  ema: ISeriesApi<"Line"> | null;
  bbUp: ISeriesApi<"Line"> | null;
  bbMid: ISeriesApi<"Line"> | null;
  bbLo: ISeriesApi<"Line"> | null;
  rsi: ISeriesApi<"Line"> | null;
  stochK: ISeriesApi<"Line"> | null;
  stochD: ISeriesApi<"Line"> | null;
}

export const EMPTY_OPTIONAL: OptionalSeries = {
  sma5: null,
  sma20: null,
  sma60: null,
  sma120: null,
  ema: null,
  bbUp: null,
  bbMid: null,
  bbLo: null,
  rsi: null,
  stochK: null,
  stochD: null,
};

// SMA — 단일 on/off 토글로 4개 고정 기간선을 함께 관리.
const SMA_CONFIG: ReadonlyArray<{
  ref: "sma5" | "sma20" | "sma60" | "sma120";
  period: number;
  color: string;
}> = [
  { ref: "sma5", period: 5, color: CHART.ma5 },
  { ref: "sma20", period: 20, color: CHART.ma20 },
  { ref: "sma60", period: 60, color: CHART.ma60 },
  { ref: "sma120", period: 120, color: CHART.ma120 },
];

// v5 panes API: chart.addSeries(def, options, paneIndex). 메인 = 0.
const RSI_PANE = 2;
const STOCH_PANE = 3;

function setLine(
  ref: ISeriesApi<"Line">,
  values: (number | null)[],
  times: string[],
) {
  ref.setData(
    values
      .map((v, i) => (v == null ? null : { time: times[i] as Time, value: v }))
      .filter((d): d is { time: Time; value: number } => d != null),
  );
}

export function syncOptionalSeries(
  chart: IChartApi,
  series: PricePoint[],
  settings: ChartSettings,
  refs: OptionalSeries,
): OptionalSeries {
  const next: OptionalSeries = { ...refs };
  const closes = series.map((p) => p.close);
  const times = series.map((p) => p.date);

  // SMA — 메인 페인, 4 고정 기간(5/20/60/120) + 단일 on/off 토글
  if (settings.overlays.sma.on) {
    for (const cfg of SMA_CONFIG) {
      if (!next[cfg.ref]) {
        next[cfg.ref] = chart.addSeries(LineSeries, {
          color: cfg.color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
      }
      setLine(next[cfg.ref]!, sma(closes, cfg.period), times);
    }
  } else {
    for (const cfg of SMA_CONFIG) {
      const ref = next[cfg.ref];
      if (ref) {
        chart.removeSeries(ref);
        next[cfg.ref] = null;
      }
    }
  }

  // EMA — 메인 페인
  if (settings.overlays.ema.on) {
    if (!next.ema) {
      next.ema = chart.addSeries(LineSeries, {
        color: CHART.ema,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    setLine(next.ema, ema(closes, settings.overlays.ema.period), times);
  } else if (next.ema) {
    chart.removeSeries(next.ema);
    next.ema = null;
  }

  // Bollinger — 메인 페인
  if (settings.overlays.bollinger.on) {
    const bb = bollinger(
      closes,
      settings.overlays.bollinger.period,
      settings.overlays.bollinger.stddev,
    );
    if (!next.bbMid) {
      next.bbMid = chart.addSeries(LineSeries, {
        color: CHART.bbMid,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!next.bbUp) {
      next.bbUp = chart.addSeries(LineSeries, {
        color: CHART.bbBand,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!next.bbLo) {
      next.bbLo = chart.addSeries(LineSeries, {
        color: CHART.bbBand,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    setLine(next.bbMid, bb.middle, times);
    setLine(next.bbUp, bb.upper, times);
    setLine(next.bbLo, bb.lower, times);
  } else {
    for (const k of ["bbMid", "bbUp", "bbLo"] as const) {
      const ref = next[k];
      if (ref) {
        chart.removeSeries(ref);
        next[k] = null;
      }
    }
  }

  // RSI — pane 2
  if (settings.panels.rsi.on) {
    if (!next.rsi) {
      next.rsi = chart.addSeries(
        LineSeries,
        {
          color: CHART.rsi,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        },
        RSI_PANE,
      );
    }
    setLine(next.rsi, rsi(closes, settings.panels.rsi.period), times);
  } else if (next.rsi) {
    chart.removeSeries(next.rsi);
    next.rsi = null;
  }

  // Stoch — pane 3
  if (settings.panels.stoch.on) {
    const { k, d } = stochasticSlow(
      closes,
      settings.panels.stoch.k,
      settings.panels.stoch.slowing,
      settings.panels.stoch.d,
    );
    if (!next.stochK) {
      next.stochK = chart.addSeries(
        LineSeries,
        {
          color: CHART.stochK,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        },
        STOCH_PANE,
      );
    }
    // Lightweight Charts v5: 요청한 paneIndex가 기존 페인 수보다 크면 라이브러리가
    // 새 페인을 생성/클램프할 수 있다. %K가 실제로 안착한 페인 인덱스를 다시 읽어와
    // %D도 같은 페인을 사용하도록 강제한다 (분리되어 그려지는 P2 버그 방지).
    const stochPaneIdx = next.stochK.getPane().paneIndex();
    if (!next.stochD) {
      next.stochD = chart.addSeries(
        LineSeries,
        {
          color: CHART.stochD,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
        },
        stochPaneIdx,
      );
    }
    setLine(next.stochK, k, times);
    setLine(next.stochD, d, times);
  } else {
    for (const key of ["stochK", "stochD"] as const) {
      const ref = next[key];
      if (ref) {
        chart.removeSeries(ref);
        next[key] = null;
      }
    }
  }

  return next;
}
