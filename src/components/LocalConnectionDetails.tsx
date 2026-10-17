"use client";

import { useEffect, useState } from "react";
import type { PortalStatus } from "@/lib/portal-api";

/** Local operator diagnostics only. Never receives ID/refresh tokens. */
export function LocalConnectionDetails({
  identity,
  status,
  connectionError,
  familyError,
  onRetry,
}: {
  identity?: { owner: string; mode: "development" | "firebase" };
  status?: PortalStatus;
  connectionError: string;
  familyError: string;
  onRetry: () => void;
}) {
  const [local, setLocal] = useState(false);
  useEffect(() => {
    setLocal(["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname));
  }, []);
  if (!local) return null;
  const allowlistUid = identity?.mode === "firebase" && identity.owner.startsWith("firebase:")
    ? identity.owner.slice("firebase:".length) : "";

  return (
    <details className="fixed bottom-3 left-3 z-50 max-h-[60vh] w-[min(26rem,calc(100vw-1.5rem))] overflow-auto rounded-xl border border-stone-200 bg-white p-3 text-xs text-stone-700 shadow-lg">
      <summary className="cursor-pointer font-semibold">Local connection details</summary>
      <dl className="mt-3 space-y-2">
        <div><dt>Browser authentication</dt><dd>{identity?.mode ?? "Not confirmed"}</dd></div>
        <div><dt>Test operator identity</dt><dd className="break-all font-mono">{identity?.owner ?? "Not available"}</dd></div>
        {allowlistUid && <div><dt>Backend allowlist UID (without prefix)</dt><dd className="break-all font-mono">{allowlistUid}</dd></div>}
        <div><dt>Backend access</dt><dd>{status ? "Authenticated" : connectionError ? "Blocked" : "Checking"}</dd></div>
        <div><dt>Selected family store</dt><dd>{status?.selectedStateAdapter ?? status?.demoStorage ?? "Not confirmed"}</dd></div>
      </dl>
      {connectionError && <p role="alert" className="mt-3 text-rose-700">{connectionError}</p>}
      {familyError && <p role="alert" className="mt-3 text-rose-700">Family storage is unavailable. Check backend ADC and access to the named test database.</p>}
      <p className="mt-3">The UID is not a login token or proof of family identity. Approve only the intended test operator. Never copy ID or refresh tokens.</p>
      {allowlistUid && <p className="mt-2">Use the same browser profile and exact address for repeat tests. A new Incognito session, cleared site data, or switching between localhost and 127.0.0.1 can create a different UID needing separate approval. A backend restart does not change your browser identity. Existing family data stays with its original UID.</p>}
      <p className="mt-2">This panel reports the configured adapter, not verified Firestore connectivity. Only fictional test data is permitted.</p>
      <button type="button" className="mt-3 rounded-lg border border-stone-300 px-3 py-1.5 font-semibold" onClick={onRetry}>
        Retry connection
      </button>
    </details>
  );
}
