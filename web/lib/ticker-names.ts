import { api } from "./api";

/** 티커를 서버 응답 키와 같은 형태(대문자·공백 제거)로 정규화한다. */
function normalize(ticker: string): string {
  return ticker.trim().toUpperCase();
}

/**
 * 티커 목록을 표시명(한글 우선)으로 해석한다.
 * 빈 목록은 네트워크 호출 없이 {} 를 반환한다. AbortSignal 로 취소 가능.
 *
 * 해석에 실패한 티커는 응답에 키가 없다 — 호출부는 키 부재를 "이름 없음"으로 읽는다.
 */
export async function fetchTickerNames(
  tickers: string[],
  signal?: AbortSignal,
): Promise<Record<string, string>> {
  const list = Array.from(new Set(tickers.map(normalize).filter(Boolean)));
  if (list.length === 0) return {};
  const data = await api<{ names: Record<string, string> }>(
    `/api/tickers/names?tickers=${encodeURIComponent(list.join(","))}`,
    { signal },
  );
  return data.names;
}

/**
 * 해석 결과 맵에서 티커의 표시명을 찾는다.
 * 서버는 대문자 키로 응답하므로 조회 시 정규화가 필요하다 — 이 함수가 그것을 소유한다.
 */
export function resolveDisplayName(
  names: Record<string, string> | undefined,
  ticker: string,
): string | undefined {
  return names?.[normalize(ticker)];
}
