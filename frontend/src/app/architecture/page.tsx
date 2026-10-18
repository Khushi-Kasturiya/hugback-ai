"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity, ArrowLeft, Bot, CheckCircle2, Cloud, Database,
  FileLock2, Gauge, LockKeyhole, Mic2, ShieldCheck, Workflow,
} from "lucide-react";
import { ArchitectureManifest, architectureGet } from "@/lib/portal-api";

const stageIcons = [Workflow, Mic2, Database, Gauge];

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export default function ArchitecturePage() {
  const [manifest, setManifest] = useState<ArchitectureManifest>();
  const [error, setError] = useState("");

  useEffect(() => {
    architectureGet().then(setManifest).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Architecture status is unavailable.");
    });
  }, []);

  return (
    <main className="min-h-screen bg-[#F7F8FE] text-[#202641]">
      <header className="border-b border-[#56619C]/10 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-bold text-[#56619C]">
            <ArrowLeft className="h-4 w-4" /> Back to HugBack
          </Link>
          <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-black uppercase tracking-[0.14em] text-emerald-700">
            Google Cloud architecture
          </span>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <div className="max-w-4xl">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-[#56619C]">Technical architecture</p>
          <h1 className="mt-4 font-serif text-5xl leading-tight tracking-[-0.04em] sm:text-6xl">
            Probabilistic intelligence. Deterministic trust.
          </h1>
          <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-600">
            {manifest?.principle || "HugBack keeps identity, consent and persistence outside model authority."}
          </p>
        </div>

        {error && <div className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900">{error}</div>}

        <div className="mt-12 grid gap-4 md:grid-cols-5">
          {[
            [Cloud, "Identity", "Firebase Auth"],
            [Activity, "Compute", "Cloud Run"],
            [Bot, "Conversation", "Gemini Live"],
            [Database, "State", "Cloud Firestore"],
            [FileLock2, "Originals", "Cloud Storage"],
          ].map(([Icon, title, copy]) => (
            <article key={String(title)} className="rounded-3xl border border-[#56619C]/10 bg-white p-5 shadow-sm">
              <Icon className="h-6 w-6 text-[#56619C]" />
              <p className="mt-5 text-xs font-black uppercase tracking-[0.15em] text-slate-400">{String(title)}</p>
              <p className="mt-1 font-bold">{String(copy)}</p>
            </article>
          ))}
        </div>

        <section className="mt-14 rounded-[2rem] bg-[#293052] p-6 text-white sm:p-9">
          <div className="flex items-center gap-3">
            <Workflow className="h-6 w-6 text-[#A9D6FF]" />
            <h2 className="font-serif text-3xl">Four-stage agentic workflow</h2>
          </div>
          <div className="mt-8 grid gap-4 lg:grid-cols-4">
            {(manifest?.stages || [
              { name: "planner", when: "before_call", authority: "advisory", output: "bounded plan" },
              { name: "live", when: "during_call", authority: "speaking_agent", output: "real-time conversation" },
              { name: "reconciler", when: "after_call", authority: "proposal_only", output: "evidence-linked memory" },
              { name: "critic", when: "after_commit", authority: "advisory", output: "quality findings" },
            ]).map((stage, index) => {
              const Icon = stageIcons[index] || Bot;
              return (
                <article key={stage.name} className="relative rounded-2xl border border-white/15 bg-white/8 p-5">
                  <div className="flex items-center justify-between">
                    <Icon className="h-5 w-5 text-[#A9D6FF]" />
                    <span className="text-xs font-bold text-white/45">0{index + 1}</span>
                  </div>
                  <h3 className="mt-5 text-xl font-bold">{label(stage.name)}</h3>
                  <p className="mt-1 text-xs font-black uppercase tracking-[0.12em] text-[#A9D6FF]">{label(stage.when)}</p>
                  <p className="mt-4 text-sm leading-6 text-white/65">{stage.output}</p>
                  <p className="mt-3 text-xs text-white/45">Authority: {label(stage.authority)}</p>
                </article>
              );
            })}
          </div>
        </section>

        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          <section className="rounded-[2rem] border border-[#56619C]/10 bg-white p-7 sm:p-8">
            <div className="flex items-center gap-3"><ShieldCheck className="h-6 w-6 text-emerald-600" /><h2 className="font-serif text-3xl">Commit firewall</h2></div>
            <p className="mt-3 leading-7 text-slate-600">A model response cannot directly grant permission or write family state.</p>
            <div className="mt-6 space-y-3">
              {(manifest?.trustControls || []).map((control, index) => (
                <div key={control} className="flex items-center gap-3 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-950">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  <span>{index + 1}. {label(control)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-[2rem] border border-[#56619C]/10 bg-white p-7 sm:p-8">
            <div className="flex items-center gap-3"><LockKeyhole className="h-6 w-6 text-[#56619C]" /><h2 className="font-serif text-3xl">Storage boundaries</h2></div>
            <p className="mt-3 leading-7 text-slate-600">Firestore is canonical. Local stores exist only where uploading would weaken privacy or leak a provider secret.</p>
            <div className="mt-6 space-y-4">
              {(manifest?.storageBoundaries || []).map((boundary) => (
                <article key={boundary.store} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-bold">{label(boundary.store)}</p>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-[#56619C]">scoped</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-slate-700">{boundary.data}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{boundary.reason}</p>
                </article>
              ))}
            </div>
          </section>
        </div>

        {manifest && (
          <section className="mt-14 rounded-[2rem] border border-[#56619C]/10 bg-gradient-to-r from-[#EAF5FF] to-[#EFEAFF] p-7 sm:p-9">
            <h2 className="font-serif text-3xl">Selected runtime</h2>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(manifest.runtime).map(([key, value]) => (
                <div key={key} className="rounded-2xl bg-white/80 p-4">
                  <p className="text-xs font-black uppercase tracking-wider text-slate-400">{label(key)}</p>
                  <p className="mt-1 font-bold text-[#293052]">{label(value)}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
