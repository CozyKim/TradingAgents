import type { TickerEntry } from "./ticker-aliases";

// Lazily resolve TICKER_SEED so that test harnesses that inline `options.seed`
// can import this module without bundling ./ticker-aliases at load time.
function getDefaultSeed(): readonly TickerEntry[] {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return (require("./ticker-aliases") as { TICKER_SEED: readonly TickerEntry[] }).TICKER_SEED;
}

export type MatchedField = "ticker" | "name" | "alias";

export type SearchResult = {
  ticker: string;
  name: string;
  matched: MatchedField;
  matchedText: string;
  score: number;
};

export type SearchOptions = {
  limit?: number;
  seed?: readonly TickerEntry[];
};

const SCORE = {
  TICKER_EXACT: 1000,
  TICKER_PREFIX: 800,
  ALIAS_EXACT: 700,
  NAME_EXACT: 700,
  ALIAS_PREFIX: 500,
  NAME_PREFIX: 500,
  ALIAS_SUBSTRING: 300,
  NAME_SUBSTRING: 300,
} as const;

function normalize(s: string): string {
  return s.trim().normalize("NFC");
}

function matchOne(entry: TickerEntry, query: string, queryLower: string): SearchResult | null {
  const tickerLower = entry.ticker.toLowerCase();
  if (tickerLower === queryLower) {
    return { ticker: entry.ticker, name: entry.name, matched: "ticker", matchedText: entry.ticker, score: SCORE.TICKER_EXACT };
  }
  if (tickerLower.startsWith(queryLower)) {
    return { ticker: entry.ticker, name: entry.name, matched: "ticker", matchedText: entry.ticker, score: SCORE.TICKER_PREFIX };
  }

  for (const alias of entry.aliases) {
    const aliasNorm = normalize(alias);
    const aliasLower = aliasNorm.toLowerCase();
    if (aliasNorm === query || aliasLower === queryLower) {
      return { ticker: entry.ticker, name: entry.name, matched: "alias", matchedText: aliasNorm, score: SCORE.ALIAS_EXACT };
    }
  }
  for (const alias of entry.aliases) {
    const aliasLower = normalize(alias).toLowerCase();
    if (aliasLower.startsWith(queryLower)) {
      return { ticker: entry.ticker, name: entry.name, matched: "alias", matchedText: alias, score: SCORE.ALIAS_PREFIX };
    }
  }

  const nameLower = entry.name.toLowerCase();
  if (nameLower === queryLower) {
    return { ticker: entry.ticker, name: entry.name, matched: "name", matchedText: entry.name, score: SCORE.NAME_EXACT };
  }
  if (nameLower.startsWith(queryLower)) {
    return { ticker: entry.ticker, name: entry.name, matched: "name", matchedText: entry.name, score: SCORE.NAME_PREFIX };
  }

  for (const alias of entry.aliases) {
    const aliasLower = normalize(alias).toLowerCase();
    if (aliasLower.includes(queryLower)) {
      return { ticker: entry.ticker, name: entry.name, matched: "alias", matchedText: alias, score: SCORE.ALIAS_SUBSTRING };
    }
  }
  if (nameLower.includes(queryLower)) {
    return { ticker: entry.ticker, name: entry.name, matched: "name", matchedText: entry.name, score: SCORE.NAME_SUBSTRING };
  }
  return null;
}

export function searchTickers(query: string, options: SearchOptions = {}): SearchResult[] {
  const seed = options.seed ?? getDefaultSeed();
  const limit = options.limit ?? 10;
  const q = normalize(query);
  if (!q) return [];
  const qLower = q.toLowerCase();

  const results: SearchResult[] = [];
  for (const entry of seed) {
    const r = matchOne(entry, q, qLower);
    if (r) results.push(r);
  }
  results.sort((a, b) => b.score - a.score);
  return results.slice(0, limit);
}

export type CommitResult =
  | { status: "ok"; ticker: string }
  | { status: "empty" }
  | { status: "needs_selection"; candidates: SearchResult[] }
  | { status: "invalid"; reason: "english_pattern" | "korean_no_match" | "mixed" };

const TICKER_PATTERN = /^[A-Z][A-Z0-9.\-]{0,15}$/;
const HANGUL_RE = /[ㄱ-ㆎ가-힣]/;

export function commitInput(raw: string, options: SearchOptions = {}): CommitResult {
  const q = normalize(raw);
  if (!q) return { status: "empty" };

  const hasHangul = HANGUL_RE.test(q);
  const upper = q.toUpperCase();

  // 1단계: 한글/영문/특수문자 불문하고 시드 정확일치(ticker 또는 alias) 먼저 시도
  //        searchTickers는 score 기준 내림차순으로 정렬해 반환하므로 EXACT 점수 항목만 필터링
  const seed = options.seed ?? getDefaultSeed();
  const qLower = q.toLowerCase();
  const exactHits: SearchResult[] = [];
  for (const entry of seed) {
    // ticker 정확일치
    if (entry.ticker.toLowerCase() === qLower) {
      exactHits.push({
        ticker: entry.ticker,
        name: entry.name,
        matched: "ticker",
        matchedText: entry.ticker,
        score: SCORE.TICKER_EXACT,
      });
      continue;
    }
    // alias 정확일치 (NFC 정규화 + 대소문자 무시)
    for (const alias of entry.aliases) {
      if (normalize(alias).toLowerCase() === qLower) {
        exactHits.push({
          ticker: entry.ticker,
          name: entry.name,
          matched: "alias",
          matchedText: alias,
          score: SCORE.ALIAS_EXACT,
        });
        break;
      }
    }
  }

  if (exactHits.length === 1) {
    return { status: "ok", ticker: exactHits[0].ticker };
  }
  if (exactHits.length > 1) {
    return { status: "needs_selection", candidates: exactHits };
  }

  // 2단계: 정확일치 없음 → 한글 포함 여부로 분기

  // 한글 포함 → 부분일치 결과 확인
  if (hasHangul) {
    const results = searchTickers(q, options);
    if (results.length > 0) {
      return { status: "needs_selection", candidates: results };
    }
    // 시드에 매치 없음 → 한글+영문 혼합 여부 재판단
    if (/[A-Z0-9]/.test(upper.replace(/[ㄱ-ㆎ가-힣]/g, ""))) {
      return { status: "invalid", reason: "mixed" };
    }
    return { status: "invalid", reason: "korean_no_match" };
  }

  // 한글+영문 혼합 (hangul 없이 특수문자만 있는 경우는 아래 패턴에서 걸림)
  const hasNonHangulNonTickerChar = /[^A-Z0-9.\-ㄱ-ㆎ가-힣]/.test(upper);
  if (hasNonHangulNonTickerChar) {
    return { status: "invalid", reason: "english_pattern" };
  }

  // 3단계: 영문 전용 → 패턴 검사 후 통과면 대문자 티커로 확정
  if (TICKER_PATTERN.test(upper)) {
    return { status: "ok", ticker: upper };
  }
  return { status: "invalid", reason: "english_pattern" };
}
