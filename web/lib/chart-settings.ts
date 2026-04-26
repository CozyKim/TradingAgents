export interface OverlaySma {
  on: boolean;
  period: number;
}
export interface OverlayEma {
  on: boolean;
  period: number;
}
export interface OverlayBollinger {
  on: boolean;
  period: number;
  stddev: number;
}
export interface PanelRsi {
  on: boolean;
  period: number;
}
export interface PanelStoch {
  on: boolean;
  k: number;
  slowing: number;
  d: number;
}

export interface ChartSettings {
  overlays: {
    sma: OverlaySma;
    ema: OverlayEma;
    bollinger: OverlayBollinger;
  };
  panels: {
    rsi: PanelRsi;
    stoch: PanelStoch;
  };
}

export const DEFAULT_CHART_SETTINGS: ChartSettings = {
  overlays: {
    sma: { on: false, period: 20 },
    ema: { on: false, period: 12 },
    bollinger: { on: false, period: 20, stddev: 2 },
  },
  panels: {
    rsi: { on: false, period: 14 },
    stoch: { on: false, k: 14, slowing: 3, d: 3 },
  },
};

export const CHART_SETTINGS_KEY = "tradingagents:chart-settings:v1";

export function loadChartSettings(): ChartSettings {
  if (typeof window === "undefined") return DEFAULT_CHART_SETTINGS;
  try {
    const raw = window.localStorage.getItem(CHART_SETTINGS_KEY);
    if (!raw) return DEFAULT_CHART_SETTINGS;
    const parsed = JSON.parse(raw);
    return mergeWithDefaults(parsed);
  } catch {
    return DEFAULT_CHART_SETTINGS;
  }
}

export function saveChartSettings(settings: ChartSettings): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      CHART_SETTINGS_KEY,
      JSON.stringify(settings),
    );
  } catch {
    // Quota or serialization errors are non-fatal.
  }
}

function mergeWithDefaults(raw: unknown): ChartSettings {
  const d = DEFAULT_CHART_SETTINGS;
  if (!raw || typeof raw !== "object") return d;
  const r = raw as {
    overlays?: Partial<ChartSettings["overlays"]>;
    panels?: Partial<ChartSettings["panels"]>;
  };
  const ov = r.overlays ?? {};
  const pa = r.panels ?? {};
  return {
    overlays: {
      sma: { ...d.overlays.sma, ...(ov.sma ?? {}) },
      ema: { ...d.overlays.ema, ...(ov.ema ?? {}) },
      bollinger: { ...d.overlays.bollinger, ...(ov.bollinger ?? {}) },
    },
    panels: {
      rsi: { ...d.panels.rsi, ...(pa.rsi ?? {}) },
      stoch: { ...d.panels.stoch, ...(pa.stoch ?? {}) },
    },
  };
}
