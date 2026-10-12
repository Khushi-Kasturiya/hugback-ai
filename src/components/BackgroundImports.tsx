"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Upload } from "lucide-react";
import { MAX_IMPORT_BYTES, parseChat, ChatPreview } from "@/lib/chat-import";
import { listImports, saveImport } from "@/lib/portal-storage";
import { DemoFamily, DemoRecipient, demoRequest } from "@/lib/demo-api";

type RelationType = "mother" | "father" | "grandmother" | "grandfather" | "other";

const RELATION_OPTIONS: { value: RelationType; label: string}[] = [
  { value: "mother", label: "Mother" },
  { value: "father", label: "Father" },
  { value: "grandmother", label: "Grandmother" },
  { value: "grandfather", label: "Grandfather" },
  { value: "other", label: "Other" },
];

export function BackgroundImports({
  owner,
  demoRecipient,
  demoFamily,
  onDemoChange,
  onRecipientSelect,
}: {
  owner?: string;
  demoRecipient?: DemoRecipient;
  demoFamily?: DemoFamily;
  onDemoChange?: (family: DemoFamily) => void;
  onRecipientSelect?: (id: string) => void;
}) {
  const [relation, setRelation] = useState<RelationType>(demoRecipient?.relationship || "mother");
  const [label, setLabel] = useState(demoRecipient?.label);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [uploadedInfo, setUploadedInfo] = useState<{ filename: string; count: number } | null>(null);

  const fileInput = useRef<HTMLInputElement>(null);

  // Sync state if demoRecipient changes
  useEffect(() => {
    if (demoRecipient) {
      setRelation(demoRecipient.relationship || "mother");
      setLabel(demoRecipient.label);
      if (demoRecipient.background?.length > 0) {
        setUploadedInfo((prev) => prev || { filename: "Uploaded Chat", count: demoRecipient.background.length });
      }
    }
  }, [demoRecipient]);

  // Check existing local imports for initial uploaded status
  useEffect(() => {
    if (!owner) return;
    let current = true;
    void listImports(owner, demoRecipient?.recipientId, demoRecipient?.legacy).then((items) => {
      if (current && items.length > 0) {
        const latest = items[0];
        setUploadedInfo({
          filename: latest.filename,
          count: latest.preview.messages.length,
        });
      }
    });
    return () => { current = false; };
  }, [owner, demoRecipient?.recipientId, demoRecipient?.legacy]);

  function handleRelationChange(newRelation: RelationType) {
    setRelation(newRelation);
    setError("");
    setSuccessMessage("");
    const opt = RELATION_OPTIONS.find((o) => o.value === newRelation);
    const prevOpt = RELATION_OPTIONS.find((o) => o.value === relation);
    if (!label?.trim()) {
      setLabel(opt ? opt.label : "Other");
    }

    const existing = demoFamily?.recipients.find((r) => r.relationship === newRelation);
    if (existing) {
      setLabel(existing.label);
      onRecipientSelect?.(existing.recipientId);
    }
  }

  async function handleFileUpload(file?: File) {
    if (!file) return;
    setError("");
    setSuccessMessage("");
    setBusy(true);

    try {
      if (!/\.(txt|json)$/i.test(file.name)) {
        throw new Error("Please choose a chat export file (.txt or .json).");
      }
      if (file.size > MAX_IMPORT_BYTES) {
        throw new Error("The file must be smaller than 1 MB.");
      }

      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      
      let parsed: ChatPreview;
      const isJson = /\.json$/i.test(file.name) || text.trimStart().startsWith("{");
      if (isJson) {
        parsed = parseChat(text, "instagram");
      } else {
        try {
          parsed = parseChat(text, "whatsapp", "DMY");
        } catch (waErr) {
          try {
            parsed = parseChat(text, "whatsapp", "MDY");
          } catch {
            try {
              parsed = parseChat(text, "instagram");
            } catch {
              throw waErr;
            }
          }
        }
      }

      if (!parsed.messages.length) {
        throw new Error("No readable messages were found in this file.");
      }

      const activeLabel = label?.trim() || RELATION_OPTIONS.find((o) => o.value === relation)?.label || "Other";

      // 1. Ensure recipient exists on backend
      let currentRecipient = demoFamily?.recipients.find(
        (r) => r.recipientId === demoRecipient?.recipientId || r.label.toLowerCase() === activeLabel.toLowerCase()
      );

      if (!currentRecipient) {
        try {
          const updatedFamily = await demoRequest(demoFamily ? "/recipients" : "/family", "POST", {
            syntheticOnly: true,
            simulateChildConsent: true,
            simulateParentConsent: true,
            enableMemory: true,
            timeZone: "Asia/Kolkata",
            label: activeLabel,
            relationship: relation,
            enableWellbeingSharing: true,
            language: "auto",
          });
          onDemoChange?.(updatedFamily);
          currentRecipient = updatedFamily.recipients.find((r) => r.label === activeLabel) || updatedFamily.recipients.at(-1);
          if (currentRecipient) {
            onRecipientSelect?.(currentRecipient.recipientId);
          }
        } catch {
          // Continue with local save if backend is offline or rejected
        }
      }

      // 2. Save background excerpts to backend if participants exist
      if (currentRecipient && parsed.participants.length >= 2) {
        const childSender = parsed.participants[0];
        const parentSender = parsed.participants[1];
        const validExcerpts = parsed.messages
          .map((m, idx) => ({ ...m, sourceIndex: idx }))
          .filter((m) => [childSender, parentSender].includes(m.sender) && m.text.trim().length > 0 && m.text.length <= 500)
          .slice(0, 8);

        if (validExcerpts.length > 0) {
          try {
            const withBg = await demoRequest("/background", "PUT", {
              recipientId: currentRecipient.recipientId,
              revision: currentRecipient.revision,
              syntheticOnly: true,
              simulateChildConsent: true,
              simulateParentConsent: true,
              source: parsed.source,
              childSender,
              parentSender,
              timeZone: "Asia/Kolkata",
              excerpts: validExcerpts.map((e) => ({
                sourceIndex: e.sourceIndex,
                sender: e.sender,
                timestamp: e.timestamp,
                text: e.text,
              })),
            });
            onDemoChange?.(withBg);
          } catch {
            // Safe fallback if background sync fails
          }
        }
      }

      // 3. Save locally in portal storage
      if (owner) {
        const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${parsed.source}:DMY:${text}`));
        const fingerprint = Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, "0")).join("");
        await saveImport(owner, {
          recipientId: currentRecipient?.recipientId,
          filename: file.name,
          fingerprint,
          childSender: parsed.participants[0] || "Child",
          parentSender: parsed.participants[1] || activeLabel,
          timezone: "Asia/Kolkata",
          preview: parsed,
        });
      }

      setUploadedInfo({
        filename: file.name,
        count: parsed.messages.length,
      });
      setSuccessMessage(`Chat uploaded successfully for ${activeLabel}! (${parsed.messages.length} messages)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to read or upload chat file.");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2">
        {/* Relation selector with cleanly positioned chevron inside the container */}
        <div>
          <label htmlFor="relation-select" className="mb-2 block text-xs font-black uppercase tracking-wider text-[#56619C]">
            Relation
          </label>
          <div className="relative">
            <select
              id="relation-select"
              value={relation}
              disabled={busy}
              onChange={(e) => handleRelationChange(e.target.value as RelationType)}
              className="w-full appearance-none rounded-2xl border border-[#9BA5FC]/25 bg-white py-3.5 pl-4 pr-11 text-sm font-medium text-[#1F2550] shadow-sm outline-none transition focus:border-[#56619C] focus:ring-2 focus:ring-[#56619C]/15 disabled:opacity-50"
            >
              {RELATION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#56619C]/70" />
          </div>
        </div>

        {/* Label input */}
        <div>
          <label htmlFor="label-input" className="mb-2 block text-xs font-black uppercase tracking-wider text-[#56619C]">
            Label
          </label>
          <input
            id="label-input"
            type="text"
            value={label}
            maxLength={40}
            disabled={busy}
            onChange={(e) => {
              setLabel(e.target.value);
              setError("");
            }}
            placeholder="e.g. Mom, Papa"
            className="w-full rounded-2xl border border-[#9BA5FC]/25 bg-white px-4 py-3.5 text-sm font-medium text-[#1F2550] shadow-sm outline-none transition placeholder:text-stone-400 focus:border-[#56619C] focus:ring-2 focus:ring-[#56619C]/15 disabled:opacity-50"
          />
        </div>
      </div>

      {/* Upload chat */}
      <div>
        <label className="mb-2 block text-xs font-black uppercase tracking-wider text-[#56619C]">
          Upload Chat
        </label>

        {uploadedInfo ? (
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-emerald-200 bg-gradient-to-r from-emerald-50/80 to-[#EDF7FF]/80 p-5 shadow-sm">
            <div className="flex items-center gap-3.5">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-emerald-100 text-emerald-700">
                <Check className="h-5 w-5 stroke-[2.5]" />
              </span>
              <div>
                <p className="font-semibold text-emerald-950">{uploadedInfo.filename}</p>
                <p className="text-xs text-emerald-700">
                  {uploadedInfo.count} messages uploaded for {label || "family member"}
                </p>
              </div>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
              className="inline-flex items-center gap-2 rounded-xl border border-[#9BA5FC]/30 bg-white px-4 py-2 text-xs font-bold text-[#56619C] shadow-sm transition hover:bg-[#F8F9FF] hover:text-[#465181] disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload different chat
            </button>
          </div>
        ) : (
          <label className="group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[#9BA5FC]/30 bg-[#FCFAFF] px-6 py-9 text-center transition hover:-translate-y-0.5 hover:border-[#56619C] hover:bg-[#F3EFFF]/50 hover:shadow-md">
            <span className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-[#F1EFFF] text-[#56619C] transition group-hover:scale-105 group-hover:bg-[#E5F2FF]">
              <Upload className="h-6 w-6" />
            </span>
            <span className="font-bold text-[#1F2550]">Choose chat export</span>
            <span className="mt-1 text-xs text-[#737386]">WhatsApp, Instagram, or chat export file (.txt / .json up to 1 MB)</span>
            <input
              ref={fileInput}
              type="file"
              accept=".txt,.json"
              disabled={busy}
              className="hidden"
              onChange={(e) => void handleFileUpload(e.target.files?.[0])}
            />
          </label>
        )}
      </div>

      <input
        ref={fileInput}
        type="file"
        accept=".txt,.json"
        disabled={busy}
        className="hidden"
        onChange={(e) => void handleFileUpload(e.target.files?.[0])}
      />

      {busy && (
        <p role="status" className="flex items-center gap-2 text-xs font-semibold text-[#56619C]">
          <span className="inline-block h-2 w-2 animate-ping rounded-full bg-[#56619C]" />
          Processing chat...
        </p>
      )}

      {error && (
        <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800">
          {error}
        </p>
      )}

      {successMessage && !error && (
        <p role="status" className="rounded-xl bg-[#EDF7FF] p-4 text-xs font-semibold text-[#315F89]">
          {successMessage}
        </p>
      )}
    </div>
  );
}
