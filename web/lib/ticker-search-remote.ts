import { api } from "./api";
import type { SearchResult } from "./ticker-search";

type RemoteRow = { ticker: string; name: string; market: "US" | "KR"; exchange?: string | null };

/**
 * 백엔드 실시간 검색을 호출해 SearchResult 배열로 매핑한다.
 * 빈 질의는 네트워크 호출 없이 빈 배열을 반환한다. AbortSignal 로 취소 가능.
 */
export async function searchTickersRemote(
  query: string,
  signal?: AbortSignal,
): Promise<SearchResult[]> {
  const q = query.trim();
  if (!q) return [];
  const data = await api<{ results: RemoteRow[] }>(
    `/api/tickers/search?q=${encodeURIComponent(q)}`,
    { signal },
  );
  return data.results.map((r) => ({
    ticker: r.ticker,
    name: r.name,
    matched: "name" as const,
    matchedText: r.name,
    score: 0,
  }));
}
