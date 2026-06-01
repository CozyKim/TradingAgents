"use client";
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useFxRate } from "@/hooks/use-fx-rate";

export type Currency = "USD" | "KRW";

export interface CurrencyCtx {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  toggle: () => void;
  fxRate: number | null;
  fxAsOf: string | null;
  fxLoading: boolean;
}

const STORAGE_KEY = "currency-preference";

const CurrencyContext = createContext<CurrencyCtx | null>(null);

function readSaved(): Currency {
  if (typeof window === "undefined") return "USD";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "USD" || saved === "KRW" ? saved : "USD";
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  // First render is always "USD" to avoid SSR/hydration mismatch.
  const [currency, setCurrencyState] = useState<Currency>("USD");
  const { data, isLoading } = useFxRate();

  useEffect(() => {
    setCurrencyState(readSaved());
  }, []);

  const setCurrency = useCallback((c: Currency) => {
    setCurrencyState(c);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, c);
    }
  }, []);

  const fxRate = data?.rate ?? null;
  const effective: Currency = currency === "KRW" && fxRate == null ? "USD" : currency;

  const toggle = useCallback(() => {
    setCurrency(effective === "USD" ? "KRW" : "USD");
  }, [effective, setCurrency]);

  const value: CurrencyCtx = {
    currency: effective,
    setCurrency,
    toggle,
    fxRate,
    fxAsOf: data?.as_of ?? null,
    fxLoading: isLoading,
  };

  return (
    <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
  );
}

export function useCurrency(): CurrencyCtx {
  const ctx = useContext(CurrencyContext);
  if (!ctx) {
    throw new Error("useCurrency must be used inside <CurrencyProvider>");
  }
  return ctx;
}

// KRX 종목은 6자리 코드 + 시장 접미사(KOSPI .KS / KOSDAQ .KQ)로 끝나고
// 원화로 호가된다. 미국 등 그 외 시장은 달러로 호가된다고 가정한다.
const KRW_SUFFIX_RE = /\.(KS|KQ)$/i;

/**
 * 종목 ticker의 거래소 원본(호가) 통화를 판별한다.
 *
 * Args:
 *   ticker: 종목 심볼(예: "005930.KS", "AAPL").
 *
 * Returns:
 *   ".KS"/".KQ"로 끝나면 "KRW", 그 외에는 "USD".
 */
export function currencyForTicker(ticker: string): Currency {
  return KRW_SUFFIX_RE.test(ticker.trim()) ? "KRW" : "USD";
}

/**
 * 종목 원본 통화 값을 USD 기준으로 정규화한다.
 *
 * 통화가 섞인 포트폴리오 합계를 한 통화로 더하기 위해 사용한다. KRW 값은
 * fxRate(USD당 KRW)로 나눈다. 환율이 없으면 정규화할 수 없어 ``null``을 반환하며,
 * 호출자는 이를 "합산 불가"로 처리해야 한다.
 *
 * Args:
 *   value: 원본 통화 기준 금액.
 *   sourceCurrency: ``value``의 원본 통화.
 *   fxRate: USD당 KRW 환율. 없으면 ``null``.
 *
 * Returns:
 *   USD 기준 금액, 또는 정규화 불가/무효 입력 시 ``null``.
 */
export function toUsd(
  value: number | null | undefined,
  sourceCurrency: Currency,
  fxRate: number | null,
): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  if (sourceCurrency === "USD") return value;
  if (fxRate == null) return null;
  return value / fxRate;
}

/**
 * 가격을 표시 통화로 포맷한다.
 *
 * ``value``는 ``sourceCurrency``(종목 거래소 원본 통화)로 호가된 값이다. 표시
 * 통화(``ctx.currency``)와 다르고 환율이 있으면 환산하고, 환율이 없으면 원본
 * 통화 그대로 표시한다(폴백). 같은 통화면 환산하지 않는다 — 한국 종목(원화)을
 * 원화로 볼 때 환율을 곱해 값이 부풀던 버그를 막는다.
 *
 * Args:
 *   value: 원본 통화 기준 금액. null/비유한이면 "—".
 *   sourceCurrency: ``value``의 원본 통화.
 *   ctx: 표시 통화와 환율.
 *   opts.signed: 양수 앞에 "+"를 붙인다.
 *   opts.usdDecimals: 달러 표시 소수 자릿수(기본 2). 원화는 항상 정수.
 *
 * Returns:
 *   통화 기호가 붙은 포맷 문자열.
 */
export function formatPrice(
  value: number | null | undefined,
  sourceCurrency: Currency,
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">,
  opts?: { signed?: boolean; usdDecimals?: number },
): string {
  if (value == null || !Number.isFinite(value)) return "—";

  const display = ctx.currency;
  const rate = ctx.fxRate;

  // 표시할 통화와 값을 결정한다: 원본==표시면 그대로, 다르고 환율이 있으면 환산,
  // 다르지만 환율이 없으면 원본 통화로 폴백.
  let outCurrency: Currency = sourceCurrency;
  let outValue = value;
  if (sourceCurrency !== display && rate != null) {
    outCurrency = display;
    outValue = sourceCurrency === "USD" ? value * rate : value / rate;
  }

  const isNeg = outValue < 0;
  const abs = Math.abs(outValue);
  const signPrefix = isNeg ? "-" : opts?.signed ? "+" : "";

  if (outCurrency === "KRW") {
    return `${signPrefix}₩${Math.round(abs).toLocaleString()}`;
  }

  const decimals = opts?.usdDecimals ?? 2;
  return `${signPrefix}$${abs.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}
