// Focused hook preflight tests; no DOM, microphone, WebSocket or Google access.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const compiled = ts.transpileModule(fs.readFileSync("src/hooks/useLiveAudio.ts", "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

const family = { schemaVersion: 2, recipients: [
  { recipientId: "mother", label: "Mother", revision: 3, busy: false, voice: { mode: "standard", profileId: null } },
  { recipientId: "father", label: "Father", revision: 1, busy: false, voice: { mode: "child", profileId: "synthetic-profile" } },
] };
function hook(portalGet, profile = null, options = {}, loadFamily = async () => family) {
  const calls = { voice: 0, audio: 0 };
  const modules = {
    react: {
      useState: (initial) => [initial, () => {}],
      useRef: (current) => ({ current }),
      useCallback: (callback) => callback,
      useEffect: () => {},
    },
    "@/lib/identity": { getAuthenticationMessage: async () => ({ type: "authenticate", userId: "synthetic-test" }) },
    "@/lib/portal-api": { portalGet },
    "@/lib/demo-api": { ...require(require("node:path").join(process.env.HUGBACK_TEST_BUILD, "demo-api.js")), demoRequest: loadFamily },
    "@/lib/voice-api": require(require("node:path").join(process.env.HUGBACK_TEST_BUILD, "voice-api.js")),
    "@/lib/voice-profile": { getInlineVoicePayload: async () => { calls.voice++; return profile; } },
    "@/lib/audio-player": { startAudioPlayer: async () => { calls.audio++; throw new Error("Stop before any real audio or socket"); } },
    "@/lib/audio-recorder": { startAudioRecorder: () => { throw new Error("No microphone allowed"); } },
  };
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, require: (name) => { if (!modules[name]) throw new Error(`Unexpected module ${name}`); return modules[name]; },
    process: { env: {} }, window: { location: { protocol: "http:", hostname: "127.0.0.1" } },
    console: { log() {}, warn() {}, error() {} }, setTimeout, clearTimeout,
  });
  return { api: exports.useLiveAudio(options), calls };
}
test("preset calls never load locally stored voice recordings", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "preset" } }), { voiceSampleAudio: "synthetic" });
  await api.startCall();
  assert.equal(calls.voice, 0);
  assert.equal(calls.audio, 1);
});
test("demo call fails before audio when local mode is disabled", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "preset" }, localDemoEnabled: false }), null, { demoParent: true, recipientId: "mother" });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
test("demo call never loads experimental recordings", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "experimental-inline" }, localDemoEnabled: true }), { voiceSampleAudio: "synthetic" }, { demoParent: true, recipientId: "mother" });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
test("enabled preset demo call reaches audio preparation", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "preset" }, localDemoEnabled: true }), null, { demoParent: true, recipientId: "mother" });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 1 });
});
test("experimental calls without both recordings fail before audio setup", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "experimental-inline" } }));
  await api.startCall();
  assert.equal(calls.voice, 1);
  assert.equal(calls.audio, 0);
});
test("ending during capability lookup prevents later audio or voice preparation", async () => {
  let resolveStatus;
  const { api, calls } = hook(() => new Promise((resolve) => { resolveStatus = resolve; }));
  const pending = api.startCall();
  api.endCall();
  resolveStatus({ voice: { mode: "experimental-inline" } });
  await pending;
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
test("a cancelled attempt cannot restart when a newer attempt exists", async () => {
  const resolvers = [];
  const { api, calls } = hook(() => new Promise((resolve) => { resolvers.push(resolve); }));
  const first = api.startCall();
  api.endCall();
  const second = api.startCall();
  resolvers[0]({ voice: { mode: "experimental-inline" } });
  await first;
  assert.deepEqual(calls, { voice: 0, audio: 0 });
  api.endCall();
  resolvers[1]({ voice: { mode: "preset" } });
  await second;
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
test("enabled custom voice works in parent demo without loading browser recordings", async () => {
  const { api, calls } = hook(async () => ({
    localDemoEnabled: true, voice: { mode: "preset", replicatedTtsEnabled: true, profile: {
      id: "synthetic-profile", enabled: true, expiresAt: "2099-01-01T00:00:00Z", expired: false,
    } },
  }), null, { demoParent: true, recipientId: "father" });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 1 });
});
test("selected expired voice stops before audio instead of preset fallback", async () => {
  const { api, calls } = hook(async () => ({
    localDemoEnabled: true, voice: { mode: "preset", replicatedTtsEnabled: true, profile: {
      id: "synthetic-profile", enabled: true, expiresAt: "2020-01-01T00:00:00Z", expired: true,
    } },
  }), null, { demoParent: true, recipientId: "father" });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});

test("demo requires explicit recipient selection before audio", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "preset" }, localDemoEnabled: true }), null, { demoParent: true });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
test("foreign recipient is rejected before audio", async () => {
  const { api, calls } = hook(async () => ({ voice: { mode: "preset" }, localDemoEnabled: true }), null, { demoParent: true, recipientId: "foreign" });
  await api.startCall();
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
test("cancel during family lookup prevents late audio setup", async () => {
  let resolveFamily;
  const { api, calls } = hook(async () => ({ voice: { mode: "preset" }, localDemoEnabled: true }), null,
    { demoParent: true, recipientId: "mother" }, () => new Promise((resolve) => { resolveFamily = resolve; }));
  const pending = api.startCall();
  while (!resolveFamily) await Promise.resolve();
  api.endCall(); resolveFamily(family); await pending;
  assert.deepEqual(calls, { voice: 0, audio: 0 });
});
