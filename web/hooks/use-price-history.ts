"use client";
import { useQuery } from "@tanstack/react-query";
import { getPriceHistory } from "@/lib/prices";

export function usePriceHistory(ticker: string | undefined, days: number = 90) {
  return useQuery({
    queryKey: ["prices", ticker, days],
    queryFn: () => getPriceHistory(ticker!, days),
    enabled: !!ticker,
    staleTime: 60_000,
  });
}
