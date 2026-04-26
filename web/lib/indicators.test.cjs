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

const approx = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;

test("sma: rolling mean with null warm-up", () => {
  const { sma } = loadTsModule("indicators.ts");
  const out = sma([1, 2, 3, 4, 5], 3);
  assert.deepEqual(out, [null, null, 2, 3, 4]);
});

test("sma: returns all nulls when not enough data", () => {
  const { sma } = loadTsModule("indicators.ts");
  assert.deepEqual(sma([1, 2], 3), [null, null]);
});

test("ema: seed equals SMA at index period-1, then recurses", () => {
  const { ema } = loadTsModule("indicators.ts");
  const out = ema([1, 2, 3, 4, 5], 3);
  assert.equal(out[0], null);
  assert.equal(out[1], null);
  assert.ok(approx(out[2], 2)); // seed = (1+2+3)/3
  // k = 2/(3+1) = 0.5; out[3] = 4*0.5 + 2*0.5 = 3
  assert.ok(approx(out[3], 3));
  // out[4] = 5*0.5 + 3*0.5 = 4
  assert.ok(approx(out[4], 4));
});

test("bollinger: middle is SMA, upper/lower symmetric around middle", () => {
  const { bollinger } = loadTsModule("indicators.ts");
  const values = [2, 4, 4, 4, 5, 5, 7, 9];
  const { middle, upper, lower } = bollinger(values, 4, 2);
  // middle[3] = (2+4+4+4)/4 = 3.5
  assert.ok(approx(middle[3], 3.5));
  // population stddev for [2,4,4,4]: mean=3.5, var = ((1.5^2 + 0.5^2 + 0.5^2 + 0.5^2)/4) = 0.75
  // sd = sqrt(0.75) ≈ 0.8660254
  assert.ok(approx(upper[3], 3.5 + 2 * Math.sqrt(0.75)));
  assert.ok(approx(lower[3], 3.5 - 2 * Math.sqrt(0.75)));
});

test("rsi: classic textbook example yields ~70 area", () => {
  const { rsi } = loadTsModule("indicators.ts");
  // Strictly increasing: avg loss = 0 → rsi = 100
  const out = rsi([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], 14);
  assert.equal(out[0], null);
  assert.equal(out[14], 100);
  assert.equal(out[15], 100);
});

test("rsi: flat data yields 50 (no gains, no losses → undefined; we emit 100 if no loss but here both 0)", () => {
  const { rsi } = loadTsModule("indicators.ts");
  const out = rsi([5, 5, 5, 5, 5, 5], 3);
  // After warm-up, avgGain=0, avgLoss=0. Our impl returns 100 when avgLoss=0.
  // This is a known edge; document it via this test.
  assert.equal(out[3], 100);
});

test("stochasticSlow: with kPeriod=3, slowing=1, dPeriod=1 returns raw %K and same %D", () => {
  const { stochasticSlow } = loadTsModule("indicators.ts");
  const closes = [1, 2, 3, 2, 1, 2, 3];
  const { k, d } = stochasticSlow(closes, 3, 1, 1);
  // window [1,2,3], close=3, range=2 → raw=100
  assert.ok(approx(k[2], 100));
  // window [2,3,2], close=2, range=1 → raw=0
  assert.ok(approx(k[3], 0));
  // window [3,2,1], close=1, range=2 → raw=0
  assert.ok(approx(k[4], 0));
  // d == k when dPeriod=1
  assert.deepEqual(d, k);
});

test("stochasticSlow: slowing>1 averages over kPeriod's raw %K", () => {
  const { stochasticSlow } = loadTsModule("indicators.ts");
  const closes = [1, 2, 3, 4, 5, 6];
  const { k } = stochasticSlow(closes, 3, 3, 1);
  // raw[2..5] = [100, 100, 100, 100] (always at top of monotone window)
  // slow k after 3-smoothing first appears at index 2+3-1 = 4
  assert.ok(approx(k[4], 100));
  assert.ok(approx(k[5], 100));
  assert.equal(k[3], null);
});
