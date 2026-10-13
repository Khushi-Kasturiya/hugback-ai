// Executes the real player and worklet against a deterministic synthetic clock.
// No AudioContext, microphone, socket or hosted API is used.
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

function audioHarness() {
  let Processor, processor, node, context;
  const commands = [], events = [];
  vm.runInNewContext(fs.readFileSync("public/audio-worklets/pcm-player-processor.js", "utf8"), {
    Int16Array, Float32Array,
    AudioWorkletProcessor: class { constructor() { this.port = { postMessage: (data) => events.push(data) }; } },
    registerProcessor: (_, Class) => { Processor = Class; },
  });
  class Context {
    constructor() {
      context = this;
      this.state = "running";
      this.audioWorklet = { addModule: async () => {} };
    }
    async resume() { this.state = "running"; }
    async close() { this.state = "closed"; }
  }
  class Node {
    constructor() {
      node = this;
      processor = new Processor();
      this.port = { postMessage: (data) => commands.push(data), onmessage: null };
    }
    connect() {}
    disconnect() {}
  }
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync("src/lib/audio-player.ts", "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, {
    exports, AudioContext: Context, AudioWorkletNode: Node, Uint8Array,
    window: { atob: (text) => Buffer.from(text, "base64").toString("binary") }, console,
  });
  return {
    api: exports,
    commands, events,
    get processor() { return processor; },
    get context() { return context; },
    get node() { return node; },
    deliverCommands() {
      while (commands.length) processor.port.onmessage({ data: commands.shift() });
    },
    deliverEvents() {
      while (events.length) {
        const data = events.shift();
        node.port.onmessage?.({ data });
      }
    },
    render(frames = 128) {
      this.deliverCommands();
      const output = [new Float32Array(frames), new Float32Array(frames)];
      processor.process([], [output]);
      return output;
    },
  };
}
module.exports = { audioHarness };
