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

/**
 * 각 pane의 의도된 픽셀 높이.
 *
 * Lightweight Charts는 chart 컨테이너의 높이를 모든 pane이 stretch factor 비율로
 * 나눠 가진다. 이 값들을 stretch factor로도 그대로 쓰면, 컨테이너 높이를 ∑(켜진 pane)
 * 으로 맞추는 한 각 pane은 자기 픽셀 크기를 유지한다 — 즉 RSI/Stoch를 켜도 메인이
 * 줄지 않고 차트 전체가 아래로 늘어난다.
 */
export const PANE_HEIGHT = {
  main: 320,
  volume: 80,
  rsi: 100,
  stoch: 100,
} as const;
