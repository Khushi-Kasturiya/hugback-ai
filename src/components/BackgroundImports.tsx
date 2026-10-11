"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, LockKeyhole, Trash2, Upload } from "lucide-react";
import { ChatPreview, ChatSource, DateOrder, MAX_IMPORT_BYTES, parseChat, SYNTHETIC_CHAT } from "@/lib/chat-import";
import { BackgroundImport, listImports, removeImport, saveImport } from "@/lib/portal-storage";
import { DemoBackgroundReview } from "@/components/DemoBackgroundReview";
import { DemoFamily, DemoRecipient, demoRequest } from "@/lib/demo-api";

export function BackgroundImports({ owner, demoRecipient, onDemoChange }: {
  owner?: string; demoRecipient?: DemoRecipient; onDemoChange?: (family: DemoFamily) => void;
}) {
  const [source, setSource] = useState<ChatSource>("whatsapp");
  const [order, setOrder] = useState<DateOrder>("DMY");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [preview, setPreview] = useState<ChatPreview | null>(null);
  const [filename, setFilename] = useState("");
  const [fingerprint, setFingerprint] = useState("");
  const [child, setChild] = useState("");
  const [parent, setParent] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [records, setRecords] = useState<BackgroundImport[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const operation = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let current = true;
    if (owner) void listImports(owner, demoRecipient?.recipientId, demoRecipient?.legacy).then((items) => { if (current) setRecords(items); })
      .catch(() => { if (current) setError("Local background storage is unavailable."); });
    return () => { current = false; operation.current++; };
  }, [owner, demoRecipient?.recipientId, demoRecipient?.legacy]);

  function resetPreview() {
    operation.current++;
    setBusy(false); setPreview(null); setFingerprint(""); setChild(""); setParent("");
    setAcknowledged(false); setError(""); setMessage("");
    if (fileInput.current) fileInput.current.value = "";
  }

  async function previewText(text: string, name: string, sequence: number) {
    const parsed = parseChat(text, source, order);
    const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${source}:${order}:${text}`));
    if (sequence !== operation.current) return;
    setPreview(parsed); setFilename(name);
    setFingerprint(Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, "0")).join(""));
  }

  async function readFile(file?: File) {
    resetPreview();
    if (!file) return;
    const sequence = operation.current;
    setBusy(true);
    try {
      const allowed = source === "instagram" ? /\.(txt|json)$/i : /\.txt$/i;
      if (!allowed.test(file.name)) throw new Error(source === "instagram" ? "Choose a .txt or single-conversation .json file." : "Choose a WhatsApp .txt export without media.");
      if (file.size > MAX_IMPORT_BYTES) throw new Error("Choose a file smaller than 1 MB.");
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      await previewText(text, file.name, sequence);
    } catch (err) {
      if (sequence === operation.current) setError(err instanceof Error ? err.message : "The file could not be read.");
    } finally { if (sequence === operation.current) setBusy(false); }
  }

  async function example() {
    resetPreview();
    const sequence = operation.current;
    setBusy(true);
    try { await previewText(SYNTHETIC_CHAT, "synthetic-conversation.txt", sequence); }
    catch { setError("The example could not be opened."); }
    finally { if (sequence === operation.current) setBusy(false); }
  }

  async function save() {
    if (!owner || !preview || !acknowledged) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await saveImport(owner, { recipientId: demoRecipient?.recipientId, filename, fingerprint, childSender: child, parentSender: parent, timezone, preview });
      setRecords(await listImports(owner, demoRecipient?.recipientId, demoRecipient?.legacy));
      resetPreview();
      setMessage("Saved on this browser for seven days. Not uploaded, extracted by AI, or used in calls.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save this file."); }
    finally { setBusy(false); }
  }

  async function remove(id: string) {
    if (!owner || !window.confirm("Delete this local conversation preview? It has not been uploaded or used in calls.")) return;
    setBusy(true); setError("");
    try {
      await removeImport(owner, id);
      setRecords(await listImports(owner, demoRecipient?.recipientId, demoRecipient?.legacy));
      setMessage("Local conversation preview deleted.");
    } catch { setError("Deletion could not be confirmed. Please retry."); }
    finally { setBusy(false); }
  }

  function reopen(record: BackgroundImport) {
    resetPreview();
    setSource(record.preview.source);
    setPreview(record.preview); setFilename(record.filename); setFingerprint(record.fingerprint);
    setChild(record.childSender); setParent(record.parentSender); setTimezone(record.timezone);
  }

  async function clearDemo() {
    if (!demoRecipient || !onDemoChange || !window.confirm(`Remove ${demoRecipient.label}’s reviewed background from future calls? Other recipients and local previews are unchanged.`)) return;
    setBusy(true); setError("");
    try { onDemoChange(await demoRequest("/background/clear", "POST", { syntheticOnly: true, recipientId: demoRecipient.recipientId, revision: demoRecipient.revision })); }
    catch (err) { setError(err instanceof Error ? err.message : "Demo background could not be removed."); }
    finally { setBusy(false); }
  }

  return <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold tracking-tight">{demoRecipient ? `Background for ${demoRecipient.label}` : "A little background goes a long way."}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">Prepare a direct conversation with your parent. Preserve who said what and when—Elara should understand your family, not pretend to be you.</p>
    </div>
    <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
      <LockKeyhole className="mt-1 h-4 w-4 shrink-0" />
      <p><strong>{demoRecipient ? "Synthetic demo context." : "Local preview only."}</strong> {demoRecipient ? "Files are parsed in this browser. Only excerpts you explicitly review below are saved on the local backend and used in demo calls. Real family uploads remain inactive." : "Files stay on this browser. Real-family AI extraction and use during calls are not connected yet and require both participants’ verified consent. Avoid secrets and unrelated conversations."}</p>
    </div>
    <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="portal-label">Conversation source
          <select className="portal-input" value={source} disabled={busy} onChange={(e) => { setSource(e.target.value as ChatSource); resetPreview(); }}>
            <option value="whatsapp">WhatsApp</option><option value="instagram">Instagram</option>
          </select>
        </label>
        <label className="portal-label">Export date order
          <select className="portal-input" value={order} disabled={busy} onChange={(e) => { setOrder(e.target.value as DateOrder); resetPreview(); }}>
            <option value="DMY">Day / month / year</option><option value="MDY">Month / day / year</option>
          </select>
        </label>
        <label className="portal-label">Conversation timezone
          <input className="portal-input" value={timezone} maxLength={80} onChange={(e) => setTimezone(e.target.value)} placeholder="Asia/Kolkata" />
        </label>
      </div>
      <label className="mt-5 flex cursor-pointer flex-col items-center rounded-2xl border-2 border-dashed border-stone-200 bg-stone-50/60 px-5 py-8 text-center hover:border-emerald-600">
        <span className="mb-3 rounded-xl bg-emerald-50 p-3 text-emerald-800"><Upload className="h-6 w-6" /></span>
        <span className="font-semibold">Choose a conversation file</span>
        <span className="mt-1 text-xs leading-5 text-stone-500">Text only · Up to 1 MB / 2,000 messages · Two participants</span>
        <input ref={fileInput} type="file" className="mt-4 block max-w-full text-xs file:mr-3 file:rounded-lg file:border-0 file:bg-stone-200 file:px-3 file:py-2"
          aria-label="Conversation file" accept={source === "whatsapp" ? ".txt" : ".txt,.json"} disabled={busy} onChange={(e) => void readFile(e.target.files?.[0])} />
      </label>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs">
        <span className="text-stone-500">No chats to hand? Explore with fictional messages.</span>
        <button className="font-semibold text-emerald-800 underline underline-offset-4 disabled:opacity-50" disabled={busy} onClick={() => void example()}>Try a synthetic example</button>
      </div>
      {source === "instagram" && <details className="mt-4 text-xs leading-6 text-stone-600">
        <summary className="cursor-pointer font-semibold">Supported Instagram formats</summary>
        <p>One conversation JSON with participants, messages, sender_name, timestamp_ms, and content; or the normalized text template below. This is not universal support for Instagram exports. HTML, ZIP, media and whole-account archives are not accepted.</p>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-stone-100 p-3">{"[2026-10-01T18:00:00+05:30] Parent: Hello\n[2026-10-01T18:01:00+05:30] Child: Hi"}</pre>
      </details>}
    </section>
    {busy && <p role="status" className="text-sm text-stone-600">Working locally…</p>}
    {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {message && <p role="status" className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">{message}</p>}
    {preview && <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-6">
      <h3 className="font-bold">Review before saving</h3>
      <p className="mt-1 break-words text-xs text-stone-500">{filename} · {preview.messages.length} text messages · {preview.skipped} system/media entries skipped</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="portal-label">Which participant is you?
          <select className="portal-input" value={child} onChange={(e) => setChild(e.target.value)}>
            <option value="">Choose the child</option>{preview.participants.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label className="portal-label">Which participant is {demoRecipient?.label || "your parent"}?
          <select className="portal-input" value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">Choose the parent</option>{preview.participants.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-4 max-h-72 space-y-3 overflow-y-auto rounded-xl bg-stone-50 p-4" tabIndex={0} aria-label="Conversation preview">
        {preview.messages.slice(0, 100).map((m, i) => <div key={i} className="text-sm">
          <div className="flex flex-wrap gap-x-3 text-xs"><strong>{m.sender}</strong><span className="text-stone-500">{m.timestamp}</span></div>
          <p className="mt-1 whitespace-pre-wrap break-words text-stone-700">{m.text}</p>
        </div>)}
        {preview.messages.length > 100 && <p className="text-xs text-stone-500">Showing the first 100 messages; the full parsed conversation will be saved locally.</p>}
      </div>
      <label className="mt-4 flex items-start gap-3 text-sm leading-6 text-stone-600">
        <input type="checkbox" className="mt-1.5 accent-emerald-700" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
        This is my direct conversation with this parent. I understand local saving is not parent consent and does not activate AI memory.
      </label>
      <div className="mt-5 flex flex-wrap gap-3">
        <button className="portal-primary" disabled={busy || !owner || !acknowledged || !child || !parent || child === parent} onClick={() => void save()}>Save local preview</button>
        <button className="portal-secondary" disabled={busy} onClick={resetPreview}>Discard preview</button>
      </div>
      {demoRecipient && onDemoChange && <DemoBackgroundReview recipient={demoRecipient} onChange={onDemoChange} preview={preview} child={child} parent={parent} timezone={timezone} />}
    </section>}
    {demoRecipient && demoRecipient.background.length > 0 && <section className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5">
      <h3 className="font-bold">Active background{demoRecipient ? ` for ${demoRecipient.label}` : ""}</h3>
      <ul className="mt-3 space-y-3">{demoRecipient.background.map((item) => <li key={item.sourceIndex} className="text-sm">
        <p className="text-xs font-semibold text-emerald-900">{item.role === "parent" ? demoRecipient.label : "Demo child"} · {item.timestamp}</p>
        <p className="mt-1 whitespace-pre-wrap break-words">{item.text}</p>
      </li>)}</ul>
      <button className="portal-secondary mt-4" disabled={busy || demoRecipient.busy} onClick={() => void clearDemo()}>Remove demo background</button>
      <p className="mt-2 text-xs text-stone-500">Deleting a browser preview below does not remove this separately reviewed backend copy.</p>
    </section>}
    <section>
      <h3 className="mb-3 font-bold">Prepared conversations <span className="font-normal text-stone-400">({records.length})</span></h3>
      {!records.length && <p className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-stone-500">No saved background files for this recipient yet.</p>}
      <div className="space-y-3">{records.map((r) => <article key={r.id} className="flex items-start gap-3 rounded-2xl border border-stone-200 bg-white p-4">
        <FileText className="mt-1 h-5 w-5 shrink-0 text-emerald-800" />
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm font-semibold">{r.filename}</p>
          <p className="mt-1 text-xs text-stone-500">{r.preview.source} · {r.preview.messages.length} messages · Local only</p>
          <p className="mt-1 text-xs text-stone-500">Expires {new Date(r.expiresAt).toLocaleDateString()}. Expired content is removed when you next open this section.</p>
          {demoRecipient && <button className="mt-2 text-xs font-semibold text-emerald-800 underline" disabled={busy} onClick={() => reopen(r)}>Review for demo calls</button>}
        </div>
        <button aria-label={`Delete ${r.filename}`} className="rounded-lg p-2 text-stone-500 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50" disabled={busy} onClick={() => void remove(r.id)}><Trash2 className="h-4 w-4" /></button>
      </article>)}</div>
    </section>
  </div>;
}
