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

test("resolves local stream URLs directly to the API server", () => {
  const { resolveRunStreamUrl } = loadTsModule("sse-url.ts");

  assert.equal(
    resolveRunStreamUrl("run 1", {
      apiBaseUrl: "",
      browserApiBaseUrl: "",
      location: { protocol: "http:", hostname: "localhost" },
    }),
    "http://localhost:8000/api/runs/run%201/stream",
  );
});

test("rewrites docker-internal API host to a browser-reachable host", () => {
  const { resolveRunStreamUrl } = loadTsModule("sse-url.ts");

  assert.equal(
    resolveRunStreamUrl("abc", {
      apiBaseUrl: "http://api:8000",
      browserApiBaseUrl: "",
      location: { protocol: "http:", hostname: "localhost" },
    }),
    "http://localhost:8000/api/runs/abc/stream",
  );
});

test("prefers explicit browser API URL", () => {
  const { resolveRunStreamUrl } = loadTsModule("sse-url.ts");

  assert.equal(
    resolveRunStreamUrl("abc", {
      apiBaseUrl: "http://api:8000",
      browserApiBaseUrl: "https://example.com/backend/",
      location: { protocol: "https:", hostname: "example.com" },
    }),
    "https://example.com/backend/api/runs/abc/stream",
  );
});
