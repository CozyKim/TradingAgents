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

test("returns same-origin relative path by default", () => {
  const { resolveRunStreamUrl } = loadTsModule("sse-url.ts");

  assert.equal(
    resolveRunStreamUrl("run 1"),
    "/api/runs/run%201/stream",
  );
});

test("prefers explicit browser API URL when provided", () => {
  const { resolveRunStreamUrl } = loadTsModule("sse-url.ts");

  assert.equal(
    resolveRunStreamUrl("abc", {
      browserApiBaseUrl: "https://example.com/backend/",
    }),
    "https://example.com/backend/api/runs/abc/stream",
  );
});
