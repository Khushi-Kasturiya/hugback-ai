const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const { audioHarness } = require("./audio-harness.cjs");
const compiled = ts.transpileModule(fs.readFileSync("src/hooks/useLiveAudio.ts", "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

async function callHarness({ autoOpening = false } = {}) {
  const audio = audioHarness(), states = [], transcriptions = [];
  const lifecycle = [];
  let socket, recorderCallback, stopped = false;
  const effects = [];
  class Socket {
    static OPEN = 1;
    constructor() {
      socket = this;
      this.readyState = 1;
      this.listeners = {};
      queueMicrotask(() => this.dispatch("open", {}));
    }
    addEventListener(type, fn) { (this.listeners[type] ||= new Set()).add(fn); }
    removeEventListener(type, fn) { this.listeners[type]?.delete(fn); }
    dispatch(type, event) {
      this[`on${type}`]?.(event);
      for (const fn of this.listeners[type] || []) fn(event);
    }
    emit(data) { this.dispatch("message", { data: JSON.stringify(data) }); }
    send(data) {
      if (typeof data !== "string") return;
      const message = JSON.parse(data);
      lifecycle.push(message.type);
      if (message.type === "authenticate") {
        queueMicrotask(() => this.emit({ type: "ready", autoOpening, voice: "replicated", sessionId: "synthetic" }));
      } else if (message.type === "start_greeting") {
        queueMicrotask(() => {
          this.emit(phrase("Hey Mumma, I am HugBack.", 128));
          this.emit({ turnComplete: true });
          lifecycle.push("opening-generated");
          setTimeout(() => {
            audio.render(128);
            audio.deliverEvents();
            lifecycle.push("opening-played");
          }, 0);
        });
      }
    }
    close() { this.readyState = 3; this.dispatch("close", {}); }
  }
  const modules = {
    react: {
      useState(initial) {
        const index = states.length; states.push(initial);
        return [initial, (value) => { states[index] = typeof value === "function" ? value(states[index]) : value; }];
      },
      useRef: (current) => ({ current }), useCallback: (callback) => callback,
      useEffect: (fn) => { effects.push(fn); },
    },
    "@/lib/audio-player": audio.api,
    "@/lib/audio-recorder": { startAudioRecorder: async (callback) => {
      lifecycle.push("recorder-started");
      recorderCallback = callback; return { stop() { stopped = true; } };
    } },
    "@/lib/identity": { getAuthenticationMessage: async () => ({ type: "authenticate" }) },
    "@/lib/voice-profile": { getInlineVoicePayload: async () => { throw new Error("No uploads"); } },
    "@/lib/portal-api": { portalGet: async () => ({ voice: { mode: "preset" } }) },
    "@/lib/voice-api": { selectedVoicePayload: () => ({ voiceProfileId: "synthetic" }) },
    "@/lib/demo-api": {},
  };
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, require: (name) => { if (!modules[name]) throw new Error(name); return modules[name]; },
    process: { env: {} }, WebSocket: Socket, Int16Array,
    window: { location: { protocol: "http:", hostname: "127.0.0.1" }, setTimeout, clearTimeout },
    console: { log() {}, warn() {}, error() {} }, performance, setTimeout, clearTimeout,
  });
  const api = exports.useLiveAudio({ onTranscriptionUpdate: (...args) => transcriptions.push(args) });
  await api.startCall();
  return {
    audio, api, states, transcriptions, effects, lifecycle,
    emit: (data) => socket.emit(data),
    get stopped() { return stopped; },
    speak: () => recorderCallback(new Int16Array(128).fill(2000).buffer),
    render(frames) { audio.render(frames); audio.deliverEvents(); },
  };
}

function phrase(text, frames = 256) {
  return { outputTranscription: { text, playbackAligned: true }, content: { parts: [
    { inlineData: { mimeType: "audio/pcm;rate=24000", data: Buffer.from(new Int16Array(frames).buffer).toString("base64") } },
  ] } };
}

test("demo greeting starts first and microphone waits for playback", async () => {
  const h = await callHarness({ autoOpening: true });
  try {
    assert.deepEqual(h.lifecycle.slice(0, 5), [
      "authenticate", "start_greeting", "opening-generated", "opening-played", "recorder-started",
    ]);
    assert.equal(h.states[3], "Hey Mumma, I am HugBack.");
  } finally { h.api.endCall(); }
});

test("replicated transcript waits for playback, user transcript stays immediate, complete waits for drain", async () => {
  const h = await callHarness();
  try {
    h.emit({ inputTranscription: { text: "How are you?" } });
    h.emit(phrase("First synthetic phrase."));
    h.emit(phrase("Second synthetic phrase."));
    h.emit({ turnComplete: true });
    assert.equal(h.states[2], "How are you?");
    assert.equal(h.states[3], "");
    assert.deepEqual(h.transcriptions, [["user", "How are you?"]]);
    h.render(128);
    assert.equal(h.states[0], "speaking");
    assert.equal(h.states[3], "First synthetic phrase.");
    h.emit({ turnComplete: true });
    assert.equal(h.states[0], "speaking");
    h.render(128);
    assert.equal(h.states[3], "First synthetic phrase.");
    h.render(128);
    assert.equal(h.states[3], "First synthetic phrase. Second synthetic phrase.");
    h.render(128);
    assert.equal(h.states[0], "listening");
    assert.equal(h.transcriptions.length, 3);
  } finally { h.api.endCall(); }
});

test("server interruption wins over bundled stale audio/text and queued phrases", async () => {
  const h = await callHarness();
  try {
    h.emit(phrase("Not yet spoken."));
    h.emit({ ...phrase("Bundled stale phrase."), interrupted: true });
    h.render();
    assert.equal(h.states[3], "");
    h.emit(phrase("New phrase.", 128)); h.render();
    assert.equal(h.states[3], "New phrase.");
  } finally { h.api.endCall(); }
});

test("loud local audio does not discard a pending child-voice phrase", async () => {
  const h = await callHarness();
  try {
    h.emit(phrase("Pending phrase."));
    h.speak(); h.render();
    assert.equal(h.states[3], "Pending phrase.");
  } finally { h.api.endCall(); }
});

test("call end, error and recipient switch prevent late subtitles", async () => {
  for (const action of ["end", "error", "switch"]) {
    const h = await callHarness();
    h.emit(phrase("Old recipient phrase."));
    h.audio.render(); // A late render-thread event is also invalidated.
    if (action === "end") h.api.endCall();
    if (action === "error") h.emit({ type: "error", message: "Synthetic failure" });
    if (action === "switch") h.effects[0]();
    h.audio.deliverEvents();
    assert.equal(h.states[3], "");
    assert.equal(h.stopped, true);
    h.api.endCall();
  }
});

test("standard voice text remains immediate; a missing aligned audio chunk never shows unspoken text", async () => {
  const h = await callHarness();
  try {
    h.emit({ outputTranscription: { text: "Standard synthetic response." } });
    assert.equal(h.states[3], "Standard synthetic response.");
    h.emit({ outputTranscription: { text: "Missing audio.", playbackAligned: true } });
    h.render();
    assert.equal(h.states[3], "Standard synthetic response.");
  } finally { h.api.endCall(); }
});

test("live words keep speaker order so scrolling reaches the newest turn", async () => {
  const h = await callHarness();
  try {
    h.emit({ inputTranscription: { text: "Hello." } });
    h.emit({ outputTranscription: { text: "Hello, I am HugBack." } });
    h.emit({ inputTranscription: { text: "I painted today." } });
    assert.deepEqual(Array.from(h.states[4], (entry) => ({ role: entry.role, text: entry.text })), [
      { role: "user", text: "Hello." },
      { role: "hugback", text: "Hello, I am HugBack." },
      { role: "user", text: "I painted today." },
    ]);
  } finally { h.api.endCall(); }
});

test("updated and overlapping Live caption chunks do not repeat words", async () => {
  const h = await callHarness();
  try {
    h.emit({ inputTranscription: { text: "I feel" } });
    h.emit({ inputTranscription: { text: "I feel calm today." } });
    h.emit({ outputTranscription: { text: "That sounds peaceful." } });
    h.emit({ outputTranscription: { text: "That sounds peaceful. Tell me more." } });
    h.emit({ outputTranscription: { text: "Tell me more. I am listening." } });
    assert.deepEqual(Array.from(h.states[4], (entry) => entry.text), [
      "I feel calm today.", "That sounds peaceful. Tell me more. I am listening.",
    ]);
    h.emit({ turnComplete: true });
    h.emit({ outputTranscription: { text: "I am still here." } });
    assert.equal(h.states[4].length, 3);
  } finally { h.api.endCall(); }
});
