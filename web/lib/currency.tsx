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

export function formatPrice(
  usdValue: number | null | undefined,
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">,
  opts?: { signed?: boolean; usdDecimals?: number },
): string {
  if (usdValue == null || !Number.isFinite(usdValue)) return "—";

  const isNeg = usdValue < 0;
  const abs = Math.abs(usdValue);
  const signPrefix = isNeg ? "-" : opts?.signed ? "+" : "";

  if (ctx.currency === "KRW" && ctx.fxRate != null) {
    const krw = Math.round(abs * ctx.fxRate);
    return `${signPrefix}₩${krw.toLocaleString()}`;
  }

  const decimals = opts?.usdDecimals ?? 2;
  return `${signPrefix}$${abs.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}
