const { test } = require("node:test");
const assert = require("node:assert/strict");
const { backendUrl } = require(`${process.env.ELARA_TEST_BUILD}/portal-api.js`);
test("API URL defaults to this origin's hostname and backend port", () => {
  delete process.env.NEXT_PUBLIC_ELARA_API_URL;
  delete process.env.NEXT_PUBLIC_ELARA_WS_URL;
  global.window = { location: { protocol: "http:", hostname: "127.0.0.1" } };
  assert.equal(backendUrl(), "http://127.0.0.1:8000");
});
test("explicit WebSocket and API overrides stay aligned", () => {
  process.env.NEXT_PUBLIC_ELARA_WS_URL = "wss://backend.example/ws";
  assert.equal(backendUrl(), "https://backend.example");
  process.env.NEXT_PUBLIC_ELARA_API_URL = "https://api.example/";
  assert.equal(backendUrl(), "https://api.example");
});
