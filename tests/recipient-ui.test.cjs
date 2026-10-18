const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const { join } = require('node:path');
const { parentCallUrl, reviewedExcerpts, automaticBackgroundExcerpts } = require(join(process.env.HUGBACK_TEST_BUILD, 'demo-api.js'));

const mother = { recipientId: 'mother', label: 'Mother', revision: 4, background: [], calls: [], voice: { mode: 'standard', profileId: null } };
const father = { ...mother, recipientId: 'father', label: 'Father', revision: 1 };
const family = { familyId: 'demo-family-' + 'a'.repeat(32), childName: 'Asha', childGender: null,
  childGenderRevision: 0, recipients: [mother, father], expiresAt: '2099-01-01T00:00:00Z' };
function component(file, name, initialProps) {
  let index = 0, tree, props = initialProps;
  const states = [], requests = [], effects = []; let effectIndex = 0, pendingEffects = [];
  const modules = {
    react: { useEffect(fn, deps) { const i = effectIndex++; if (!effects[i] || deps.some((v, j) => v !== effects[i][j])) { effects[i] = deps; pendingEffects.push(fn); } }, useState: (initial) => {
      const i = index++; if (states.length <= i) states.push(initial);
      return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value; }];
    } },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'next/link': { default: 'a' },
    '@/lib/demo-api': { parentCallUrl, reviewedExcerpts, automaticBackgroundExcerpts, demoRequest: async (path, method, body) => { requests.push({ path, method, body }); return family; } },
    '@/lib/portal-storage': { loadChildPhoto: async () => null, saveChildPhoto: async () => {}, removeChildPhoto: async () => {} },
  };
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => { if (!modules[name]) throw new Error(name); return modules[name]; }, Date });
  function render(next = props) { props = next; index = 0; effectIndex = 0; pendingEffects = []; tree = exports[name](props); pendingEffects.forEach(fn => fn()); }
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
  assert.equal(Object.hasOwn(ui.requests[0].body, 'speakingForm'), false);
});
test('speaking form cannot be manually chosen in Family setup', () => {
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, selectedId: 'mother' });
  assert.equal(ui.button('Save speaking form'), undefined);
  assert.equal(ui.nodes().some(n => n.type === 'select' && ui.text(n).includes('Masculine')), false);
});
test('new family asks child name and gender and sends both with setup details', async () => {
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, family: undefined });
  assert.equal(ui.button('Create family bridge').props.disabled, true);
  const name = ui.nodes().find(n => n.type === 'input' && n.props.placeholder === 'Fictional child name');
  name.props.onChange({ target: { value: 'Asha' } }); ui.render();
  const selector = ui.nodes().find(n => n.type === 'select' && ui.text(n).includes('Use neutral phrasing'));
  selector.props.onChange({ target: { value: 'male' } }); ui.render();
  await ui.button('Create family bridge').props.onClick();
  assert.equal(ui.requests[0].body.childName, 'Asha');
  assert.equal(ui.requests[0].body.childGender, 'male');
  assert.equal(ui.requests[0].body.enableMemory, true);
  assert.equal(ui.requests[0].body.enableWellbeingSharing, false);
  assert.equal(ui.requests[0].body.enableTranscriptSharing, true);
});
test('existing family can save child gender without changing recipients or voice profile', async () => {
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, selectedId: 'mother' });
  const selector = ui.nodes().find(n => n.type === 'select' && ui.text(n).includes('Another identity'));
  selector.props.onChange({ target: { value: 'female' } }); ui.render();
  await ui.button('Save child details').props.onClick();
  assert.equal(ui.requests[0].path, '/child-details');
  assert.equal(ui.requests[0].body.familyId, family.familyId);
  assert.equal(ui.requests[0].body.revision, 0);
  assert.equal(ui.requests[0].body.childGender, 'female');
  assert.equal(ui.requests[0].body.childName, 'Asha');
  assert.equal(Object.hasOwn(ui.requests[0].body, 'profileId'), false);
});
test('existing recipient can stop call signal sharing without changing another recipient', async () => {
  const enabledMother = { ...mother, wellbeingSharingEnabled: true, wellbeingSignals: [] };
  const scopedFamily = { ...family, recipients: [enabledMother, father] };
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, family: scopedFamily, selectedId: 'mother' });
  await ui.button('Turn off signals').props.onClick();
  assert.equal(ui.requests[0].path, '/wellbeing-sharing');
  assert.equal(ui.requests[0].body.recipientId, 'mother');
  assert.equal(ui.requests[0].body.enabled, false);
});
test('tone continuity uses one explicit button and can be stopped for one recipient', async () => {
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, selectedId: 'mother' });
  await ui.button('Enable tone check-ins').props.onClick();
  assert.equal(ui.requests[0].path, '/tone-continuity');
  assert.equal(ui.requests[0].body.recipientId, 'mother');
  assert.equal(ui.requests[0].body.simulateParentConsent, true);
  await new Promise(setImmediate);
  const enabled = { ...mother, toneContinuityEnabled: true };
  ui.render({ ...baseProps, family: { ...family, recipients: [enabled, father] }, selectedId: 'mother' });
  assert.equal(!!ui.button('Turn off and erase tone note').props.disabled, false);
  await ui.button('Turn off and erase tone note').props.onClick();
  assert.equal(ui.requests.length, 2, ui.requests);
  assert.equal(ui.requests[1].body.enabled, false);
  assert.equal(ui.requests[1].body.recipientId, 'mother');
});
test('new parent setup is a single action with optional features off', async () => {
  const ui = component(setupFile, 'DemoFamilySetup', baseProps);
  ui.button('+ Add parent').props.onClick(); ui.render();
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.button('Add parent').props.disabled, false);
  await ui.button('Add parent').props.onClick();
  assert.equal(ui.requests[0].body.simulateParentConsent, true);
  assert.equal(ui.requests[0].body.enableWellbeingSharing, false);
  assert.equal(ui.requests[0].body.enableToneContinuity, false);
  assert.equal(ui.requests[0].body.simulateToneConsent, false);
  assert.equal(ui.requests[0].path, '/recipients');
});
test('one action prepares parent messages only for the selected recipient and revision', async () => {
  const preview = { source: 'whatsapp', participants: ['Child', 'Parent'], messages: [{ sender: 'Parent', timestamp: '2026-10-01T18:00:00', text: 'A fictional garden.' }] };
  const ui = component('src/components/DemoBackgroundReview.tsx', 'DemoBackgroundReview', {
    recipient: mother, preview, child: 'Child', parent: 'Parent', timezone: 'Asia/Kolkata', onChange() {},
  });
  for (const input of ui.nodes().filter(n => n.type === 'input')) input.props.onChange({ target: { checked: true } });
  ui.render();
  await ui.button("Prepare Mother's background").props.onClick();
  assert.equal(ui.requests[0].body.recipientId, 'mother');
  assert.equal(ui.requests[0].body.revision, 4);
  assert.equal(ui.requests[0].body.excerpts[0].text, 'A fictional garden.');
});

test('optional settings are collapsed and email has one delivery acknowledgement', () => {
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, selectedId: 'mother' });
  assert.match(ui.text(ui.nodes()), /Optional demo features/);
  assert.equal(ui.nodes().filter(n => n.type === 'input' && n.props.type === 'checkbox').length, 1);
});

test('family email is sent to backend only after explicit Family setup confirmation', async () => {
  const scopedFamily = { ...family, familyId: 'demo-family-' + 'a'.repeat(32), storageMode: 'sqlite' };
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, family: scopedFamily, selectedId: 'mother' });
  assert.equal(ui.button('Save email').props.disabled, true);
  assert.equal(ui.requests.length, 0);
  const input = ui.nodes().find(n => n.type === 'input' && n.props.type === 'email');
  input.props.onChange({ target: { value: 'child@example.com' } });
  // The label owns the text; choose the confirmation checkbox by its parent label.
  const label = ui.nodes().find(n => n.type === 'label' && ui.text(n).includes('Send future call summaries'));
  label.props.children[0].props.onChange({ target: { checked: true } });
  ui.render();
  assert.equal(ui.button('Save email').props.disabled, false);
  await ui.button('Save email').props.onClick();
  assert.equal(ui.requests[0].path, '/alert-destination');
  assert.equal(ui.requests[0].body.email, 'child@example.com');
  assert.equal(ui.requests[0].body.familyId, scopedFamily.familyId);
  assert.equal(ui.requests[0].body.confirmTestRecipient, true);
});

test('Firestore accepts an owner-scoped email and returns only a masked address', async () => {
  const scopedFamily = { ...family, storageMode: 'firestore', alertEmailSelected: true,
    alertEmailConfigured: true, alertEmailHint: 'k***@gmail.com' };
  const ui = component(setupFile, 'DemoFamilySetup', { ...baseProps, family: scopedFamily, selectedId: 'mother' });
  const input = ui.nodes().find(n => n.type === 'input' && n.props.type === 'email');
  assert.ok(input);
  assert.match(ui.text(ui.nodes()), /Inbox ready: k\*\*\*@gmail\.com/);
  input.props.onChange({ target: { value: 'new@example.com' } });
  const label = ui.nodes().find(n => n.type === 'label' && ui.text(n).includes('Send future call summaries'));
  label.props.children[0].props.onChange({ target: { checked: true } });
  ui.render();
  await ui.button('Save email').props.onClick();
  assert.equal(ui.requests[0].path, '/alert-destination');
  assert.equal(ui.requests[0].body.email, 'new@example.com');
});
