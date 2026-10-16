const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function history(recipient) {
  const state = [];
  const requests = [];
  let index = 0;
  let tree;
  const source = fs.readFileSync('src/components/DemoCallHistory.tsx', 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const modules = {
    react: { useState(initial) {
      const slot = index++;
      if (!(slot in state)) state[slot] = initial;
      return [state[slot], value => { state[slot] = typeof value === 'function' ? value(state[slot]) : value; }];
    } },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    '@/lib/demo-api': {
      demoCallSummary: async (recipientId, sessionId) => {
        requests.push({ recipientId, sessionId });
        return { sessionId, summary: 'The fictional parent talked about painting.' };
      },
      generateLegacyCallSummary: async () => { throw new Error('Unexpected paid conversion'); },
    },
  };
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => modules[name], Date, Intl });
  const render = () => { index = 0; tree = exports.DemoCallHistory({ recipient, refresh: async () => {} }); };
  const nodes = node => Array.isArray(node) ? node.flatMap(nodes) : !node || typeof node !== 'object' ? [] :
    [node, ...nodes(node.props?.children)];
  const text = node => Array.isArray(node) ? node.map(text).join('') : !node ? '' :
    typeof node === 'object' ? text(node.props?.children) : String(node);
  render();
  return { render, nodes: () => nodes(tree), text: () => text(tree), requests };
}

test('new Signals view fetches only a scoped summary and filters calls by recipient date', async () => {
  const recipient = {
    recipientId: 'demo-parent-' + 'a'.repeat(32), label: 'Mother', timeZone: 'Asia/Kolkata',
    transcriptSharingEnabled: true,
    calls: [
      { sessionId: 'session-old', startedAt: '2026-10-12T08:00:00Z', status: 'completed', summaryStatus: 'not_enabled' },
      { sessionId: 'session-new', startedAt: '2026-10-13T08:00:00Z', status: 'completed', summaryStatus: 'available' },
    ],
  };
  const ui = history(recipient);
  assert.equal(ui.nodes().filter(node => node.type === 'li').length, 2);
  assert.equal(ui.requests.length, 0);
  const summaryButton = ui.nodes().find(node => node.type === 'button' && node.props['aria-expanded'] === false);
  summaryButton.props.onClick();
  await new Promise(setImmediate);
  ui.render();
  assert.deepEqual(ui.requests, [{ recipientId: recipient.recipientId, sessionId: 'session-new' }]);
  assert.match(ui.text(), /fictional parent talked about painting/);
  const date = ui.nodes().find(node => node.type === 'input' && node.props.type === 'date');
  date.props.onChange({ target: { value: '2026-10-12' } });
  ui.render();
  assert.equal(ui.nodes().filter(node => node.type === 'li').length, 1);
  assert.doesNotMatch(ui.text(), /fictional parent talked about painting/);
});
