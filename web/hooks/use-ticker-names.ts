"use client";
import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchTickerNames, resolveDisplayName } from "@/lib/ticker-names";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

/**
 * 티커 목록의 표시명을 한 번의 요청으로 가져온다.
 *
 * 맵을 그대로 노출하지 않고 nameOf 를 반환하는 이유: 호출부가 names[ticker] 를
 * 직접 쓰면 대소문자 불일치로 조용히 miss 가 난다(서버는 대문자 키로 응답한다).
 * nameOf 가 정규화를 소유한다.
 *
 * 이름은 거의 변하지 않으므로 staleTime 을 24시간으로 둔다. 서버가 30일 TTL 로
 * 갱신하므로 클라이언트가 자주 물어볼 이유가 없다.
 */
export function useTickerNames(tickers: string[]) {
  // queryKey 는 안정적이어야 한다. 매 렌더마다 새 배열이 와도 같은 키를 만든다.
  const key = useMemo(
    () =>
      Array.from(new Set(tickers.map((t) => t.trim().toUpperCase()).filter(Boolean)))
        .sort()
        .join(","),
    [tickers],
  );

  const { data, isLoading } = useQuery({
    queryKey: ["ticker-names", key],
    queryFn: ({ signal }) => fetchTickerNames(key.split(","), signal),
    staleTime: ONE_DAY_MS,
    enabled: key.length > 0,
  });

  const nameOf = useCallback(
    (ticker: string) => resolveDisplayName(data, ticker),
    [data],
  );

  return { nameOf, isLoading };
}
