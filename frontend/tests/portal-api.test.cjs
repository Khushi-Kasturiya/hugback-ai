const { test } = require("node:test");
const assert = require("node:assert/strict");
const { backendUrl } = require(`${process.env.HUGBACK_TEST_BUILD}/portal-api.js`);
test("API URL defaults to this origin's hostname and backend port", () => {
  delete process.env.NEXT_PUBLIC_HUGBACK_API_URL;
  delete process.env.NEXT_PUBLIC_HUGBACK_WS_URL;
  global.window = { location: { protocol: "http:", hostname: "127.0.0.1" } };
  assert.equal(backendUrl(), "http://127.0.0.1:8000");
});
test("explicit WebSocket and API overrides stay aligned", () => {
  process.env.NEXT_PUBLIC_HUGBACK_WS_URL = "wss://backend.example/ws";
  assert.equal(backendUrl(), "https://backend.example");
  process.env.NEXT_PUBLIC_HUGBACK_API_URL = "https://api.example/";
  assert.equal(backendUrl(), "https://api.example");
});

test("403 diagnostics distinguish UID denial, loopback-only deployment and unknown failures", async () => {
  const identity = require(`${process.env.HUGBACK_TEST_BUILD}/identity.js`);
  const { portalGet } = require(`${process.env.HUGBACK_TEST_BUILD}/portal-api.js`);
  const savedHeaders = identity.getAuthenticationHeaders;
  const savedFetch = global.fetch;
  identity.getAuthenticationHeaders = async () => ({});
  try {
    for (const [hostname, detail, expected, forbidden] of [
      ["127.0.0.1", "This identity is not an authorized synthetic test operator.", /Backend allowlist UID/, /provider-secret/],
      ["hugback.cloud.run", "This identity is not an authorized synthetic test operator.", /deployed backend/, /copy the Backend allowlist UID/],
      ["hugback.cloud.run", "Demo mode is localhost-only.", /Adding a UID or changing CORS will not/, /copy the Backend allowlist UID/],
      ["127.0.0.1", "Local demo mode is disabled.", /test-mode configuration/, /not authorized for the Firestore test/],
      ["127.0.0.1", "provider-secret", /backend denied portal access/, /provider-secret/],
    ]) {
      global.window = { location: { hostname } };
      global.fetch = async () => ({ ok: false, status: 403, json: async () => ({ detail }) });
      await assert.rejects(portalGet("/status"), (error) => {
        assert.match(error.message, expected);
        assert.doesNotMatch(error.message, forbidden);
        return true;
      });
    }
    global.fetch = async () => ({ ok: false, status: 403, json: async () => { throw new Error("not JSON"); } });
    await assert.rejects(portalGet("/status"), /backend denied portal access/);
  } finally {
    identity.getAuthenticationHeaders = savedHeaders;
    global.fetch = savedFetch;
  }
});
