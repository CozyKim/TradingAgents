export const INDICATOR_COLORS = {
  price: "#4f8cff",
  sma: "#fbbf24",
  ema: "#22d3ee",
  bbMid: "#a0a0a8",
  bbBand: "#5a5a64",
  avgCost: "#a0a0a8",
  rsi: "#a78bfa",
  stochK: "#34d399",
  stochD: "#f87171",
  threshold: "#3a3a42",
} as const;

// Chart chrome (axes, ticks, tooltip) — synced with the design system text/border tokens.
export const CHART_CHROME = {
  axis: "#8a8a93",
  tick: "#8a8a93",
  tooltipBg: "#111114",
  tooltipBorder: "#2d2d34",
  tooltipLabel: "#a0a0a8",
} as const;

export const SIGNAL_MARKER = {
  BUY: { color: "#34d399", shape: "▲" },
  OVERWEIGHT: { color: "#34d399", shape: "▲" },
  SELL: { color: "#f87171", shape: "▼" },
  UNDERWEIGHT: { color: "#f87171", shape: "▼" },
  HOLD: { color: "#fbbf24", shape: "●" },
} as const;
