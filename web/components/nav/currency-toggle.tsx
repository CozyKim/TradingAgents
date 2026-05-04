"use client";
import { useCurrency } from "@/lib/currency";
import { cn } from "@/lib/utils";

/**
 * Segmented USD/KRW toggle. Renders compact (icon-sized) or wide (with
 * `as_of` footnote) depending on the `compact` prop.
 *
 * KRW button is disabled when fxRate is unavailable.
 */
export function CurrencyToggle({ compact = false }: { compact?: boolean }) {
  const { currency, setCurrency, fxRate, fxAsOf } = useCurrency();
  const krwDisabled = fxRate == null;

  const btn = (active: boolean, disabled: boolean) =>
    cn(
      "px-2 py-1 text-[11px] font-semibold tracking-[-0.01em] transition-colors rounded-md",
      active
        ? "bg-text-1 text-bg-1"
        : disabled
        ? "text-text-3/40 cursor-not-allowed"
        : "text-text-3 hover:text-text-1",
    );

  return (
    <div className="flex flex-col items-end gap-0.5">
      <div
        role="group"
        aria-label="표시 통화 선택"
        className="inline-flex items-center gap-0.5 rounded-lg border border-border-1 bg-bg-1 p-0.5"
      >
        <button
          type="button"
          className={btn(currency === "USD", false)}
          onClick={() => setCurrency("USD")}
          aria-pressed={currency === "USD"}
        >
          USD
        </button>
        <button
          type="button"
          className={btn(currency === "KRW", krwDisabled)}
          onClick={() => !krwDisabled && setCurrency("KRW")}
          disabled={krwDisabled}
          aria-pressed={currency === "KRW"}
          title={
            krwDisabled
              ? "환율 정보를 불러올 수 없어 KRW 모드를 사용할 수 없습니다"
              : undefined
          }
        >
          KRW
        </button>
      </div>
      {!compact && currency === "KRW" && fxAsOf && (
        <span className="text-[10px] font-mono text-text-3">as of {fxAsOf}</span>
      )}
    </div>
  );
}
