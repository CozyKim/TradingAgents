const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const Module = require("node:module");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

// Mirror of currency.test.cjs's on-demand .ts/.tsx loader so `@/...` imports
// (transitively `./currency`) are transpiled and path-rewritten.
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

function load() {
  return loadTsModule("portfolio-totals.ts").computePortfolioTotals;
}

test("computePortfolioTotals: empty portfolio has zero cost and no value", () => {
  const compute = load();
  const t = compute([], {}, null);
  assert.equal(t.cost, 0);
  assert.equal(t.value, null);
  assert.equal(t.pnl, null);
  assert.equal(t.positions, 0);
});

test("computePortfolioTotals: all-USD fully priced sums in USD", () => {
  const compute = load();
  const t = compute(
    [{ ticker: "AAPL", qty: 2, avg_cost: 100 }],
    { AAPL: 150 },
    null,
  );
  assert.equal(t.cost, 200);
  assert.equal(t.value, 300);
  assert.equal(t.pnl, 100);
  assert.equal(t.pnlPct, 50);
  assert.equal(t.positions, 1);
});

test("computePortfolioTotals: KRW holding is normalized to USD with fxRate", () => {
  const compute = load();
  // 10 * 69000 = 690000 KRW; /1380 = 500 USD
  const t = compute(
    [{ ticker: "005930.KS", qty: 10, avg_cost: 69000 }],
    { "005930.KS": 69000 },
    1380,
  );
  assert.equal(t.cost, 500);
  assert.equal(t.value, 500);
  assert.equal(t.pnl, 0);
  assert.equal(t.positions, 1);
});

test("computePortfolioTotals: KRW holding without fxRate cannot normalize", () => {
  const compute = load();
  const t = compute(
    [{ ticker: "005930.KS", qty: 10, avg_cost: 69000 }],
    { "005930.KS": 69000 },
    null,
  );
  assert.equal(t.cost, null);
  assert.equal(t.value, null);
  assert.equal(t.pnl, null);
});

test("computePortfolioTotals: mixed currencies sum after normalization", () => {
  const compute = load();
  // AAPL: cost 100, value 120 USD. 005930.KS: cost 1380KRW->1USD, value 2760KRW->2USD
  const t = compute(
    [
      { ticker: "AAPL", qty: 1, avg_cost: 100 },
      { ticker: "005930.KS", qty: 1, avg_cost: 1380 },
    ],
    { AAPL: 120, "005930.KS": 2760 },
    1380,
  );
  assert.equal(t.cost, 101);
  assert.equal(t.value, 122);
  assert.equal(t.pnl, 21);
  assert.equal(t.positions, 2);
});

test("computePortfolioTotals: not fully priced yields null value but keeps cost", () => {
  const compute = load();
  const t = compute(
    [
      { ticker: "AAPL", qty: 1, avg_cost: 100 },
      { ticker: "MSFT", qty: 1, avg_cost: 200 },
    ],
    { AAPL: 120, MSFT: null },
    null,
  );
  assert.equal(t.cost, 300);
  assert.equal(t.value, null);
  assert.equal(t.pnl, null);
  assert.equal(t.positions, 2);
});
