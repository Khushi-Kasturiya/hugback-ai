const { test } = require("node:test");
const assert = require("node:assert/strict");
const { audioHarness } = require("./audio-harness.cjs");
const pcm = (frames) => new Int16Array(frames).fill(1000).buffer;

test("phrases are revealed at their own render position, not enqueue or first response audio", async () => {
  const h = audioHarness(), cues = [], states = [];
  const player = await h.api.startAudioPlayer({ onPlaybackChange: (value) => states.push(value) });
  player.playPcm(pcm(256), () => cues.push("first"));
  player.playPcm(pcm(128), () => cues.push("second"));
  assert.deepEqual(cues, []);
  assert.equal(player.isBusy(), true);
  h.render(); h.deliverEvents();
  assert.deepEqual(cues, ["first"]);
  h.render(); h.deliverEvents();
  assert.deepEqual(cues, ["first"]);
  assert.equal(player.isBusy(), true);
  h.render(); h.deliverEvents();
  assert.deepEqual(cues, ["first", "second"]);
  assert.deepEqual(states, [true, false]);
  assert.equal(player.isBusy(), false);
  assert.ok(h.render().every((channel) => channel.every((sample) => sample === 0)));
  player.stop();
});

test("flush drops queued and already-posted but undelivered subtitle callbacks", async () => {
  const h = audioHarness(), cues = [];
  const player = await h.api.startAudioPlayer();
  player.playPcm(pcm(256), () => cues.push("old"));
  h.render(); // Render-thread event exists, but main thread hasn't handled it.
  player.flush();
  h.deliverEvents();
  assert.deepEqual(cues, []);
  assert.ok(h.render().every((channel) => channel.every((sample) => sample === 0)));
  player.playPcm(pcm(128), () => cues.push("new"));
  h.render(); h.deliverEvents();
  assert.deepEqual(cues, ["new"]);
  player.stop();
});

test("an old drained notification cannot mark newer queued audio idle", async () => {
  const h = audioHarness();
  const player = await h.api.startAudioPlayer();
  player.playPcm(pcm(128));
  h.render();
  player.playPcm(pcm(256));
  h.deliverEvents();
  assert.equal(player.isBusy(), true);
  h.render(); h.deliverEvents();
  assert.equal(player.isBusy(), true);
  h.render(); h.deliverEvents();
  assert.equal(player.isBusy(), false);
  player.stop();
});

test("end call discards pending cues and ignores stale messages", async () => {
  const h = audioHarness(), cues = [];
  const player = await h.api.startAudioPlayer();
  player.playPcm(pcm(128), () => cues.push("discard"));
  h.render();
  player.stop(); player.stop();
  h.deliverEvents();
  assert.deepEqual(cues, []);
  assert.equal(h.context.state, "closed");
  assert.equal(player.isBusy(), false);
});

test("overflow fails closed without silently skipping speech or showing its caption", async () => {
  const h = audioHarness(), cues = [];
  let failures = 0;
  const player = await h.api.startAudioPlayer({ onError: () => failures++ });
  player.playPcm(pcm(24000 * 60 + 1), () => cues.push("discard"));
  h.render(); h.deliverEvents();
  assert.equal(failures, 1);
  assert.deepEqual(cues, []);
  assert.equal(player.isBusy(), false);
  player.stop();
});

test("empty and invalid PCM cannot reveal text; render errors stop playback", async () => {
  const h = audioHarness(), cues = [];
  let failures = 0;
  const player = await h.api.startAudioPlayer({ onError: () => failures++ });
  player.playPcm(pcm(0), () => cues.push("empty"));
  assert.throws(() => player.playPcm(new ArrayBuffer(1)), /PCM16/);
  assert.equal(player.isBusy(), false);
  player.playPcm(pcm(128), () => cues.push("failed"));
  h.node.onprocessorerror();
  h.render(); h.deliverEvents();
  assert.equal(failures, 1);
  assert.deepEqual(cues, []);
  player.stop();
});

test("ring wrap and variable render block sizes keep cues on their exact sample", async () => {
  const h = audioHarness(), cues = [];
  const player = await h.api.startAudioPlayer();
  h.processor.bufferSize = 16;
  h.processor.buffer = new Float32Array(16);
  player.playPcm(pcm(12), () => cues.push("one"));
  h.render(10); h.deliverEvents();
  player.playPcm(pcm(8), () => cues.push("two"));
  h.render(2); h.deliverEvents();
  assert.deepEqual(cues, ["one"]);
  h.render(8); h.deliverEvents();
  assert.deepEqual(cues, ["one", "two"]);
  assert.equal(player.isBusy(), false);
  player.stop();
});
