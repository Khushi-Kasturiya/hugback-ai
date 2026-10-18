const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync("src/components/LocalConnectionDetails.tsx", "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function render(hostname, props) {
  let local = false;
  const effects = [];
  const modules = {
    react: {
      useState: () => [local, (value) => { local = value; }],
      useEffect: (fn) => effects.push(fn),
    },
    "react/jsx-runtime": {
      jsx: (type, props) => ({ type, props }),
      jsxs: (type, props) => ({ type, props }),
    },
  };
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    window: { location: { hostname } },
    require: (name) => {
      assert.ok(modules[name], `Unexpected dependency ${name}`);
      return modules[name];
    },
  });
  assert.equal(exports.LocalConnectionDetails(props), null, "Hidden before host check");
  effects.forEach((fn) => fn());
  return exports.LocalConnectionDetails(props);
}

function nodes(node) {
  if (Array.isArray(node)) return node.flatMap(nodes);
  if (!node || typeof node !== "object") return [];
  return [node, ...nodes(node.props?.children)];
}
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  return node && typeof node === "object" ? text(node.props?.children) : String(node ?? "");
}
const props = {
  identity: { owner: "firebase:synthetic-local-operator", mode: "firebase" },
  connectionError: "Operator is not allowlisted.",
  familyError: "",
  onRetry() {},
};

test("operator diagnostics never render on a hosted or lookalike origin", () => {
  for (const host of ["hugback.cloud.run", "localhost.example.com", "192.0.2.1"]) {
    assert.equal(render(host, props), null);
  }
});

test("loopback diagnostics expose only the operator UID while access is blocked", () => {
  for (const host of ["127.0.0.1", "localhost", "[::1]"]) {
    const tree = render(host, props);
    assert.match(text(tree), /firebase:synthetic-local-operator/);
    assert.match(text(tree), /Blocked/);
    assert.match(text(tree), /Operator is not allowlisted/);
    assert.match(text(tree), /not verified Firestore connectivity/);
  }
  assert.doesNotMatch(source, /localStorage|idToken|refreshToken|fetch\(/);
});

test("configured Firestore is not presented as a verified database read", () => {
  let retries = 0;
  const tree = render("127.0.0.1", {
    ...props, connectionError: "", familyError: "private provider detail",
    status: { selectedStateAdapter: "firestore" },
    onRetry: () => { retries += 1; },
  });
  assert.match(text(tree), /Authenticated/);
  assert.match(text(tree), /firestore/);
  assert.match(text(tree), /Family storage is unavailable/);
  assert.doesNotMatch(text(tree), /private provider detail/);
  nodes(tree).find((node) => node.type === "button").props.onClick();
  assert.equal(retries, 1);
});

test("Firebase diagnostics distinguish the raw allowlist UID and explain session changes", () => {
  const tree = render("127.0.0.1", props);
  const field = nodes(tree).find((node) =>
    node.type === "div" && text(node.props.children[0]) === "Backend allowlist UID (without prefix)");
  assert.ok(field);
  assert.equal(text(field.props.children[1]), "synthetic-local-operator");
  assert.match(text(tree), /new Incognito session/);
  assert.match(text(tree), /switching between localhost and 127\.0\.0\.1/);
  assert.match(text(tree), /backend restart does not change your browser identity/);
  assert.match(text(tree), /family data stays with its original UID/);
});

test("development identity is never suggested as a Firebase allowlist entry", () => {
  const tree = render("localhost", {
    ...props, identity: { owner: "development:synthetic", mode: "development" },
  });
  assert.doesNotMatch(text(tree), /Backend allowlist UID/);
});
