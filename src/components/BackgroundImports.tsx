"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, LockKeyhole, Trash2, Upload } from "lucide-react";
import { ChatPreview, MAX_IMPORT_BYTES, parseChat } from "@/lib/chat-import";
import { BackgroundImport, listImports, removeImport, saveImport } from "@/lib/portal-storage";
import { DemoBackgroundReview } from "@/components/DemoBackgroundReview";
import { DemoFamily, DemoRecipient, demoRequest } from "@/lib/demo-api";

export function BackgroundImports({ owner, demoRecipient, onDemoChange }: {
  owner?: string; demoRecipient?: DemoRecipient; onDemoChange?: (family: DemoFamily) => void;
}) {
  const [preview, setPreview] = useState<ChatPreview | null>(null);
  const [filename, setFilename] = useState("");
  const [fingerprint, setFingerprint] = useState("");
  const [child, setChild] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [records, setRecords] = useState<BackgroundImport[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const operation = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const timezone = "Asia/Kolkata";
  const parent = preview?.participants.find((participant) => participant !== child) || "";

  useEffect(() => {
    let current = true;
    if (owner) void listImports(owner, demoRecipient?.recipientId, demoRecipient?.legacy).then((items) => { if (current) setRecords(items); })
      .catch(() => { if (current) setError("Local background storage is unavailable."); });
    return () => { current = false; operation.current++; };
  }, [owner, demoRecipient?.recipientId, demoRecipient?.legacy]);

  function resetPreview() {
    operation.current++;
    setBusy(false); setPreview(null); setFingerprint(""); setChild("");
    setAcknowledged(false); setError(""); setMessage("");
    if (fileInput.current) fileInput.current.value = "";
  }

  async function previewText(text: string, name: string, sequence: number) {
    const parsed = parseChat(text, "whatsapp", "DMY");
    const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`whatsapp:DMY:${text}`));
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
      if (!/\.txt$/i.test(file.name)) throw new Error("Choose a WhatsApp .txt export without media.");
      if (file.size > MAX_IMPORT_BYTES) throw new Error("Choose a file smaller than 1 MB.");
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      await previewText(text, file.name, sequence);
    } catch (err) {
      if (sequence === operation.current) setError(err instanceof Error ? err.message : "The file could not be read.");
    } finally { if (sequence === operation.current) setBusy(false); }
  }

  async function save() {
    if (!owner || !preview || !acknowledged) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await saveImport(owner, { recipientId: demoRecipient?.recipientId, filename, fingerprint, childSender: child, parentSender: parent, timezone, preview });
      setRecords(await listImports(owner, demoRecipient?.recipientId, demoRecipient?.legacy));
      setMessage(demoRecipient
        ? `Saved on this browser for seven days. Use Prepare ${demoRecipient.label}'s background below to add bounded call context from the conversation.`
        : "Saved on this browser for seven days. Not uploaded, extracted by AI, or used in calls.");
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
    setPreview(record.preview); setFilename(record.filename); setFingerprint(record.fingerprint);
    setChild(record.childSender);
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
      <h2 className="font-serif text-3xl tracking-tight text-[#252D49]">{demoRecipient ? `The language you share with ${demoRecipient.label}` : "A little family context goes a long way."}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">Add a conversation so HugBack can recognise the names, phrases and ordinary details that make your relationship sound like home.</p>
    </div>
    <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
      <LockKeyhole className="mt-1 h-4 w-4 shrink-0" />
      <p><strong>{demoRecipient ? "Synthetic demo context." : "Local preview only."}</strong> {demoRecipient ? "Files are parsed in this browser. After the simulated permissions below, one action prepares up to 24 parent-authored excerpts spread across the full conversation for the selected recipient. The complete chat is not sent into calls or stored on the demo backend. Real family uploads remain inactive." : "Files stay on this browser. Real-family AI extraction and use during calls are not connected yet and require both participants’ verified consent. Avoid secrets and unrelated conversations."}</p>
    </div>
    <section className="rounded-[1.75rem] border border-[#9BA5FC]/20 bg-white/85 p-5 shadow-[0_16px_36px_rgba(86,97,156,0.1)] backdrop-blur sm:p-6">
      <label className="flex cursor-pointer flex-col items-center rounded-2xl border-2 border-dashed border-[#9BA5FC]/40 bg-[#F8F9FF] px-5 py-8 text-center transition-all duration-300 hover:-translate-y-0.5 hover:border-[#56619C] hover:bg-[#F2F8FF] hover:shadow-md">
        <span className="mb-3 rounded-xl bg-[#E5F2FF] p-3 text-[#56619C]"><Upload className="h-6 w-6" /></span>
        <span className="font-semibold">Choose a family conversation</span>
        <span className="mt-1 text-xs leading-5 text-stone-500">WhatsApp .txt export · Up to 1 MB</span>
        <input ref={fileInput} type="file" className="mt-4 block max-w-full text-xs file:mr-3 file:rounded-lg file:border-0 file:bg-stone-200 file:px-3 file:py-2"
          aria-label="Conversation file" accept=".txt" disabled={busy} onChange={(e) => void readFile(e.target.files?.[0])} />
      </label>
    </section>
    {busy && <p role="status" className="text-sm text-stone-600">Working locally…</p>}
    {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {message && <p role="status" className="rounded-xl bg-[#EDF7FF] p-4 text-sm text-[#315F89]">{message}</p>}
    {preview && <section className="dashboard-enter rounded-[1.75rem] border border-[#9BA5FC]/20 bg-white/85 p-5 shadow-[0_16px_36px_rgba(86,97,156,0.1)] backdrop-blur sm:p-6">
      <h3 className="font-bold">Review before saving</h3>
      <p className="mt-1 break-words text-xs text-stone-500">{filename} · {preview.messages.length} text messages · {preview.skipped} system/media entries skipped</p>
      <div className="mt-4 max-w-md">
        <label className="portal-label">Which name is yours?
          <select className="portal-input" value={child} onChange={(e) => setChild(e.target.value)}>
            <option value="">Choose your name</option>{preview.participants.map((p) => <option key={p}>{p}</option>)}
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
        <input type="checkbox" className="mt-1.5 accent-[#56619C]" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
        This is my direct conversation with this parent. I understand local saving is not parent consent and does not activate AI memory.
      </label>
      <div className="mt-5 flex flex-wrap gap-3">
        <button className="portal-primary" disabled={busy || !owner || !acknowledged || !child || !parent || child === parent} onClick={() => void save()}>Save browser copy (not call context)</button>
        <button className="portal-secondary" disabled={busy} onClick={resetPreview}>Discard preview</button>
      </div>
      {demoRecipient && onDemoChange && <DemoBackgroundReview recipient={demoRecipient} onChange={onDemoChange} preview={preview} child={child} parent={parent} timezone={timezone} />}
    </section>}
    {demoRecipient && demoRecipient.background.length > 0 && <section className="rounded-2xl border border-[#9BA5FC]/30 bg-[#F2F8FF] p-5">
      <h3 className="font-bold">Active background{demoRecipient ? ` for ${demoRecipient.label}` : ""}</h3>
      <ul className="mt-3 space-y-3">{demoRecipient.background.map((item) => <li key={item.sourceIndex} className="text-sm">
        <p className="text-xs font-semibold text-[#56619C]">{item.role === "parent" ? demoRecipient.label : "Demo child"} · {item.timestamp}</p>
        <p className="mt-1 whitespace-pre-wrap break-words">{item.text}</p>
      </li>)}</ul>
      <button className="portal-secondary mt-4" disabled={busy || demoRecipient.busy} onClick={() => void clearDemo()}>Remove demo background</button>
      <p className="mt-2 text-xs text-stone-500">Deleting a browser preview below does not remove this separately reviewed backend copy.</p>
    </section>}
    <section>
      <h3 className="mb-3 font-bold">Prepared conversations <span className="font-normal text-stone-400">({records.length})</span></h3>
      {!records.length && <p className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-stone-500">No saved background files for this recipient yet.</p>}
      <div className="space-y-3">{records.map((r) => <article key={r.id} className="flex items-start gap-3 rounded-2xl border border-[#9BA5FC]/20 bg-white/85 p-4 shadow-sm transition duration-300 hover:-translate-y-0.5 hover:border-[#9BA5FC] hover:shadow-md">
        <FileText className="mt-1 h-5 w-5 shrink-0 text-[#56619C]" />
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm font-semibold">{r.filename}</p>
          <p className="mt-1 text-xs text-stone-500">{r.preview.source} · {r.preview.messages.length} messages · Local only</p>
          <p className="mt-1 text-xs text-stone-500">Expires {new Date(r.expiresAt).toLocaleDateString()}. Expired content is removed when you next open this section.</p>
          {demoRecipient && <button className="mt-2 text-xs font-semibold text-[#56619C] underline" disabled={busy} onClick={() => reopen(r)}>Prepare for demo calls</button>}
        </div>
        <button aria-label={`Delete ${r.filename}`} className="rounded-lg p-2 text-stone-500 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50" disabled={busy} onClick={() => void remove(r.id)}><Trash2 className="h-4 w-4" /></button>
      </article>)}</div>
    </section>
  </div>;
}
