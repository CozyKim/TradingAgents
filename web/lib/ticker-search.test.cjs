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

test("commitInput: english alias auto-resolves to ticker (regression for Codex P2)", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  const SEED_WITH_ENG_ALIAS = [
    { ticker: "MSFT", name: "Microsoft Corporation", aliases: ["마이크로소프트", "MS"] },
    { ticker: "TSM", name: "Taiwan Semiconductor Manufacturing", aliases: ["TSMC", "대만반도체"] },
    { ticker: "BAC", name: "Bank of America Corporation", aliases: ["뱅크오브아메리카", "BoA"] },
  ];
  assert.deepEqual(commitInput("MS", { seed: SEED_WITH_ENG_ALIAS }), { status: "ok", ticker: "MSFT" });
  assert.deepEqual(commitInput("ms", { seed: SEED_WITH_ENG_ALIAS }), { status: "ok", ticker: "MSFT" });
  assert.deepEqual(commitInput("TSMC", { seed: SEED_WITH_ENG_ALIAS }), { status: "ok", ticker: "TSM" });
  assert.deepEqual(commitInput("BoA", { seed: SEED_WITH_ENG_ALIAS }), { status: "ok", ticker: "BAC" });
});

test("commitInput: special-char alias auto-resolves to ticker (regression for Codex P2)", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  const SEED_WITH_SPECIAL = [
    { ticker: "SPY", name: "SPDR S&P 500 ETF Trust", aliases: ["S&P500", "스파이"] },
  ];
  assert.deepEqual(commitInput("S&P500", { seed: SEED_WITH_SPECIAL }), { status: "ok", ticker: "SPY" });
});

test("commitInput: ticker-as-input still resolves to itself", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // 시드에 있는 정식 티커는 ticker-exact match로 ok 처리
  assert.deepEqual(commitInput("AAPL", { seed: SEED }), { status: "ok", ticker: "AAPL" });
});

test("commitInput: ambiguous alias across multiple tickers requires selection", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // SEED has GOOGL/GOOG both with alias "구글" → ambiguous
  const result = commitInput("구글", { seed: SEED });
  assert.equal(result.status, "needs_selection");
});

test("commitInput: english company name partial match forces selection (regression for Codex P2)", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // "tesla" matches TSLA via name substring → must not auto-confirm "TESLA"
  const r1 = commitInput("tesla", { seed: SEED });
  assert.equal(r1.status, "needs_selection");
  // "apple" matches AAPL via name prefix → must not auto-confirm "APPLE"
  const r2 = commitInput("apple", { seed: SEED });
  assert.equal(r2.status, "needs_selection");
});

test("commitInput: english ticker prefix preserves free-form input (regression for Codex P2)", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // "MS" is a prefix of MSFT in seed but is also Morgan Stanley's real ticker.
  // Ticker-prefix-only matches must not block free-form commit.
  const SEED_WITH_PREFIX = [
    { ticker: "MSFT", name: "Microsoft Corporation", aliases: ["마이크로소프트"] },
  ];
  assert.deepEqual(commitInput("MS", { seed: SEED_WITH_PREFIX }), { status: "ok", ticker: "MS" });
  // "tsl" is a prefix of TSLA but should still commit as TSL since match is ticker-prefix only
  assert.deepEqual(commitInput("tsl", { seed: SEED }), { status: "ok", ticker: "TSL" });
});

test("commitInput: free-form english ticker passes only when seed has no match at all", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // SOFI: not in seed and no name/alias contains "sofi" → pattern fallback ok
  assert.deepEqual(commitInput("SOFI", { seed: SEED }), { status: "ok", ticker: "SOFI" });
  // MSTR: not in this test seed, also no substring match → pattern fallback ok
  assert.deepEqual(commitInput("MSTR", { seed: SEED }), { status: "ok", ticker: "MSTR" });
});

test("commitInput: ignores caller-provided limit when checking matches (regression for Codex P2)", () => {
  const { commitInput } = loadTsModule("ticker-search.ts");
  // With a wide seed, low-score name matches could be cut off by limit.
  // commitInput must scan the full seed regardless of limit option.
  const WIDE_SEED = [
    { ticker: "AA", name: "Alcoa Corporation", aliases: [] },
    { ticker: "AAL", name: "American Airlines", aliases: [] },
    { ticker: "AAP", name: "Advance Auto Parts", aliases: [] },
    { ticker: "AAPL", name: "Apple Inc.", aliases: ["애플"] },
    { ticker: "AAU", name: "Almaden Minerals", aliases: [] },
    { ticker: "GOOGL", name: "Alphabet Inc.", aliases: ["알파벳"] }, // substring "a" via name
  ];
  // Even when limit=2 would cut off Alphabet (substring score 300),
  // commit must still see the name match and force selection.
  const result = commitInput("a", { seed: WIDE_SEED, limit: 2 });
  assert.equal(result.status, "needs_selection");
});
