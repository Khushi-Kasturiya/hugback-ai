const { test, beforeEach } = require("node:test");
const assert = require("node:assert/strict");
const { webcrypto } = require("node:crypto");
const file = `${process.env.HUGBACK_TEST_BUILD}/identity.js`;
let storage;
beforeEach(() => {
  delete require.cache[require.resolve(file)];
  delete process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  storage = new Map();
  global.window = { location: { hostname: "127.0.0.1" }, localStorage: {
    getItem: (k) => storage.get(k) ?? null,
    setItem: (k, v) => storage.set(k, v),
    removeItem: (k) => storage.delete(k),
  }};
  global.crypto = webcrypto;
  global.fetch = () => { throw new Error("No network allowed in tests"); };
});
test("reuses existing local identity for calls and portal without a sign-in", async () => {
  const api = require(file);
  const auth = await api.getAuthenticationMessage();
  assert.equal((await api.getAuthenticationMessage()).userId, auth.userId);
  assert.equal((await api.getBrowserIdentity()).owner, `development:${auth.userId}`);
  assert.equal((await api.getAuthenticationHeaders())["X-Hugback-Development-User"], auth.userId);
});
test("no development fallback on public hosts", async () => {
  window.location.hostname = "hugback.example";
  await assert.rejects(require(file).getAuthenticationMessage(), /must be configured/);
});
test("simultaneous anonymous sign-ups share one request and owner", async () => {
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY = "synthetic-key";
  let count = 0;
  global.fetch = async () => {
    count++;
    await new Promise((r) => setTimeout(r, 1));
    return { ok: true, json: async () => ({ idToken: "synthetic-token", refreshToken: "refresh", localId: "child-1", expiresIn: "3600" }) };
  };
  const api = require(file);
  await Promise.all([api.getAuthenticationMessage(), api.getAuthenticationMessage()]);
  assert.equal(count, 1);
  assert.equal((await api.getBrowserIdentity()).owner, "firebase:child-1");
  assert.equal((await api.getAuthenticationHeaders()).Authorization, "Bearer synthetic-token");
});
test("refresh failure never replaces a family identity or falls back to UUID", async () => {
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY = "synthetic-key";
  const record = JSON.stringify({ localId: "child-1", idToken: "expired", refreshToken: "refresh", expiresAt: 1 });
  storage.set("hugback.firebase.identity.v1", record);
  global.fetch = async () => ({ ok: false });
  await assert.rejects(require(file).getAuthenticationMessage(), /saved identity has been kept/);
  assert.equal(storage.get("hugback.firebase.identity.v1"), record);
  assert.equal(storage.has("hugback.development.user.v1"), false);
});
test("malformed saved credentials do not silently create a new identity", async () => {
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY = "synthetic-key";
  storage.set("hugback.firebase.identity.v1", "{}");
  await assert.rejects(require(file).getAuthenticationMessage(), /could not be read/);
});
test("successful refresh preserves the UID and stores new expiry", async () => {
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY = "synthetic-key";
  storage.set("hugback.firebase.identity.v1", JSON.stringify({
    localId: "child-1", idToken: "expired", refreshToken: "refresh", expiresAt: 1,
  }));
  global.fetch = async () => ({ ok: true, json: async () => ({
    user_id: "child-1", id_token: "renewed", refresh_token: "new-refresh", expires_in: "3600",
  }) });
  assert.equal((await require(file).getAuthenticationMessage()).idToken, "renewed");
  assert.equal(JSON.parse(storage.get("hugback.firebase.identity.v1")).localId, "child-1");
});
test("refresh refuses an unexpected owner change", async () => {
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY = "synthetic-key";
  storage.set("hugback.firebase.identity.v1", JSON.stringify({
    localId: "child-1", idToken: "expired", refreshToken: "refresh", expiresAt: 1,
  }));
  global.fetch = async () => ({ ok: true, json: async () => ({
    user_id: "child-2", id_token: "renewed", refresh_token: "new-refresh", expires_in: "3600",
  }) });
  await assert.rejects(require(file).getAuthenticationMessage(), /did not preserve/);
  assert.equal(JSON.parse(storage.get("hugback.firebase.identity.v1")).localId, "child-1");
});
