const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const { join } = require('node:path');
const { parentCallUrl, reviewedExcerpts } = require(join(process.env.HUGBACK_TEST_BUILD, 'demo-api.js'));

const mother = { recipientId: 'mother', label: 'Mother', revision: 4, background: [], calls: [], voice: { mode: 'standard', profileId: null } };
const father = { ...mother, recipientId: 'father', label: 'Father', revision: 1 };
const family = { recipients: [mother, father], expiresAt: '2099-01-01T00:00:00Z' };
function component(file, name, initialProps) {
  let index = 0, tree, props = initialProps;
  const states = [], requests = [];
  const modules = {
    react: { useEffect() {}, useState: (initial) => {
      const i = index++; if (states.length <= i) states.push(initial);
      return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value; }];
    } },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'next/link': { default: 'a' },
    '@/lib/demo-api': { parentCallUrl, reviewedExcerpts, demoRequest: async (path, method, body) => { requests.push({ path, method, body }); return family; } },
  };
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => { if (!modules[name]) throw new Error(name); return modules[name]; }, Date });
  function render(next = props) { props = next; index = 0; tree = exports[name](props); }
  function nodes(node) {
    if (Array.isArray(node)) return node.flatMap(nodes);
    if (!node || typeof node !== 'object') return [];
    return [node, ...nodes(node.props?.children ?? null)];
  }
  function text(node) { return Array.isArray(node) ? node.map(text).join('') : !node ? '' : typeof node === 'object' ? text(node.props?.children) : String(node); }
  function button(label) { return nodes(tree).find(n => n.type === 'button' && text(n).includes(label)); }
  render(); return { nodes: () => nodes(tree), button, render, requests, text };
}
const setupFile = 'src/components/DemoFamilySetup.tsx';
const baseProps = { family, selectedId: '', onSelect() {}, onChange() {}, refresh: async () => {}, loading: false, loadError: '' };

test('family setup requires explicit recipient choice; selection itself makes no request', () => {
  const selected = [];
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, onSelect: id => selected.push(id) });
  assert.equal(selected.length, 0);
  ui.button('Mother').props.onClick();
  assert.deepEqual(selected, ['mother']);
  assert.equal(ui.requests.length, 0);
});
test('voice assignment includes selected recipient revision and authorized child profile', async () => {
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, selectedId: 'mother', voice: {
    replicatedTtsEnabled: true, profile: { id: 'synthetic-voice', enabled: true, expired: false, expiresAt: '2099-01-01T00:00:00Z' },
  } });
  await ui.button('Assign child voice').props.onClick();
  assert.equal(ui.requests[0].path, '/recipient-voice');
  assert.equal(ui.requests[0].body.recipientId, 'mother');
  assert.equal(ui.requests[0].body.revision, 4);
  assert.equal(ui.requests[0].body.profileId, 'synthetic-voice');
});
test('existing recipient can stop call signal sharing without changing another recipient', async () => {
  const enabledMother = { ...mother, wellbeingSharingEnabled: true, wellbeingSignals: [] };
  const scopedFamily = { ...family, recipients: [enabledMother, father] };
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, family: scopedFamily, selectedId: 'mother' });
  await ui.button('Stop sharing call signals').props.onClick();
  assert.equal(ui.requests[0].path, '/wellbeing-sharing');
  assert.equal(ui.requests[0].body.recipientId, 'mother');
  assert.equal(ui.requests[0].body.enabled, false);
});
test('new recipient needs separate simulated consent; nothing auto-creates Father', async () => {
  const ui = component(setupFile, 'DemoFamilySetup', baseProps);
  ui.button('+ Add recipient').props.onClick(); ui.render();
  assert.equal(ui.button('Add recipient').props.disabled, true);
  assert.equal(ui.requests.length, 0);
  for (const node of ui.nodes().filter(n => n.type === 'input' && n.props.type === 'checkbox')) node.props.onChange({ target: { checked: true } });
  ui.render();
  assert.equal(ui.button('Add recipient').props.disabled, false);
  await ui.button('Add recipient').props.onClick();
  assert.equal(ui.requests[0].body.simulateParentConsent, true);
  assert.equal(ui.requests[0].body.enableWellbeingSharing, true);
  assert.equal(ui.requests[0].path, '/recipients');
});
test('review sends excerpts only to the selected recipient and their revision', async () => {
  const preview = { source: 'whatsapp', participants: ['Child', 'Parent'], messages: [{ sender: 'Parent', timestamp: '2026-10-01T18:00:00', text: 'A fictional garden.' }] };
  const ui = component('src/components/DemoBackgroundReview.tsx', 'DemoBackgroundReview', {
    recipient: mother, preview, child: 'Child', parent: 'Parent', timezone: 'Asia/Kolkata', onChange() {},
  });
  for (const input of ui.nodes().filter(n => n.type === 'input')) input.props.onChange({ target: { checked: true } });
  ui.render();
  await ui.button('Use 1 reviewed excerpts for Mother').props.onClick();
  assert.equal(ui.requests[0].body.recipientId, 'mother');
  assert.equal(ui.requests[0].body.revision, 4);
  assert.equal(ui.requests[0].body.excerpts[0].text, 'A fictional garden.');
});
