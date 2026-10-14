const { spawn } = require("node:child_process");

const isCloudRun = Boolean(process.env.K_SERVICE || process.env.K_REVISION);
const nextBin = require.resolve("next/dist/bin/next");
const args = isCloudRun ? ["start", "-H", "0.0.0.0"] : ["dev"];
const env = { ...process.env };

// The managed Cloud Build trigger currently invokes `npm run dev`. Cloud Run
// always supplies K_SERVICE/K_REVISION, so serve the build created by the
// buildpack instead of starting Next's development compiler in production.
if (isCloudRun) {
  env.NODE_ENV = "production";
}

const child = spawn(process.execPath, [nextBin, ...args], {
  env,
  stdio: "inherit",
});

const forwardSignal = (signal) => {
  if (!child.killed) child.kill(signal);
};

process.on("SIGINT", forwardSignal);
process.on("SIGTERM", forwardSignal);

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }

  process.exit(code ?? 1);
});
