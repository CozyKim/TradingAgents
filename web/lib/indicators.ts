export type Series = (number | null)[];

export function sma(values: number[], period: number): Series {
  const out: Series = new Array(values.length).fill(null);
  if (period <= 0 || values.length < period) return out;
  let sum = 0;
  for (let i = 0; i < period; i++) sum += values[i];
  out[period - 1] = sum / period;
  for (let i = period; i < values.length; i++) {
    sum += values[i] - values[i - period];
    out[i] = sum / period;
  }
  return out;
}

export function ema(values: number[], period: number): Series {
  const out: Series = new Array(values.length).fill(null);
  if (period <= 0 || values.length < period) return out;
  const k = 2 / (period + 1);
  let seed = 0;
  for (let i = 0; i < period; i++) seed += values[i];
  let prev = seed / period;
  out[period - 1] = prev;
  for (let i = period; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export interface BollingerBands {
  middle: Series;
  upper: Series;
  lower: Series;
}

export function bollinger(
  values: number[],
  period: number,
  stddev: number,
): BollingerBands {
  const middle = sma(values, period);
  const upper: Series = new Array(values.length).fill(null);
  const lower: Series = new Array(values.length).fill(null);
  for (let i = period - 1; i < values.length; i++) {
    const mid = middle[i];
    if (mid == null) continue;
    let sq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const d = values[j] - mid;
      sq += d * d;
    }
    const sd = Math.sqrt(sq / period);
    upper[i] = mid + stddev * sd;
    lower[i] = mid - stddev * sd;
  }
  return { middle, upper, lower };
}

// Wilder's RSI
export function rsi(values: number[], period: number): Series {
  const out: Series = new Array(values.length).fill(null);
  if (period <= 0 || values.length <= period) return out;
  let gainSum = 0;
  let lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];
    if (diff >= 0) gainSum += diff;
    else lossSum -= diff;
  }
  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i] - values[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

export interface StochasticSlow {
  k: Series;
  d: Series;
}

// Slow stochastic: raw %K = (close - low_n) / (high_n - low_n) * 100,
// then slow %K = SMA(raw %K, slowing), %D = SMA(slow %K, dPeriod).
// Without OHLC we approximate high/low from close window (close-only data).
export function stochasticSlow(
  closes: number[],
  kPeriod: number,
  slowing: number,
  dPeriod: number,
): StochasticSlow {
  const n = closes.length;
  const raw: Series = new Array(n).fill(null);
  for (let i = kPeriod - 1; i < n; i++) {
    let hi = -Infinity;
    let lo = Infinity;
    for (let j = i - kPeriod + 1; j <= i; j++) {
      if (closes[j] > hi) hi = closes[j];
      if (closes[j] < lo) lo = closes[j];
    }
    const range = hi - lo;
    raw[i] = range === 0 ? 50 : ((closes[i] - lo) / range) * 100;
  }
  const k = smaOfSeries(raw, slowing);
  const d = smaOfSeries(k, dPeriod);
  return { k, d };
}

function smaOfSeries(values: Series, period: number): Series {
  const out: Series = new Array(values.length).fill(null);
  if (period <= 1) {
    for (let i = 0; i < values.length; i++) out[i] = values[i];
    return out;
  }
  for (let i = period - 1; i < values.length; i++) {
    let sum = 0;
    let ok = true;
    for (let j = i - period + 1; j <= i; j++) {
      const v = values[j];
      if (v == null) {
        ok = false;
        break;
      }
      sum += v;
    }
    if (ok) out[i] = sum / period;
  }
  return out;
}
