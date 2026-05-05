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
