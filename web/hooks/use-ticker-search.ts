"use client";
import * as React from "react";

import {
  hasHangul,
  mergeResults,
  searchTickers,
  type SearchResult,
} from "@/lib/ticker-search";
import { searchTickersRemote } from "@/lib/ticker-search-remote";

export type TickerSearchState = {
  /** 시드 결과와 원격 결과를 병합한 최종 목록 */
  results: SearchResult[];
  /** 원격 검색이 진행 중 */
  loading: boolean;
  /** 한글 질의인데 결과가 하나도 없을 때만 참 — 영문 자유 입력은 힌트를 띄우지 않는다 */
  showEmptyHint: boolean;
};

const DEBOUNCE_MS = 250;

/**
 * 티커 질의에 대한 시드+원격 검색 결과를 반환한다.
 *
 * 원격 호출은 250ms 디바운스되고 AbortController로 취소된다. 원격이 실패하면
 * 시드 결과만으로 degrade한다(AbortError는 정상 취소이므로 무시).
 */
export function useTickerSearch(query: string): TickerSearchState {
  const seedResults = React.useMemo<SearchResult[]>(() => {
    if (!query.trim()) return [];
    return searchTickers(query);
  }, [query]);

  const [remoteResults, setRemoteResults] = React.useState<SearchResult[]>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    const q = query.trim();
    if (!q) {
      setRemoteResults([]);
      setLoading(false);
      return;
    }
    // 질의가 바뀌면 이전 원격 결과를 즉시 비워, 디바운스/네트워크 대기 동안
    // stale 결과가 병합·선택되지 않게 한다.
    setRemoteResults([]);
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      searchTickersRemote(q, controller.signal)
        .then((remote) => {
          if (!controller.signal.aborted) setRemoteResults(remote);
        })
        .catch((err: unknown) => {
          // abort는 정상 취소이므로 무시. 그 외 실패는 원격 결과 비움(시드로 degrade).
          if ((err as { name?: string })?.name !== "AbortError") setRemoteResults([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const results = React.useMemo<SearchResult[]>(
    () => mergeResults(seedResults, remoteResults),
    [seedResults, remoteResults],
  );

  const showEmptyHint =
    !loading && results.length === 0 && query.trim().length > 0 && hasHangul(query);

  return { results, loading, showEmptyHint };
}
