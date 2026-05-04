"use client";
import { useQuery } from "@tanstack/react-query";
import { getUsdKrwRate, FxRate } from "@/lib/fx";

const TWELVE_HOURS_MS = 12 * 60 * 60 * 1000;

export function useFxRate() {
  return useQuery<FxRate>({
    queryKey: ["fx", "usd-krw"],
    queryFn: getUsdKrwRate,
    staleTime: TWELVE_HOURS_MS,
    gcTime: TWELVE_HOURS_MS,
    refetchOnWindowFocus: false,
  });
}
