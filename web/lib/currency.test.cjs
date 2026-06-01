const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const Module = require("node:module");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

// Register a require hook for .ts/.tsx so transitively imported source files
// (e.g. `@/hooks/use-fx-rate`) are transpiled on demand. Also rewrite
// `@/...` requires to relative paths because tsconfig path mapping is not
// honored by the standalone transpiler.
const WEB_ROOT = path.resolve(__dirname, "..");

function compileTs(filename) {
  const source = readFileSync(filename, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
    },
    fileName: filename,
  });
  return outputText.replace(
    /require\(["']@\/([^"']+)["']\)/g,
    (_m, sub) => {
      const target = path.join(WEB_ROOT, sub);
      const rel = path.relative(path.dirname(filename), target);
      const norm = rel.startsWith(".") ? rel : `./${rel}`;
      return `require(${JSON.stringify(norm)})`;
    },
  );
}

function tsLoader(mod, filename) {
  mod._compile(compileTs(filename), filename);
}

if (!require.extensions[".ts"]) require.extensions[".ts"] = tsLoader;
if (!require.extensions[".tsx"]) require.extensions[".tsx"] = tsLoader;

function loadTsModule(relativePath) {
  const filename = path.join(__dirname, relativePath);
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(__dirname);
  mod._compile(compileTs(filename), filename);
  return mod.exports;
}

// ---------------------------------------------------------------------------
// formatPrice(value, sourceCurrency, ctx, opts)
//
// `sourceCurrency` is the native currency of `value` (the exchange's quote
// currency). The display currency is `ctx.currency`. formatPrice converts
// source -> display when they differ and an fxRate is available; otherwise it
// falls back to rendering in the source currency.
// ---------------------------------------------------------------------------

test("formatPrice: USD source, USD display, positive default", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(123.45, "USD", { currency: "USD", fxRate: null }),
    "$123.45",
  );
});

test("formatPrice: USD negative places sign before symbol", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(-12.34, "USD", { currency: "USD", fxRate: null }),
    "-$12.34",
  );
});

test("formatPrice: USD signed=true on positive", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(12.34, "USD", { currency: "USD", fxRate: null }, { signed: true }),
    "+$12.34",
  );
});

test("formatPrice: USD source converted to KRW display rounds and adds comma", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  // 123.45 * 1380 = 170361 exactly
  assert.equal(
    formatPrice(123.45, "USD", { currency: "KRW", fxRate: 1380 }),
    "₩170,361",
  );
});

test("formatPrice: USD->KRW negative places sign before symbol", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(-100, "USD", { currency: "KRW", fxRate: 1380 }),
    "-₩138,000",
  );
});

test("formatPrice: null returns em-dash", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(null, "USD", { currency: "USD", fxRate: null }), "—");
  assert.equal(
    formatPrice(undefined, "USD", { currency: "KRW", fxRate: 1380 }),
    "—",
  );
});

test("formatPrice: usdDecimals option", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(123.45, "USD", { currency: "USD", fxRate: null }, { usdDecimals: 0 }),
    "$123",
  );
});

test("formatPrice: USD source, KRW display but null fxRate falls back to USD", () => {
  // Provider routes effectiveCurrency to "USD" when fxRate is null, but
  // formatPrice is also defensive: with no rate it renders the source currency.
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(50, "USD", { currency: "KRW", fxRate: null }), "$50.00");
});

// --- KRW-native value (the Korean-ticker bug) ------------------------------

test("formatPrice: KRW source on KRW display is NOT multiplied by fxRate", () => {
  // 005930.KS quotes ₩75,000 natively. Displaying in KRW must show the raw
  // value, NOT 75000 * fxRate (the original bug).
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(75000, "KRW", { currency: "KRW", fxRate: 1380 }),
    "₩75,000",
  );
});

test("formatPrice: KRW source on KRW display works without an fxRate", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(75000, "KRW", { currency: "KRW", fxRate: null }),
    "₩75,000",
  );
});

test("formatPrice: KRW source converted to USD display divides by fxRate", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  // 69000 / 1380 = 50 exactly
  assert.equal(
    formatPrice(69000, "KRW", { currency: "USD", fxRate: 1380 }),
    "$50.00",
  );
});

test("formatPrice: KRW source, USD display, null fxRate falls back to KRW", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(75000, "KRW", { currency: "USD", fxRate: null }),
    "₩75,000",
  );
});

test("formatPrice: KRW source rounds won to whole number with comma", () => {
  // Won is always whole-number; usdDecimals only affects dollar rendering.
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(1234.6, "KRW", { currency: "KRW", fxRate: null }),
    "₩1,235",
  );
});

// --- currencyForTicker ------------------------------------------------------

test("currencyForTicker: KOSPI .KS suffix is KRW", () => {
  const { currencyForTicker } = loadTsModule("currency.tsx");
  assert.equal(currencyForTicker("005930.KS"), "KRW");
});

test("currencyForTicker: KOSDAQ .KQ suffix is KRW", () => {
  const { currencyForTicker } = loadTsModule("currency.tsx");
  assert.equal(currencyForTicker("035720.KQ"), "KRW");
});

test("currencyForTicker: lowercase suffix is normalized", () => {
  const { currencyForTicker } = loadTsModule("currency.tsx");
  assert.equal(currencyForTicker("005930.ks"), "KRW");
});

test("currencyForTicker: plain US ticker is USD", () => {
  const { currencyForTicker } = loadTsModule("currency.tsx");
  assert.equal(currencyForTicker("AAPL"), "USD");
  assert.equal(currencyForTicker("brk.b"), "USD");
});

// --- toUsd (normalization for cross-currency summation) ---------------------

test("toUsd: USD passes through unchanged even without a rate", () => {
  const { toUsd } = loadTsModule("currency.tsx");
  assert.equal(toUsd(100, "USD", null), 100);
});

test("toUsd: KRW divides by the rate", () => {
  const { toUsd } = loadTsModule("currency.tsx");
  assert.equal(toUsd(69000, "KRW", 1380), 50);
});

test("toUsd: KRW without a rate cannot normalize and returns null", () => {
  const { toUsd } = loadTsModule("currency.tsx");
  assert.equal(toUsd(69000, "KRW", null), null);
});

test("toUsd: null/undefined value returns null", () => {
  const { toUsd } = loadTsModule("currency.tsx");
  assert.equal(toUsd(null, "USD", 1380), null);
  assert.equal(toUsd(undefined, "KRW", 1380), null);
});
