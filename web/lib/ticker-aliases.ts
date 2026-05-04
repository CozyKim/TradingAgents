// web/lib/ticker-aliases.ts
export type TickerEntry = {
  ticker: string;
  name: string;
  aliases: string[];
};

/**
 * 자주 쓰는 미국 종목 시드. 한글 별칭은 한국 증권사(토스증권/한국투자증권 등)
 * 거래 화면 표기를 우선. 신규 항목은 `aliases`에 한글/약칭을 추가하면 된다.
 *
 * NOTE: 더 광범위한 시드(S&P 500/나스닥 100)는 별도 Codex 생성 스크립트로 확장 예정.
 */
export const TICKER_SEED: readonly TickerEntry[] = [
  { ticker: "AAPL", name: "Apple Inc.", aliases: ["애플"] },
  { ticker: "MSFT", name: "Microsoft Corporation", aliases: ["마이크로소프트", "MS"] },
  { ticker: "GOOGL", name: "Alphabet Inc. Class A", aliases: ["알파벳A", "구글A", "구글", "알파벳"] },
  { ticker: "GOOG", name: "Alphabet Inc. Class C", aliases: ["알파벳C", "구글C", "구글", "알파벳"] },
  { ticker: "AMZN", name: "Amazon.com Inc.", aliases: ["아마존"] },
  { ticker: "META", name: "Meta Platforms Inc.", aliases: ["메타", "페이스북"] },
  { ticker: "NVDA", name: "NVIDIA Corporation", aliases: ["엔비디아"] },
  { ticker: "TSLA", name: "Tesla Inc.", aliases: ["테슬라"] },
  { ticker: "AMD", name: "Advanced Micro Devices Inc.", aliases: ["AMD", "에이엠디"] },
  { ticker: "INTC", name: "Intel Corporation", aliases: ["인텔"] },
  { ticker: "AVGO", name: "Broadcom Inc.", aliases: ["브로드컴"] },
  { ticker: "TSM", name: "Taiwan Semiconductor Manufacturing", aliases: ["TSMC", "대만반도체"] },
  { ticker: "ASML", name: "ASML Holding N.V.", aliases: ["ASML"] },
  { ticker: "NFLX", name: "Netflix Inc.", aliases: ["넷플릭스"] },
  { ticker: "DIS", name: "The Walt Disney Company", aliases: ["디즈니"] },
  { ticker: "ORCL", name: "Oracle Corporation", aliases: ["오라클"] },
  { ticker: "CRM", name: "Salesforce Inc.", aliases: ["세일즈포스"] },
  { ticker: "ADBE", name: "Adobe Inc.", aliases: ["어도비"] },
  { ticker: "PLTR", name: "Palantir Technologies Inc.", aliases: ["팔란티어"] },
  { ticker: "MSTR", name: "MicroStrategy Incorporated", aliases: ["마이크로스트래티지"] },
  { ticker: "COIN", name: "Coinbase Global Inc.", aliases: ["코인베이스"] },
  { ticker: "JPM", name: "JPMorgan Chase & Co.", aliases: ["JP모건", "제이피모건"] },
  { ticker: "BAC", name: "Bank of America Corporation", aliases: ["뱅크오브아메리카", "BoA"] },
  { ticker: "BRK.B", name: "Berkshire Hathaway Inc. Class B", aliases: ["버크셔B", "버크셔해서웨이B"] },
  { ticker: "BRK.A", name: "Berkshire Hathaway Inc. Class A", aliases: ["버크셔A", "버크셔해서웨이A"] },
  { ticker: "V", name: "Visa Inc.", aliases: ["비자"] },
  { ticker: "MA", name: "Mastercard Incorporated", aliases: ["마스터카드"] },
  { ticker: "SPY", name: "SPDR S&P 500 ETF Trust", aliases: ["S&P500", "스파이"] },
  { ticker: "QQQ", name: "Invesco QQQ Trust", aliases: ["나스닥100", "큐큐큐"] },
  { ticker: "VOO", name: "Vanguard S&P 500 ETF", aliases: ["뱅가드S&P500"] },
];
