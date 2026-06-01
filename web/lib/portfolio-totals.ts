import { currencyForTicker, toUsd } from "./currency";

/** 합계 계산에 필요한 보유 종목의 최소 형태. */
export interface TotalsInput {
  ticker: string;
  qty: number;
  avg_cost: number;
}

export interface PortfolioTotals {
  /** 평가액(USD 기준). 전 종목이 가격·정규화 가능할 때만, 아니면 null. */
  value: number | null;
  /** 매입 원가(USD 기준). 정규화 가능할 때만, 아니면 null. */
  cost: number | null;
  /** 평가손익(USD 기준). value/cost가 모두 유효할 때만. */
  pnl: number | null;
  /** 손익률(%). */
  pnlPct: number | null;
  /** 보유 종목 수. */
  positions: number;
}

/**
 * 통화가 섞인 포트폴리오의 합계를 USD 기준으로 정규화해 계산한다.
 *
 * 각 종목의 원가·평가액을 ``toUsd``로 USD로 환산한 뒤 합산한다. 한국 종목이
 * 포함됐는데 환율이 없으면 정규화할 수 없어 해당 합계를 ``null``로 둔다. 표시
 * 측에서는 반환된 USD 값을 ``formatPrice(x, "USD", ctx)``로 표시 통화에 맞게
 * 환산한다.
 *
 * Args:
 *   items: 보유 종목(ticker/qty/avg_cost).
 *   prices: ticker별 현재가(원본 통화). 미가격이면 null/없음.
 *   fxRate: USD당 KRW 환율. 없으면 null.
 *
 * Returns:
 *   USD 기준으로 정규화된 합계.
 */
export function computePortfolioTotals(
  items: TotalsInput[],
  prices: Record<string, number | null>,
  fxRate: number | null,
): PortfolioTotals {
  let valueUsd = 0;
  let costUsd = 0;
  let priced = 0;
  // 환율이 없는데 KRW 종목이 있으면 합산 자체가 불가능하다.
  let normalizable = true;

  for (const h of items) {
    const cur = currencyForTicker(h.ticker);
    const costNorm = toUsd(h.qty * h.avg_cost, cur, fxRate);
    if (costNorm == null) {
      normalizable = false;
    } else {
      costUsd += costNorm;
    }

    const last = prices[h.ticker];
    if (last != null) {
      const valNorm = toUsd(h.qty * last, cur, fxRate);
      if (valNorm == null) {
        normalizable = false;
      } else {
        valueUsd += valNorm;
        priced += 1;
      }
    }
  }

  const positions = items.length;
  const fullyPriced = priced === positions && positions > 0 && normalizable;
  const cost = normalizable ? costUsd : null;
  const value = fullyPriced ? valueUsd : null;
  const pnl = value != null && cost != null ? value - cost : null;
  const pnlPct = pnl != null && cost != null && cost > 0 ? (pnl / cost) * 100 : null;

  return { value, cost, pnl, pnlPct, positions };
}
