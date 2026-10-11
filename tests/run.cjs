// No new test dependency: compile isolated libraries, use Node's test runner.
const { mkdtempSync, rmSync, readdirSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { spawnSync } = require("node:child_process");
const out = mkdtempSync(join(tmpdir(), "elara-portal-tests-"));
let status = 1;
try {
  const compile = spawnSync(process.execPath, [
    "node_modules/typescript/bin/tsc", "--outDir", out, "--module", "commonjs",
    "--target", "ES2020", "--lib", "ES2020,DOM", "--skipLibCheck", "--strict",
    "src/lib/chat-import.ts", "src/lib/identity.ts", "src/lib/portal-api.ts",
    "src/lib/portal-storage.ts",
    "src/lib/demo-api.ts",
    "src/lib/voice-api.ts",
  ], { stdio: "inherit" });
  if (compile.status === 0) {
    const tests = readdirSync("tests").filter((name) => name.endsWith(".test.cjs")).map((name) => join("tests", name));
    status = spawnSync(process.execPath, ["--test", ...tests], {
      stdio: "inherit", env: { ...process.env, ELARA_TEST_BUILD: out },
    }).status ?? 1;
  }
} finally {
  rmSync(out, { recursive: true, force: true });
}
process.exit(status);
