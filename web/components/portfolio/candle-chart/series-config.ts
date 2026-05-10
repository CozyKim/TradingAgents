export const CHART = {
  up: "#F04452",          // KR convention: 상승 = 빨강 (signal.buy)
  down: "#1B64DA",        // 하락 = 파랑 (signal.sell)
  hold: "#8B95A1",        // text-3
  axis: "#C0C8CF",        // border-2
  grid: "#EAECEF",        // border-1
  text: "#4E5968",        // text-2
  background: "#FFFFFF",  // bg-1
  ma5: "#F59E0B",
  ma20: "#06B6D4",
  ma60: "#7C3AED",
  ma120: "#8B95A1",
  volumeUp: "rgba(240, 68, 82, 0.45)",
  volumeDown: "rgba(27, 100, 218, 0.45)",
  volumeMa: "#3182F6",
  avgCost: "#8B95A1",
  ema: "#06B6D4",
  bbBand: "#C0C8CF",
  bbMid: "#8B95A1",
  rsi: "#7C3AED",
  stochK: "#F04452",
  stochD: "#1B64DA",
  threshold: "#D1D6DB",
} as const;
