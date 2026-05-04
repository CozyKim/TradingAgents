# 한글/영문 통합 티커 검색 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run/Holding/Schedule 폼의 티커 입력을 한글 별칭(예: `알파벳A` → `GOOGL`)으로도 검색 가능한 공용 autocomplete 컴포넌트로 교체하면서, 한글 미확정 입력이 백엔드로 누수되지 않도록 막는다.

**Architecture:** 정적 시드 데이터(`web/lib/ticker-aliases.ts`) + 순수 검색/검증 로직(`web/lib/ticker-search.ts`) + Radix Popover 기반 공용 컴포넌트(`web/components/ui/ticker-combobox.tsx`)로 분리. 컴포넌트는 검색어(query)와 확정 티커(committed ticker)를 분리해 한글/패턴 미달 입력은 부모 폼으로 전달하지 않는다.

**Tech Stack:** Next.js 14, React 18, TypeScript, Radix UI Popover, Node.js 내장 `node:test` (기존 `web/lib/*.test.cjs` 패턴)

**Spec:** `docs/superpowers/specs/2026-05-05-ticker-korean-search-design.md`

**Per-task Codex review:** 각 Task의 commit 직후에 Codex로 변경 사항을 리뷰한다. 리뷰 결과는 verbatim으로 사용자에게 보여주고, **사용자 확인 전까지 자동 수정하지 않는다**. 리뷰 명령(공통):

```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```

리뷰가 `pass`면 다음 Task로 진행. `needs-attention` 이상이면 사용자에게 결과를 보여주고 후속 조치 결정을 받는다.

---

## File Structure

| Path | 역할 | 신규/수정 |
|------|------|----------|
| `web/lib/ticker-aliases.ts` | 시드 데이터(영문 티커 + 회사명 + 한글 별칭) | 신규 |
| `web/lib/ticker-search.ts` | 순수 검색/매칭 + 입력 확정(검증) 로직 | 신규 |
| `web/lib/ticker-search.test.cjs` | 검색/확정 유닛 테스트 | 신규 |
| `web/components/ui/ticker-combobox.tsx` | 공용 autocomplete 컴포넌트 | 신규 |
| `web/components/run/run-form.tsx` | 티커 input → TickerCombobox로 교체 | 수정 |
| `web/components/portfolio/holding-form.tsx` | 동일 | 수정 |
| `web/components/schedules/schedule-form.tsx` | 다중 티커 → 칩 UX 리팩터 | 수정 |

각 파일은 단일 책임을 가진다: 시드(데이터), 검색/검증(순수 로직), 컴포넌트(렌더링/UX), 폼(통합).

---

## Task 1: 시드 데이터 파일 작성

자주 쓰는 미국 종목 ~30개의 영문 티커/회사명/한글 별칭을 직접 작성한다. 전체 S&P 500/나스닥 100 확장은 추후 별도 Codex 스크립트 작업으로 분리(이 플랜 범위 밖). 30개로도 검색 동작 검증과 후속 작업 통합에 충분하다.

**Files:**
- Create: `web/lib/ticker-aliases.ts`

- [ ] **Step 1: 시드 파일 생성**

```ts
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
```

- [ ] **Step 2: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS (이 시점에는 시드 파일을 import하는 코드가 없으므로 무관한 타입 에러만 없으면 OK)

- [ ] **Step 3: Commit**

```bash
git add web/lib/ticker-aliases.ts
git commit -m "feat(web): seed ticker aliases for korean search"
```

- [ ] **Step 4: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과(verdict) 출력. verdict가 `pass`면 다음 Task로. `needs-attention` 이상이면 결과를 사용자에게 verbatim으로 전달하고 후속 조치 결정을 받는다(자동 수정 금지).

---

## Task 2: 검색 로직 + 테스트 (TDD)

순수 함수 `searchTickers(query, options)`를 테스트 우선으로 구현한다. 매칭 우선순위는 스펙 §3.2 따름.

**Files:**
- Create: `web/lib/ticker-search.ts`
- Create: `web/lib/ticker-search.test.cjs`

- [ ] **Step 1: 실패 테스트 작성**

```js
// web/lib/ticker-search.test.cjs
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const Module = require("node:module");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

function loadTsModule(relativePath) {
  const filename = path.join(__dirname, relativePath);
  const source = readFileSync(filename, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
    fileName: filename,
  });
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(__dirname);
  mod._compile(outputText, filename);
  return mod.exports;
}

const SEED = [
  { ticker: "AAPL", name: "Apple Inc.", aliases: ["애플"] },
  { ticker: "GOOGL", name: "Alphabet Inc. Class A", aliases: ["알파벳A", "구글A", "구글", "알파벳"] },
  { ticker: "GOOG", name: "Alphabet Inc. Class C", aliases: ["알파벳C", "구글C", "구글", "알파벳"] },
  { ticker: "TSLA", name: "Tesla Inc.", aliases: ["테슬라"] },
  { ticker: "BRK.B", name: "Berkshire Hathaway Inc. Class B", aliases: ["버크셔B"] },
];

test("searchTickers: empty query returns empty array", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  assert.deepEqual(searchTickers("", { seed: SEED }), []);
  assert.deepEqual(searchTickers("   ", { seed: SEED }), []);
});

test("searchTickers: ticker exact match scores highest", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("AAPL", { seed: SEED });
  assert.equal(out[0].ticker, "AAPL");
  assert.equal(out[0].matched, "ticker");
});

test("searchTickers: ticker prefix matches case-insensitively", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("goo", { seed: SEED });
  const tickers = out.map((r) => r.ticker);
  assert.ok(tickers.includes("GOOGL"));
  assert.ok(tickers.includes("GOOG"));
});

test("searchTickers: korean alias exact match", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("알파벳A", { seed: SEED });
  assert.equal(out[0].ticker, "GOOGL");
  assert.equal(out[0].matched, "alias");
});

test("searchTickers: korean alias prefix match", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("알파", { seed: SEED });
  const tickers = out.map((r) => r.ticker);
  assert.ok(tickers.includes("GOOGL"));
  assert.ok(tickers.includes("GOOG"));
});

test("searchTickers: korean alias substring match", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("벳A", { seed: SEED });
  assert.equal(out[0].ticker, "GOOGL");
});

test("searchTickers: english company name substring match", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("alphabet", { seed: SEED });
  const tickers = out.map((r) => r.ticker);
  assert.ok(tickers.includes("GOOGL"));
});

test("searchTickers: no match returns empty", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  assert.deepEqual(searchTickers("ZZZ존재하지않음", { seed: SEED }), []);
});

test("searchTickers: respects limit option", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("구글", { seed: SEED, limit: 1 });
  assert.equal(out.length, 1);
});

test("searchTickers: dot-containing ticker matches by prefix", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  const out = searchTickers("BRK", { seed: SEED });
  assert.ok(out.some((r) => r.ticker === "BRK.B"));
});

test("searchTickers: prioritizes exact > prefix > substring", () => {
  const { searchTickers } = loadTsModule("ticker-search.ts");
  // "구글"은 GOOGL/GOOG 두 시드의 alias 정확일치 → 둘 다 같은 점수권
  // "구"는 prefix이므로 그보다 낮은 점수
  const exactOut = searchTickers("구글", { seed: SEED });
  const prefixOut = searchTickers("구", { seed: SEED });
  // 정확일치 결과의 score가 prefix 결과 score보다 큼
  assert.ok(exactOut[0].score > prefixOut[0].score);
});
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `node web/lib/ticker-search.test.cjs`
Expected: 모든 테스트 FAIL (`Cannot find module ./ticker-search.ts` 또는 함수 미정의)

- [ ] **Step 3: 검색 로직 구현**

```ts
// web/lib/ticker-search.ts
import { TICKER_SEED, type TickerEntry } from "./ticker-aliases";

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
  const seed = options.seed ?? TICKER_SEED;
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
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `node web/lib/ticker-search.test.cjs`
Expected: 모든 테스트 PASS

- [ ] **Step 5: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/lib/ticker-search.ts web/lib/ticker-search.test.cjs
git commit -m "feat(web): ticker search with korean alias support"
```

- [ ] **Step 7: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과 출력. verdict 처리는 Task 1 Step 4와 동일.

---

## Task 3: 입력 확정(검증) 로직 + 테스트

스펙 §4.4의 자유 입력 가드를 순수 함수로 구현한다. 한글 미확정/패턴 미달 입력을 컴포넌트 진입 전에 차단할 수 있게 한다.

**Files:**
- Modify: `web/lib/ticker-search.ts` (export 추가)
- Modify: `web/lib/ticker-search.test.cjs` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가**

`web/lib/ticker-search.test.cjs` 파일 끝에 다음 테스트들을 **추가**한다(기존 테스트는 그대로):

```js
test("commitInput: empty input returns empty status", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  assert.deepEqual(commitInput("", { seed: SEED }), { status: "empty" });
  assert.deepEqual(commitInput("   ", { seed: SEED }), { status: "empty" });
});

test("commitInput: english ticker pattern accepted", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  assert.deepEqual(commitInput("MSTR", { seed: SEED }), { status: "ok", ticker: "MSTR" });
  assert.deepEqual(commitInput("mstr", { seed: SEED }), { status: "ok", ticker: "MSTR" });
});

test("commitInput: dot/hyphen tickers accepted", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  assert.deepEqual(commitInput("BRK.B", { seed: SEED }), { status: "ok", ticker: "BRK.B" });
  assert.deepEqual(commitInput("BF-B", { seed: SEED }), { status: "ok", ticker: "BF-B" });
});

test("commitInput: korean exact alias auto-resolves to ticker", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  assert.deepEqual(commitInput("알파벳A", { seed: SEED }), { status: "ok", ticker: "GOOGL" });
  assert.deepEqual(commitInput("애플", { seed: SEED }), { status: "ok", ticker: "AAPL" });
});

test("commitInput: korean ambiguous alias requires user selection", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // "구글" matches both GOOGL and GOOG → cannot auto-commit
  const result = commitInput("구글", { seed: SEED });
  assert.equal(result.status, "needs_selection");
});

test("commitInput: korean partial input is invalid", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // "알파" matches by prefix but is not exact alias → invalid
  const result = commitInput("알파", { seed: SEED });
  assert.equal(result.status, "needs_selection");
});

test("commitInput: korean with no match is invalid", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  const result = commitInput("존재하지않는한글", { seed: SEED });
  assert.equal(result.status, "invalid");
  assert.equal(result.reason, "korean_no_match");
});

test("commitInput: english pattern violation is invalid", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  assert.equal(commitInput("MSTR!", { seed: SEED }).status, "invalid");
  assert.equal(commitInput("MSTR ABC", { seed: SEED }).status, "invalid");
  // 0 chars 정확히 한 글자 영문은 패턴 미달 (16자 초과도 미달)
  assert.equal(commitInput("ABCDEFGHIJKLMNOPQ", { seed: SEED }).status, "invalid");
});

test("commitInput: mixed korean+english is invalid", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  assert.equal(commitInput("알파벳GOOGL", { seed: SEED }).status, "invalid");
});
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `node web/lib/ticker-search.test.cjs`
Expected: 신규 테스트들 FAIL (`commitInput is not a function`)

- [ ] **Step 3: commitInput 구현**

`web/lib/ticker-search.ts` 끝에 다음을 **추가**:

```ts
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
  const hasNonHangulNonTickerChar = /[^A-Z0-9.\-ㄱ-ㆎ가-힣]/.test(upper);

  // 한글 + 영문/숫자 혼합 → 무효
  if (hasHangul && /[A-Z0-9]/.test(upper.replace(/[ㄱ-ㆎ가-힣]/g, ""))) {
    return { status: "invalid", reason: "mixed" };
  }
  // 공백/특수문자 포함 → 무효
  if (hasNonHangulNonTickerChar) {
    return { status: "invalid", reason: hasHangul ? "korean_no_match" : "english_pattern" };
  }

  // 한글 단독 → 시드 정확일치 시 자동 변환, 모호하면 선택 요구, 매치 없으면 무효
  if (hasHangul) {
    const results = searchTickers(q, options);
    const exactAliasHits = results.filter((r) => r.matched === "alias" && r.score >= SCORE.ALIAS_EXACT);
    if (exactAliasHits.length === 1) {
      return { status: "ok", ticker: exactAliasHits[0].ticker };
    }
    if (exactAliasHits.length > 1 || results.length > 0) {
      return { status: "needs_selection", candidates: results };
    }
    return { status: "invalid", reason: "korean_no_match" };
  }

  // 영문 → 패턴 검사 후 통과면 대문자 티커로 확정
  if (TICKER_PATTERN.test(upper)) {
    return { status: "ok", ticker: upper };
  }
  return { status: "invalid", reason: "english_pattern" };
}
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `node web/lib/ticker-search.test.cjs`
Expected: 모든 테스트 PASS

- [ ] **Step 5: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/lib/ticker-search.ts web/lib/ticker-search.test.cjs
git commit -m "feat(web): ticker input commit guard (korean/pattern validation)"
```

- [ ] **Step 7: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과 출력. verdict 처리는 Task 1 Step 4와 동일. (가드 로직이 보안/검증 영역이므로 특히 주의 깊게 본다.)

---

## Task 4: TickerCombobox 공용 컴포넌트

스펙 §4의 인라인 popover autocomplete. 검색어/확정 티커 분리, 키보드/마우스 인터랙션, 한글 미확정 시 invalid 상태.

**Files:**
- Create: `web/components/ui/ticker-combobox.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
// web/components/ui/ticker-combobox.tsx
"use client";
import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";

import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { searchTickers, commitInput, type SearchResult } from "@/lib/ticker-search";
import { cn } from "@/lib/utils";

export type TickerComboboxProps = {
  value: string;
  onChange: (ticker: string) => void;
  onValidityChange?: (valid: boolean) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  className?: string;
};

export function TickerCombobox({
  value,
  onChange,
  onValidityChange,
  placeholder,
  required,
  id,
  disabled,
  autoFocus,
  className,
}: TickerComboboxProps) {
  const [query, setQuery] = React.useState(value);
  const [highlight, setHighlight] = React.useState(0);
  const [open, setOpen] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const listboxId = React.useId();

  // 부모가 value를 외부에서 바꾼 경우(예: form reset) query 동기화
  React.useEffect(() => {
    if (value !== query && document.activeElement?.id !== id) {
      setQuery(value);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const results = React.useMemo<SearchResult[]>(() => {
    if (!query.trim()) return [];
    return searchTickers(query);
  }, [query]);

  React.useEffect(() => {
    if (highlight >= results.length) setHighlight(0);
  }, [results.length, highlight]);

  const setValid = (valid: boolean) => {
    onValidityChange?.(valid);
  };

  const commit = (raw: string): boolean => {
    const result = commitInput(raw);
    if (result.status === "ok") {
      onChange(result.ticker);
      setQuery(result.ticker);
      setError(null);
      setOpen(false);
      setValid(true);
      return true;
    }
    if (result.status === "empty") {
      onChange("");
      setError(null);
      setValid(true);
      return true;
    }
    if (result.status === "needs_selection") {
      setError("목록에서 선택해주세요");
      setValid(false);
      setOpen(true);
      return false;
    }
    setError(
      result.reason === "korean_no_match"
        ? "검색 결과가 없습니다"
        : result.reason === "mixed"
          ? "한글과 영문을 섞어 입력할 수 없습니다"
          : "올바른 영문 티커 형식이 아닙니다",
    );
    setValid(false);
    return false;
  };

  const selectResult = (r: SearchResult) => {
    onChange(r.ticker);
    setQuery(r.ticker);
    setError(null);
    setOpen(false);
    setValid(true);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" && results.length > 0) {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(results.length - 1, h + 1));
      return;
    }
    if (e.key === "ArrowUp" && results.length > 0) {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.max(0, h - 1));
      return;
    }
    if (e.key === "Enter") {
      if (open && results[highlight]) {
        e.preventDefault();
        selectResult(results[highlight]);
        return;
      }
      // 자유 입력 확정 시도 — 폼 제출은 commit 결과에 따라 막거나 허용
      if (!commit(query)) {
        e.preventDefault();
      }
      return;
    }
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
  };

  const onBlur = () => {
    // 약간의 지연 — 옵션 클릭이 먼저 처리되도록
    setTimeout(() => {
      if (!open) commit(query);
    }, 100);
  };

  return (
    <Popover open={open && results.length > 0} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div className={cn("relative", className)}>
          <Input
            id={id}
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-activedescendant={results[highlight] ? `${listboxId}-${highlight}` : undefined}
            aria-invalid={error !== null || undefined}
            aria-autocomplete="list"
            autoComplete="off"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setError(null);
              setOpen(true);
              setValid(false); // 사용자가 다시 타이핑 중 — 미확정
            }}
            onFocus={() => results.length > 0 && setOpen(true)}
            onBlur={onBlur}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            required={required}
            disabled={disabled}
            autoFocus={autoFocus}
            className={cn(
              "font-num font-bold uppercase tracking-[-0.02em]",
              error && "ring-1 ring-signal-sell focus-visible:ring-signal-sell",
            )}
          />
          {error && (
            <p className="mt-1 text-xs text-signal-sell" role="alert">
              {error}
            </p>
          )}
        </div>
      </PopoverAnchor>
      <PopoverContent
        id={listboxId}
        role="listbox"
        align="start"
        sideOffset={4}
        className="w-[var(--radix-popover-trigger-width)] p-1"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {results.map((r, i) => (
          <button
            key={`${r.ticker}-${i}`}
            id={`${listboxId}-${i}`}
            role="option"
            aria-selected={i === highlight}
            type="button"
            onMouseEnter={() => setHighlight(i)}
            onMouseDown={(e) => {
              e.preventDefault(); // blur 방지
              selectResult(r);
            }}
            className={cn(
              "flex w-full items-baseline justify-between gap-3 rounded-md px-3 py-2 text-left text-sm",
              i === highlight ? "bg-bg-2" : "hover:bg-bg-2",
            )}
          >
            <span className="font-num font-bold text-text-1">{r.ticker}</span>
            <span className="truncate text-xs text-text-3">
              {r.matched === "ticker" ? r.name : `${r.matchedText} · ${r.name}`}
            </span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS

(`text-signal-sell`은 기존 tailwind 토큰. 없으면 `text-red-500`으로 임시 대체)

- [ ] **Step 3: Commit**

```bash
git add web/components/ui/ticker-combobox.tsx
git commit -m "feat(web): TickerCombobox autocomplete with korean alias guard"
```

- [ ] **Step 4: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과 출력. verdict 처리는 Task 1 Step 4와 동일.

---

## Task 5: RunForm에 TickerCombobox 통합

`web/components/run/run-form.tsx`의 티커 `<Input>`을 `<TickerCombobox>`로 교체.

**Files:**
- Modify: `web/components/run/run-form.tsx`

- [ ] **Step 1: 변경 전 구조 확인**

Run: `grep -n "ticker\|Input" web/components/run/run-form.tsx | head -20`
Expected: 26번째 줄 부근에서 `setTicker`, 50~58번째 줄 부근에서 `<Input id="ticker"...>` 확인

- [ ] **Step 2: 컴포넌트 교체**

`web/components/run/run-form.tsx`에서:

기존(상단 import 추가):
```tsx
import { Input } from "@/components/ui/input";
```
밑에 다음 한 줄 추가:
```tsx
import { TickerCombobox } from "@/components/ui/ticker-combobox";
```

티커 input 섹션(현재 49–59번째 줄 부근):
```tsx
<div className="grid gap-2">
  <Label htmlFor="ticker">티커</Label>
  <Input
    id="ticker"
    value={ticker}
    onChange={(e) => setTicker(e.target.value)}
    placeholder="예: AAPL"
    className="font-num text-[18px] font-bold uppercase tracking-[-0.02em]"
    required
  />
</div>
```

다음으로 교체:
```tsx
<div className="grid gap-2">
  <Label htmlFor="ticker">티커</Label>
  <TickerCombobox
    id="ticker"
    value={ticker}
    onChange={setTicker}
    placeholder="예: AAPL 또는 애플"
    required
    className="text-[18px]"
  />
</div>
```

- [ ] **Step 3: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/components/run/run-form.tsx
git commit -m "feat(web/run-form): use TickerCombobox for korean ticker search"
```

- [ ] **Step 5: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과 출력. verdict 처리는 Task 1 Step 4와 동일.

---

## Task 6: HoldingForm에 TickerCombobox 통합

**Files:**
- Modify: `web/components/portfolio/holding-form.tsx`

- [ ] **Step 1: 컴포넌트 교체**

`web/components/portfolio/holding-form.tsx`에서:

기존 import 라인 위에 추가:
```tsx
import { TickerCombobox } from "@/components/ui/ticker-combobox";
```

티커 input 섹션(현재 38–47번째 줄 부근):
```tsx
<div>
  <Label htmlFor="ticker">Ticker</Label>
  <Input
    id="ticker"
    required
    value={ticker}
    onChange={(e) => setTicker(e.target.value.toUpperCase())}
    placeholder="AAPL"
  />
</div>
```

다음으로 교체:
```tsx
<div>
  <Label htmlFor="ticker">Ticker</Label>
  <TickerCombobox
    id="ticker"
    required
    value={ticker}
    onChange={setTicker}
    placeholder="AAPL or 애플"
  />
</div>
```

(`onChange` 안의 `.toUpperCase()`는 컴포넌트가 책임지므로 부모에서 제거)

- [ ] **Step 2: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/portfolio/holding-form.tsx
git commit -m "feat(web/holding-form): use TickerCombobox for korean ticker search"
```

- [ ] **Step 4: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과 출력. verdict 처리는 Task 1 Step 4와 동일.

---

## Task 7: ScheduleForm 칩 UX 리팩터

다중 티커 입력을 자유 텍스트 split에서 칩 기반으로 변경. 확정된 티커만 칩으로 추가.

**Files:**
- Modify: `web/components/schedules/schedule-form.tsx`

- [ ] **Step 1: 폼 상태 및 입력 UI 교체**

`web/components/schedules/schedule-form.tsx`를 다음으로 변경:

import 부분에 추가:
```tsx
import { TickerCombobox } from "@/components/ui/ticker-combobox";
```

`useState` 변경:
```tsx
// 기존
const [tickers, setTickers] = useState("");

// 변경
const [tickers, setTickers] = useState<string[]>([]);
const [tickerDraft, setTickerDraft] = useState("");
```

submit 핸들러 변경:
```tsx
// 기존
const submit = async (e: React.FormEvent) => {
  e.preventDefault();
  const tickerList = tickers
    .split(/[,\s]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
  for (const t of tickerList) {
    await m.mutateAsync({
      name: tickerList.length === 1 ? name : `${name} (${t})`,
      ticker: t,
      cron_expr: cron,
      timezone: tz,
      preset: { analysts, debate_rounds: rounds },
    });
  }
  router.push("/schedules");
};

// 변경
const submit = async (e: React.FormEvent) => {
  e.preventDefault();
  if (tickers.length === 0) return;
  for (const t of tickers) {
    await m.mutateAsync({
      name: tickers.length === 1 ? name : `${name} (${t})`,
      ticker: t,
      cron_expr: cron,
      timezone: tz,
      preset: { analysts, debate_rounds: rounds },
    });
  }
  router.push("/schedules");
};

const addTicker = (t: string) => {
  if (!t) return;
  setTickers((cur) => (cur.includes(t) ? cur : [...cur, t]));
  setTickerDraft("");
};

const removeTicker = (t: string) => {
  setTickers((cur) => cur.filter((x) => x !== t));
};
```

티커 입력 섹션(현재 65–73번째 줄 부근) 교체:
```tsx
{/* 기존 */}
<div>
  <Label htmlFor="tickers">Tickers (comma or space separated)</Label>
  <Input
    id="tickers"
    required
    value={tickers}
    onChange={(e) => setTickers(e.target.value)}
    placeholder="AAPL, NVDA, AMD"
  />
</div>

{/* 변경 */}
<div>
  <Label htmlFor="tickers">Tickers</Label>
  {tickers.length > 0 && (
    <div className="mb-2 flex flex-wrap gap-2">
      {tickers.map((t) => (
        <span
          key={t}
          className="inline-flex items-center gap-1 rounded-full bg-bg-2 px-3 py-1 text-xs font-bold"
        >
          {t}
          <button
            type="button"
            onClick={() => removeTicker(t)}
            aria-label={`Remove ${t}`}
            className="text-text-3 hover:text-text-1"
          >
            ×
          </button>
        </span>
      ))}
    </div>
  )}
  <TickerCombobox
    id="tickers"
    value={tickerDraft}
    onChange={(t) => {
      if (t) addTicker(t);
      else setTickerDraft("");
    }}
    placeholder="AAPL 또는 애플 (Enter로 추가)"
  />
  <p className="mt-1 text-xs text-text-3">
    Enter 또는 검색 결과 선택 시 칩으로 추가됩니다.
  </p>
</div>
```

submit 버튼 disable 조건 변경(`tickers.length === 0`도 추가):
```tsx
{/* 기존 */}
<Button type="submit" disabled={m.isPending}>

{/* 변경 */}
<Button type="submit" disabled={m.isPending || tickers.length === 0}>
```

- [ ] **Step 2: 타입 체크**

Run: `cd web && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/schedules/schedule-form.tsx
git commit -m "feat(web/schedule-form): chip-based multi-ticker input"
```

- [ ] **Step 4: Codex 리뷰**

Run:
```bash
node "/Users/kimjaehyun/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" review --wait
```
Expected: 리뷰 결과 출력. verdict 처리는 Task 1 Step 4와 동일. (다중 티커 칩 상태 관리/제출 흐름의 미묘한 버그를 특히 점검.)

---

## Task 8: 수동 브라우저 검증

자동 테스트로 커버할 수 없는 UX/통합 동작을 확인.

**Files:**
- 변경 없음(검증만)

- [ ] **Step 1: 의존성/빌드 확인**

```bash
cd web && npm run typecheck
cd web && npm run lint
node web/lib/ticker-search.test.cjs
```
Expected: 모두 PASS

- [ ] **Step 2: dev 서버 가동**

Run: `./dev.sh`
Expected: web 서버 기동, 콘솔에 백엔드/프론트 로그 표시

- [ ] **Step 3: RunForm(`/`) 검증**

브라우저에서 분석 실행 폼 열기. 다음 케이스 각각 확인:
- 한글 검색 `알파` → 드롭다운에 GOOGL/GOOG 표시
- `알파벳A` 정확 입력 후 blur → GOOGL로 자동 확정
- `애플` 정확 입력 후 Enter → AAPL로 확정 + 폼 제출 가능
- `구글` 입력 후 Enter → "목록에서 선택해주세요" 안내 + 제출 차단(목록에서 선택 시 정상)
- `존재하지않는한글` 입력 후 blur → "검색 결과가 없습니다" 안내 + 제출 차단
- `MSTR` 직접 입력(시드 미존재 영문) → 정상 확정/제출
- `MSTR!` → "올바른 영문 티커 형식이 아닙니다" 안내 + 제출 차단
- ↑↓ 키로 항목 이동, Enter로 선택, Esc로 닫기 동작

- [ ] **Step 4: HoldingForm 검증**

`/portfolio` 페이지에서 보유 추가:
- 한글 검색 → 선택 → Add 동작
- 시드 미존재 티커(`PLTR` 같은 시드 포함 + 시드 미존재 임의 티커) 직접 입력 후 Add

- [ ] **Step 5: ScheduleForm 검증**

`/schedules/new`:
- 한글로 여러 종목 추가(`애플` Enter, `테슬` 선택 후 Enter, `MSTR` 직접 입력 후 Enter)
- 칩이 위에 표시되고 ✕로 제거 가능
- `구글` Enter → 칩 추가되지 않고 안내 메시지(컴포넌트 invalid 상태)
- 칩 1개 이상일 때만 "Create schedule(s)" 활성화

- [ ] **Step 6: 모바일 뷰포트 확인**

Chrome DevTools에서 iPhone 14 Pro 등 모바일 프리셋으로:
- popover 위치/너비가 입력란과 정렬
- 가상 키보드 위에서 항목 클릭 가능
- 키보드 등장/퇴장 시 레이아웃 깨짐 없음

- [ ] **Step 7: 회귀 확인**

기존 분석 실행/보유/스케줄 흐름이 영문 티커로 그대로 동작하는지 확인:
- `AAPL` 직접 입력 → 분석 실행 정상
- 기존 보유 데이터/스케줄 조회/표시 정상
- run/[id] 페이지 SSE 등 무관 영역에 회귀 없음

- [ ] **Step 8: 검증 보고**

확인된 결과를 다음 형태로 정리해 보고:
```
PASS:
- RunForm 한글/영문/자유입력 가드: ✓
- HoldingForm 통합: ✓
- ScheduleForm 칩 UX: ✓
- 모바일 뷰포트: ✓
- 회귀 없음: ✓

(또는 발견된 이슈를 명시)
```

수정이 필요한 이슈가 있으면 별도 task로 추가하고 같은 PR 안에서 처리.

---

## Self-Review 결과

- **Spec 커버리지**: §2(시드)→Task 1, §3(검색)→Task 2, §4.4(가드)→Task 3, §4(컴포넌트)→Task 4, §5.1/5.2/5.3(폼 통합)→Task 5/6/7, §6(검증)→Task 2/3/8 모두 매핑됨.
- **Placeholder 스캔**: 모든 코드 블록에 실제 코드가 들어 있고, "TBD"/"적절한 처리"/"비슷하게" 같은 표현 없음.
- **타입 일관성**: `TickerEntry`(Task 1) → `searchTickers`/`commitInput`(Task 2/3) → `TickerCombobox`(Task 4) → 폼 통합(Task 5/6/7) 시그니처 일관.
- **확장 시드 작업**: Task 1은 30개 시드로 한정. S&P 500 등 대규모 확장은 별도 Codex 스크립트 작업으로 분리(이 플랜 범위 밖) — 후속 별도 작업으로 처리.
