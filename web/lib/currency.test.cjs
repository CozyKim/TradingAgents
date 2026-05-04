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

test("formatPrice: USD positive default", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(123.45, { currency: "USD", fxRate: null }), "$123.45");
});

test("formatPrice: USD negative places sign before symbol", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(-12.34, { currency: "USD", fxRate: null }), "-$12.34");
});

test("formatPrice: USD signed=true on positive", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(12.34, { currency: "USD", fxRate: null }, { signed: true }),
    "+$12.34",
  );
});

test("formatPrice: KRW with fxRate rounds and adds comma", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  // 123.45 * 1380 = 170361 exactly
  assert.equal(
    formatPrice(123.45, { currency: "KRW", fxRate: 1380 }),
    "₩170,361",
  );
});

test("formatPrice: KRW negative places sign before symbol", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(-100, { currency: "KRW", fxRate: 1380 }),
    "-₩138,000",
  );
});

test("formatPrice: null returns em-dash", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(null, { currency: "USD", fxRate: null }), "—");
  assert.equal(formatPrice(undefined, { currency: "KRW", fxRate: 1380 }), "—");
});

test("formatPrice: usdDecimals option", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(123.45, { currency: "USD", fxRate: null }, { usdDecimals: 0 }),
    "$123",
  );
});

test("formatPrice: KRW with null fxRate falls back to USD", () => {
  // The Provider routes effectiveCurrency to "USD" when fxRate is null,
  // but formatPrice should also be defensive: if currency is "KRW" but
  // fxRate is null, render USD format.
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(50, { currency: "KRW", fxRate: null }), "$50.00");
});
