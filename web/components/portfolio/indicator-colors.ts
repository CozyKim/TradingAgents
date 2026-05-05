// Light-theme palette tuned for Toss-style charts.
// Foreground lines stay saturated against the soft-gray surface.
export const INDICATOR_COLORS = {
  price: "#3182F6", // Toss blue
  sma: "#F59E0B",
  ema: "#06B6D4",
  bbMid: "#8B95A1",
  bbBand: "#C0C8CF",
  avgCost: "#8B95A1",
  rsi: "#7C3AED",
  stochK: "#F04452", // KR up = red
  stochD: "#1B64DA", // KR down = blue
  threshold: "#D1D6DB",
} as const;

// Chart chrome (axes, ticks, tooltip) — synced with light-mode tokens.
export const CHART_CHROME = {
  axis: "#C0C8CF",
  tick: "#8B95A1",
  tooltipBg: "#FFFFFF",
  tooltipBorder: "#EAECEF",
  tooltipLabel: "#4E5968",
} as const;

// KR-market signal markers: buy/up = red, sell/down = blue.
export const SIGNAL_MARKER = {
  BUY: { color: "#F04452", shape: "▲" },
  OVERWEIGHT: { color: "#F04452", shape: "▲" },
  SELL: { color: "#1B64DA", shape: "▼" },
  UNDERWEIGHT: { color: "#1B64DA", shape: "▼" },
  HOLD: { color: "#8B95A1", shape: "●" },
} as const;
