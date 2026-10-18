// Configuration-only checks. No Firebase enrollment, network, audio or paid I/O.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

function readEnv(path) {
  return Object.fromEntries(fs.readFileSync(path, "utf8").split(/\r?\n/)
    .filter((line) => line.trim() && !line.trim().startsWith("#"))
    .map((line) => {
      const separator = line.indexOf("=");
      assert.ok(separator > 0, "Expected a plain dotenv assignment");
      return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
    }));
}

test("hosted demo selects recipient-scoped Firestore call UI", () => {
  const env = readEnv(".env.production");
  assert.equal(env.NEXT_PUBLIC_HUGBACK_DEMO_MODE, "true");
  assert.ok(env.NEXT_PUBLIC_FIREBASE_API_KEY);
  const api = new URL(env.NEXT_PUBLIC_HUGBACK_API_URL);
  const ws = new URL(env.NEXT_PUBLIC_HUGBACK_WS_URL);
  assert.equal(api.protocol, "https:");
  assert.equal(ws.protocol, "wss:");
  assert.equal(api.host, ws.host);
  assert.equal(ws.pathname, "/ws");
  for (const url of [api, ws]) {
    assert.equal(url.username + url.password + url.search + url.hash, "");
  }
  const publicKeys = new Set([
    "NEXT_PUBLIC_FIREBASE_API_KEY", "NEXT_PUBLIC_FIREBASE_PROJECT_ID",
    "NEXT_PUBLIC_HUGBACK_API_URL", "NEXT_PUBLIC_HUGBACK_WS_URL",
    "NEXT_PUBLIC_HUGBACK_DEMO_MODE",
  ]);
  for (const name of Object.keys(env)) {
    assert.ok(publicKeys.has(name), "Backend secrets must not enter the frontend environment");
  }
});

test("Docker excludes local overrides but includes public production build config", () => {
  const ignore = fs.readFileSync(".dockerignore", "utf8").split(/\r?\n/);
  assert.ok(ignore.includes(".env*.local"));
  assert.ok(!ignore.includes(".env.production"));
  const dockerfile = fs.readFileSync("Dockerfile", "utf8");
  assert.ok(dockerfile.indexOf("COPY . .") < dockerfile.indexOf("RUN npm run build"));
});
