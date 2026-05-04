import { api } from "./api";

export interface FxRate {
  pair: "USDKRW";
  rate: number | null;
  as_of: string | null;
  fetched_at: string;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function getUsdKrwRate(): Promise<FxRate> {
  return api(`${BASE}/api/fx/usd-krw`);
}
