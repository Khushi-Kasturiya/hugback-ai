// Component lifecycle with synthetic files and mocked transport; no browser uploads.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const compiled = ts.transpileModule(fs.readFileSync('src/components/VoiceEnrollment.tsx', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const created = { id: 'synthetic-profile', expiresAt: '2099-01-01T00:00:00Z', enabled: false, expired: false };
function harness({ enabled = true, profile = null, failUpload = false, recipient,
                   failAssignment = false, identityMode = 'development' } = {}) {
  let index = 0, tree;
  const states = [], requests = [];
  const initialVoice = { mode: 'preset', name: 'Aoede', replicatedTtsEnabled: enabled, profile };
  const modules = {
    react: { useEffect() {}, useState: (initial) => {
      const i = index++;
      if (states.length <= i) states.push(initial);
      return [states[i], (value) => { states[i] = typeof value === 'function' ? value(states[i]) : value; }];
    } },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'next/link': { default: 'a' },
    'lucide-react': new Proxy({}, { get: (_, name) => String(name) }),
    '@/components/BrowserAudioRecorder': { BrowserAudioRecorder: 'BrowserAudioRecorder' },
    '@/lib/voice-wav': { prepareVoiceWav: async (file) => file },
    '@/lib/voice-profile': { deleteLocalVoiceProfile: async () => {}, hasLocalVoiceProfile: async () => false },
    '@/lib/portal-api': { portalGet: async () => ({ identityMode, voice: initialVoice }) },
    '@/lib/demo-api': {
      parentCallUrl: (id) => `/call?recipient=${encodeURIComponent(id)}`,
      demoRequest: async (path, method, body) => {
        requests.push({ path, method, body });
        if (failAssignment) throw new Error('Assignment not confirmed');
        return { recipients: [{ ...recipient, revision: recipient.revision + 1,
          voice: { mode: body.mode, profileId: body.profileId } }] };
      },
    },
    '@/lib/voice-api': { audioBase64: async () => 'synthetic', voiceRequest: async (path, method, body) => {
      requests.push({ path, method, body });
      if (method === 'POST' && failUpload) throw new Error('Network uncertain');
      return { profile: method === 'POST' ? created : method === 'PUT' ? { ...created, enabled: body.enabled } : null };
    } },
  };
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: (name) => {
    if (!modules[name]) throw new Error(`Unexpected module ${name}`);
    return modules[name];
  }, window: { confirm: () => true }, Date });
  function render() { index = 0; tree = exports.VoiceEnrollment({ voice: initialVoice, recipient,
    onAssigned: (family) => { recipient = family.recipients.find(r => r.recipientId === recipient.recipientId); },
  }); }
  function nodes(node = tree) {
    if (Array.isArray(node)) return node.flatMap(nodes);
    if (!node || typeof node !== 'object') return [];
    return [node, ...nodes(node.props?.children ?? null)];
  }
  function text(node) {
    if (Array.isArray(node)) return node.map(text).join('');
    if (!node) return '';
    return typeof node === 'object' ? text(node.props?.children) : String(node);
  }
  function button(label) { return nodes().find((n) => n.type === 'button' && text(n).includes(label)); }
  function prepare() {
    nodes().filter((n) => n.type === 'BrowserAudioRecorder').forEach((n) => n.props.onRecorded({ name: 'synthetic.webm' }));
    render();
  }
  function consent() { nodes().find((n) => n.type === 'input' && n.props.type === 'checkbox').props.onChange({ target: { checked: true } }); render(); }
  render();
  return { render, button, nodes, requests, prepare, consent,
    setRecipient(value) { recipient = value; render(); } };
}
test('browser recording stays local; voice creation requires explicit consent and separate activation', async () => {
  const ui = harness();
  assert.equal(ui.button('Create voice').props.disabled, true);
  ui.prepare();
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.button('Create voice').props.disabled, true);
  ui.consent();
  assert.equal(ui.button('Create voice').props.disabled, false);
  await ui.button('Create voice').props.onClick(); ui.render();
  assert.equal(ui.requests.length, 1);
  assert.equal(ui.requests[0].body.consentToGoogleAndBilling, true);
  assert.equal(ui.requests[0].body.adultOwnVoice, true);
  assert.equal(ui.button('Enable child voice').props.disabled, false);
  await ui.button('Enable child voice').props.onClick(); ui.render();
  assert.equal(ui.requests[1].body.enabled, true);
  assert.equal(ui.button('Disable child voice').props.disabled, false);
  await ui.button('Disable child voice').props.onClick(); ui.render();
  assert.equal(ui.requests[2].body.enabled, false);
});
test('feature disabled blocks both browser recorders and makes no requests', () => {
  const ui = harness({ enabled: false });
  assert.equal(ui.button('Create voice').props.disabled, true);
  for (const node of ui.nodes().filter((n) => n.type === 'BrowserAudioRecorder')) assert.equal(node.props.disabled, true);
  for (const node of ui.nodes().filter((n) => n.type === 'input')) assert.equal(node.props.disabled, true);
  assert.equal(ui.requests.length, 0);
});
test('uncertain upload blocks repeated paid submission until explicit refresh', async () => {
  const ui = harness({ failUpload: true }); ui.prepare(); ui.consent();
  await ui.button('Create voice').props.onClick(); ui.render();
  assert.equal(ui.button('Create voice').props.disabled, true);
  assert.equal(ui.requests.length, 1);
  await ui.button('Refresh status').props.onClick(); ui.render();
  assert.equal(ui.button('Create voice').props.disabled, false);
});
test('expired voice can be disabled or removed, never enabled', async () => {
  const ui = harness({ profile: { ...created, enabled: true, expired: true } });
  assert.equal(ui.button('Enable child voice').props.disabled, true);
  assert.equal(ui.button('Disable child voice').props.disabled, false);
  await ui.button('Remove voice').props.onClick(); ui.render();
  assert.equal(ui.requests[0].method, 'DELETE');
});

const father = { recipientId: 'synthetic-father', label: 'Father', revision: 3, busy: false,
  voice: { mode: 'standard', profileId: null } };
const callLinks = (ui) => ui.nodes().filter(n => n.props?.href?.startsWith('/call'));
test('enabled voice with no recipient leads to assignment, never unscoped preview', () => {
  const ui = harness({ profile: { ...created, enabled: true } });
  assert.equal(callLinks(ui).length, 0);
  assert.ok(ui.nodes().some(n => n.props?.href === '#family-dashboard'));
  assert.equal(ui.requests.length, 0);
});
test('create replacement -> enable -> assign Father -> preview carries the exact recipient', async () => {
  const ui = harness({ profile: { ...created, id: 'old-profile', enabled: true }, recipient: {
    ...father, voice: { mode: 'child', profileId: 'old-profile' },
  } });
  ui.prepare(); ui.consent();
  await ui.button('Create replacement voice').props.onClick(); ui.render();
  assert.equal(callLinks(ui).length, 0);
  assert.equal(ui.button('Assign this voice to Father').props.disabled, true);
  await ui.button('Enable child voice').props.onClick(); ui.render();
  assert.equal(callLinks(ui).length, 0); // Enabling still must not imply assignment.
  await ui.button('Assign this voice to Father').props.onClick(); ui.render();
  const assignment = ui.requests.find(r => r.path === '/recipient-voice');
  assert.equal(assignment.body.recipientId, 'synthetic-father');
  assert.equal(assignment.body.profileId, 'synthetic-profile');
  assert.equal(assignment.body.revision, 3);
  assert.equal(callLinks(ui)[0].props.href, '/call?recipient=synthetic-father');
  ui.setRecipient({ ...father, recipientId: 'synthetic-mother', label: 'Mother' });
  assert.equal(callLinks(ui).length, 0); // No inherited assignment/preview for Mother.
});
test('failed assignment never exposes a preview link or changes the recipient', async () => {
  const ui = harness({ profile: { ...created, enabled: true }, recipient: father, failAssignment: true });
  await ui.button('Assign this voice to Father').props.onClick(); ui.render();
  assert.equal(callLinks(ui).length, 0);
  assert.equal(ui.requests.length, 1);
});
test('busy recipient blocks assignment and Firebase uncertain upload can be refreshed', async () => {
  const busy = harness({ profile: { ...created, enabled: true }, recipient: { ...father, busy: true } });
  assert.equal(busy.button('Assign this voice to Father').props.disabled, true);
  const ui = harness({ failUpload: true, identityMode: 'firebase' });
  ui.prepare(); ui.consent();
  await ui.button('Create voice').props.onClick(); ui.render();
  assert.equal(ui.button('Create voice').props.disabled, true);
  await ui.button('Refresh status').props.onClick(); ui.render();
  assert.equal(ui.button('Create voice').props.disabled, false);
});
