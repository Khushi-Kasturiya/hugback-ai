const { test, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const { selectedVoicePayload, audioBase64, voiceRequest } = require(join(process.env.HUGBACK_TEST_BUILD, "voice-api.js"));
const profile = { id: "synthetic-profile", expiresAt: "2099-01-01T00:00:00Z", enabled: true, expired: false };
const voice = { mode: "preset", name: "Aoede", replicatedTtsEnabled: true, profile };
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; delete global.window; });

test("call sends only owner-scoped profile ID, never provider key or recordings", () => {
  assert.deepEqual(selectedVoicePayload(voice), { voiceProfileId: profile.id });
  assert.deepEqual(selectedVoicePayload({ ...voice, profile: { ...profile, enabled: false } }), {});
  assert.deepEqual(selectedVoicePayload({ ...voice, profile: null }), {});
});
test("custom selection fails closed on expired, invalid-date or disabled backend", () => {
  for (const changed of [
    { ...voice, replicatedTtsEnabled: false },
    { ...voice, mode: "experimental-inline" },
    { ...voice, profile: { ...profile, expired: true } },
    { ...voice, profile: { ...profile, expiresAt: "invalid" } },
    { ...voice, profile: { ...profile, expiresAt: "2020-01-01T00:00:00Z" } },
  ]) assert.throws(() => selectedVoicePayload(changed), /Voice setup|voice setup/i);
});
test("audio encoding preserves synthetic bytes", async () => {
  const bytes = new Uint8Array(20_000).fill(127);
  assert.equal(await audioBase64(new Blob([bytes])), Buffer.from(bytes).toString("base64"));
});
test("upload uses existing identity and JSON acknowledgements with no automatic retries", async () => {
  global.window = { location: { hostname: "127.0.0.1", protocol: "http:" },
    localStorage: { getItem: () => "synthetic-owner" } };
  let attempts = 0;
  global.fetch = async (url, options) => {
    attempts++;
    assert.equal(url, "http://127.0.0.1:8000/api/voice/enroll");
    assert.equal(options.headers["X-Hugback-Development-User"], "synthetic-owner");
    assert.equal(options.cache, "no-store");
    assert.equal(JSON.parse(options.body).adultOwnVoice, true);
    throw new TypeError("network unavailable");
  };
  await assert.rejects(voiceRequest("/enroll", "POST", { adultOwnVoice: true }), /Refresh status/);
  assert.equal(attempts, 1);
});
test("profile removal is explicit and provider errors stay readable", async () => {
  global.window = { location: { hostname: "127.0.0.1", protocol: "http:" },
    localStorage: { getItem: () => "synthetic-owner" } };
  global.fetch = async (url, options) => {
    assert.equal(options.method, "DELETE");
    assert.equal(options.body, undefined);
    return { ok: false, json: async () => ({ detail: "Wait for voice setup to finish." }) };
  };
  await assert.rejects(voiceRequest("/profile", "DELETE"), /Wait for voice setup/);
});
