"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Clock3,
  Globe2,
  Heart,
  LockKeyhole,
  MessageCircleHeart,
  Mic2,
  PhoneCall,
  Plane,
  ShieldCheck,
  Sparkles,
  Upload,
  Volume2,
} from "lucide-react";

const steps = [
  {
    number: "01",
    eyebrow: "Teach the context",
    title: "Bring the family language",
    copy: "Choose a few WhatsApp memories or add family notes. HugBack learns the names, inside jokes and regional phrases that make a conversation feel like home—not like a script.",
    detail: "You review what is shared. Private family context stays separated for each parent.",
    icon: Upload,
    tint: "from-[#E5F2FF] to-[#F8FBFF]",
  },
  {
    number: "02",
    eyebrow: "Carry your voice",
    title: "Record two warm minutes",
    copy: "With your permission, a short voice sample captures your cadence, warmth and pitch. Your parent hears a familiar voice rather than a cold synthetic assistant.",
    detail: "Voice setup requires explicit recording and consent. You remain in control.",
    icon: Mic2,
    tint: "from-[#E9E2FF] to-[#F8F7FF]",
  },
  {
    number: "03",
    eyebrow: "Close the distance",
    title: "Check in—and stay in the loop",
    copy: "HugBack can hold a natural voice check-in at a familiar time. Afterwards, you receive a concise, non-clinical signal so you know whether today felt easy, tired or worth a real call.",
    detail: "No diagnosis. No secret surveillance. Just a gentle cue to help you show up.",
    icon: PhoneCall,
    tint: "from-[#E9E2FF] to-[#F2F8FF]",
  },
];

function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        node.dataset.visible = "true";
        observer.disconnect();
      }
    }, { threshold: 0.16 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return <div ref={ref} className={`landing-reveal ${className}`} style={{ transitionDelay: `${delay}ms` }}>{children}</div>;
}

function VoiceWave({ compact = false }: { compact?: boolean }) {
  const heights = [28, 48, 70, 42, 82, 58, 96, 62, 78, 44, 68, 34, 54, 26];
  return (
    <div className={`landing-wave ${compact ? "h-8" : "h-14"}`} aria-hidden="true">
      {heights.map((height, index) => <span key={index} style={{ height: `${height}%`, animationDelay: `${index * 70}ms` }} />)}
    </div>
  );
}

function BetaForm() {
  const [saved, setSaved] = useState(false);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    if (!email) return;
    window.localStorage.setItem("hugback.beta-interest.v1", email);
    setSaved(true);
  }

  return (
    <form onSubmit={submit} className="mt-8" aria-label="Early beta interest">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="sr-only" htmlFor="beta-email">Email address</label>
        <input id="beta-email" name="email" type="email" required placeholder="you@example.com" className="min-h-14 flex-1 rounded-full border border-white/25 bg-white/10 px-6 text-base text-white outline-none placeholder:text-white/50 focus:border-[#72B5FE] focus:ring-4 focus:ring-[#72B5FE]/15" />
        <button className="group min-h-14 rounded-full bg-[#72B5FE] px-7 font-bold text-[#1F253B] transition hover:-translate-y-0.5 hover:bg-[#A9D6FF]" type="submit">
          Request early access <ArrowRight className="ml-2 inline h-4 w-4 transition-transform group-hover:translate-x-1" />
        </button>
      </div>
      <p className="mt-3 text-xs leading-5 text-white/55" aria-live="polite">
        {saved ? "Saved on this device for the hackathon preview. No email was uploaded." : "Hackathon preview: your email stays on this device and is not uploaded."}
      </p>
    </form>
  );
}

export function LandingPage() {
  const [activeStep, setActiveStep] = useState(0);

  return (
    <main className="landing-shell overflow-hidden bg-[#F8F9FF] text-[#1F253B]">
      <nav className="fixed inset-x-0 top-0 z-50 border-b border-[#56619C]/10 bg-[#F8F9FF]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8">
          <Link href="/" className="flex items-center gap-3" aria-label="HugBack home">
            <Image src="/logo.png" width={727} height={343} priority alt="" className="h-9 w-[4.6rem] object-contain" />
            <Image src="/hugback.png" width={983} height={254} priority alt="HugBack AI" className="h-auto w-28" />
          </Link>
          <div className="hidden items-center gap-8 text-sm font-semibold text-[#56617F] md:flex">
            <a href="#why" className="transition hover:text-[#56619C]">Why HugBack</a>
            <a href="#how-it-works" className="transition hover:text-[#56619C]">How it works</a>
            <a href="#for-families" className="transition hover:text-[#56619C]">For families</a>
          </div>
          <Link href="/childportal" className="rounded-full bg-[#293052] px-5 py-3 text-sm font-bold text-white shadow-lg shadow-[#293052]/10 transition hover:-translate-y-0.5 hover:bg-[#404A7E]">
            Create your bridge
          </Link>
        </div>
      </nav>

      <section className="relative min-h-screen pt-28 sm:pt-32">
        <div className="landing-aurora landing-aurora-one" aria-hidden="true" />
        <div className="landing-aurora landing-aurora-two" aria-hidden="true" />
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 sm:px-8 lg:grid-cols-[0.92fr_1.08fr] lg:gap-16 lg:pb-28">
          <div className="relative z-10">
            <div className="landing-hero-enter inline-flex items-center gap-2 rounded-full border border-[#72B5FE]/30 bg-[#F2F8FF] px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-[#56619C]">
              <Heart className="h-4 w-4 fill-current" /> Distant, but still close
            </div>
            <h1 className="landing-hero-enter mt-7 max-w-3xl font-serif text-[clamp(3rem,7vw,6.4rem)] font-medium leading-[0.96] tracking-[-0.055em] text-[#1F253B]" style={{ animationDelay: "90ms" }}>
              When you’re oceans apart, the best sound is <span className="landing-script text-[#56619C]">your voice.</span>
            </h1>
            <p className="landing-hero-enter mt-7 max-w-xl text-lg leading-8 text-[#56617F] sm:text-xl" style={{ animationDelay: "170ms" }}>
              HugBack helps your parents hear you checking in—even when work, time zones and distance get in the way. Your voice, your family context, and a gentle update that brings you back into their day.
            </p>
            <div className="landing-hero-enter mt-9 flex flex-col gap-3 sm:flex-row" style={{ animationDelay: "240ms" }}>
              <Link href="/childportal" className="group inline-flex min-h-14 items-center justify-center rounded-full bg-[#56619C] px-7 font-bold text-white shadow-xl shadow-[#56619C]/20 transition hover:-translate-y-1 hover:bg-[#404A7E]">
                Create your voice bridge <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <a href="#how-it-works" className="inline-flex min-h-14 items-center justify-center rounded-full border border-[#414A67]/15 bg-white/80 px-7 font-bold text-[#2D344E] transition hover:-translate-y-1 hover:border-[#56619C]/40">
                <Volume2 className="mr-2 h-5 w-5 text-[#56619C]" /> See how it works
              </a>
            </div>
            <div className="landing-hero-enter mt-9 flex flex-wrap gap-x-6 gap-y-3 text-sm text-[#56617F]" style={{ animationDelay: "310ms" }}>
              <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#56619C]" /> Consent-led voice setup</span>
              <span className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-[#56619C]" /> Private family context</span>
            </div>
          </div>

          <div className="landing-hero-enter relative mx-auto w-full max-w-2xl lg:mx-0" style={{ animationDelay: "160ms" }}>
            <div className="relative overflow-hidden rounded-[2rem] border border-white/70 bg-white p-2 shadow-[0_35px_100px_rgba(68,48,35,0.18)] sm:rounded-[2.8rem]">
              <div className="relative aspect-[1.08/1] overflow-hidden rounded-[1.6rem] sm:rounded-[2.4rem]">
                <Image src="/hugback-family-hero.png" fill priority sizes="(max-width: 1024px) 100vw, 55vw" alt="A mother smiling while listening to a familiar voice at home" className="object-cover object-[64%_center]" />
                <div className="absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-t from-[#293052]/75 to-transparent" />
                <div className="absolute bottom-5 left-5 right-5 rounded-2xl border border-white/20 bg-[#293052]/75 p-4 text-white shadow-xl backdrop-blur-md sm:bottom-7 sm:left-7 sm:right-auto sm:w-80 sm:p-5">
                  <div className="flex items-center justify-between gap-4">
                    <div><p className="text-xs font-bold uppercase tracking-[0.17em] text-[#A9D6FF]">Tea-time check-in</p><p className="mt-1 font-serif text-xl">“Ma, chai ho gayi?”</p></div>
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#72B5FE] text-[#1F253B]"><Volume2 className="h-5 w-5" /></span>
                  </div>
                  <VoiceWave compact />
                </div>
              </div>
            </div>
            <div className="landing-float-card absolute -left-3 top-10 hidden w-52 rounded-2xl border border-white/75 bg-white/90 p-4 shadow-2xl backdrop-blur md:block">
              <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-[#E5F2FF] text-[#56619C]"><Plane className="h-5 w-5" /></span><div><p className="text-[10px] font-black uppercase tracking-[0.14em] text-[#737D9E]">8,000 km away</p><p className="text-sm font-bold">Singapore → Pune</p></div></div>
            </div>
            <div className="landing-float-card landing-float-delay absolute -right-3 -bottom-5 hidden w-60 rounded-2xl border border-white/75 bg-[#F2F8FF]/95 p-4 shadow-2xl backdrop-blur sm:block">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-[#56619C]">Today’s gentle signal</p>
              <p className="mt-2 text-sm font-bold text-[#2D344E]">Mum sounded cheerful and talked about the garden.</p>
              <p className="mt-2 text-[11px] text-[#737D9E]">AI-estimated · not medical advice</p>
            </div>
          </div>
        </div>
        <div className="mx-auto flex max-w-7xl items-center gap-5 border-t border-[#56619C]/10 px-5 py-6 text-xs font-bold uppercase tracking-[0.16em] text-[#737D9E] sm:px-8">
          <span>Built for families across distance</span><span className="h-px flex-1 bg-[#56619C]/10" /><span className="hidden sm:inline">Voice-first · real-time · consent-led</span>
        </div>
      </section>

      <section id="why" className="relative bg-[#293052] py-24 text-white sm:py-32">
        <div className="landing-night-grid absolute inset-0 opacity-50" aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
            <div><p className="text-xs font-black uppercase tracking-[0.2em] text-[#72B5FE]">The reality between two time zones</p><h2 className="mt-5 max-w-xl font-serif text-5xl leading-[1.02] tracking-[-0.035em] sm:text-6xl">The distance is hard. <span className="text-[#9BA5FC]">The guilt is harder.</span></h2></div>
            <p className="max-w-2xl text-lg leading-8 text-white/68">The call you meant to make slips past midnight. The five-minute time difference becomes five missed days. Back home, the phone stays quiet—and your parents say they are “fine” because they do not want to worry you.</p>
          </Reveal>
          <div className="mt-16 grid gap-px overflow-hidden rounded-[2rem] border border-white/10 bg-white/10 md:grid-cols-3">
            {[
              [Clock3, "Time zones don’t care", "Their relaxed evening lands in the middle of your workday."],
              [MessageCircleHeart, "Love becomes a pending task", "You remember at the wrong hour, then carry the guilt into tomorrow."],
              [Globe2, "Small moments disappear", "The knee feeling better. The new neighbour. What they made for tea."],
            ].map(([Icon, title, copy], index) => <Reveal key={String(title)} delay={index * 90} className="bg-[#293052]/90 p-7 sm:p-9"><Icon className="h-7 w-7 text-[#72B5FE]" /><h3 className="mt-8 font-serif text-2xl">{String(title)}</h3><p className="mt-3 leading-7 text-white/60">{String(copy)}</p></Reveal>)}
          </div>
          <Reveal className="mt-12 flex flex-col items-start justify-between gap-6 rounded-[2rem] border border-[#72B5FE]/25 bg-[#72B5FE]/10 p-7 sm:flex-row sm:items-center sm:p-9">
            <p className="max-w-3xl font-serif text-2xl leading-snug sm:text-3xl">HugBack does not try to replace your relationship. It helps your care arrive more often—and gives you a reason to make the next real call count.</p>
            <Heart className="h-12 w-12 shrink-0 fill-[#72B5FE] text-[#72B5FE]" />
          </Reveal>
        </div>
      </section>

      <section id="how-it-works" className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal className="mx-auto max-w-3xl text-center"><p className="text-xs font-black uppercase tracking-[0.2em] text-[#56619C]">One bridge. Three thoughtful steps.</p><h2 className="mt-5 font-serif text-5xl leading-tight tracking-[-0.04em] sm:text-6xl">From family memories to a familiar hello.</h2><p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-[#737D9E]">Every layer is designed to sound personal, stay bounded, and bring the child back into the loop.</p></Reveal>
          <div className="mt-14 grid gap-4 lg:grid-cols-3">
            {steps.map((step, index) => {
              const Icon = step.icon;
              const active = activeStep === index;
              return <Reveal key={step.number} delay={index * 90}><button type="button" onClick={() => setActiveStep(index)} className={`group relative min-h-[23rem] w-full overflow-hidden rounded-[2rem] border p-7 text-left transition duration-500 sm:p-9 ${active ? `border-[#56619C]/35 bg-gradient-to-br ${step.tint} shadow-[0_25px_70px_rgba(95,63,42,0.12)] lg:-translate-y-3` : "border-[#56619C]/10 bg-white hover:-translate-y-2 hover:shadow-xl"}`}>
                <div className="flex items-center justify-between"><span className="font-mono text-xs font-bold tracking-[0.2em] text-[#737D9E]">STEP {step.number}</span><span className={`grid h-12 w-12 place-items-center rounded-2xl transition ${active ? "bg-[#56619C] text-white" : "bg-[#F1F3FA] text-[#56619C]"}`}><Icon className="h-5 w-5" /></span></div>
                <p className="mt-12 text-xs font-black uppercase tracking-[0.17em] text-[#56619C]">{step.eyebrow}</p><h3 className="mt-3 font-serif text-3xl leading-tight">{step.title}</h3><p className="mt-5 leading-7 text-[#56617F]">{step.copy}</p>
                <div className={`mt-6 overflow-hidden border-t border-[#56619C]/10 pt-5 text-sm leading-6 text-[#56617F] transition-all ${active ? "max-h-28 opacity-100" : "max-h-0 border-transparent pt-0 opacity-0 lg:max-h-28 lg:border-[#56619C]/10 lg:pt-5 lg:opacity-100"}`}><Check className="mr-2 inline h-4 w-4 text-[#56619C]" />{step.detail}</div>
              </button></Reveal>;
            })}
          </div>
          <Reveal className="mt-16 grid overflow-hidden rounded-[2.25rem] border border-[#56619C]/10 bg-[#F2F8FF] lg:grid-cols-[1.05fr_0.95fr]">
            <div className="p-8 sm:p-12"><span className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-[#56619C]"><Sparkles className="h-4 w-4" /> The loop closes</span><h3 className="mt-7 font-serif text-4xl leading-tight sm:text-5xl">They hear your warmth. You hear what mattered.</h3><p className="mt-5 max-w-xl text-lg leading-8 text-[#56617F]">After a consented check-in, HugBack turns the conversation into a small, careful cue—not a transcript and never a diagnosis.</p></div>
            <div className="relative m-4 rounded-[1.7rem] bg-white p-6 shadow-sm sm:m-6 sm:p-8"><p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#56619C]">Today · Mum</p><div className="mt-6 flex gap-4"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#E9E2FF] text-[#56619C]"><Heart className="h-5 w-5 fill-current" /></span><div><p className="font-serif text-2xl leading-snug">Mum sounded bright today.</p><p className="mt-3 leading-7 text-[#56617F]">She said her knee felt a little better and laughed about making too much chai again.</p></div></div><div className="mt-7 flex flex-wrap gap-2 text-[11px] font-bold text-[#737D9E]"><span className="rounded-full bg-[#F1F3FA] px-3 py-1.5">AI-estimated</span><span className="rounded-full bg-[#F1F3FA] px-3 py-1.5">Shared with consent</span><span className="rounded-full bg-[#F1F3FA] px-3 py-1.5">Not medical advice</span></div></div>
          </Reveal>
        </div>
      </section>

      <section id="for-families" className="bg-[#F4F1FF] py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal className="grid gap-12 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
            <div className="relative"><div className="aspect-[4/3] overflow-hidden rounded-[2.5rem] border-8 border-white shadow-[0_30px_90px_rgba(81,60,45,0.16)]"><Image src="/hugback-family-hero.png" width={1776} height={888} alt="Illustrative story of a parent enjoying a familiar voice check-in" className="h-full w-full object-cover object-[68%_center]" /></div><div className="absolute -bottom-5 left-5 right-5 rounded-2xl bg-white/90 p-5 shadow-xl backdrop-blur sm:left-auto sm:right-7 sm:w-72"><p className="text-[10px] font-black uppercase tracking-[0.17em] text-[#56619C]">Illustrative family story</p><p className="mt-2 font-serif text-xl">Aarav in Singapore. Maa in Pune. Tea at 5:30.</p></div></div>
            <div className="lg:pl-8"><p className="text-xs font-black uppercase tracking-[0.2em] text-[#56619C]">A familiar rhythm, restored</p><blockquote className="mt-6 font-serif text-4xl leading-[1.18] tracking-[-0.03em] sm:text-5xl">“It feels like my child is in the next room, asking if I had my tea.”</blockquote><p className="mt-6 text-lg leading-8 text-[#56617F]">For this imagined family, HugBack knows Maa calls dinner “something light,” remembers the balcony tulsi plant, and speaks in the mix of English, Hindi and family shorthand that sounds like home.</p><div className="mt-8 border-l-2 border-[#9BA5FC] pl-5"><p className="font-bold">The goal is not more screen time.</p><p className="mt-1 text-[#56617F]">It is one more moment of warmth for them—and one more meaningful cue for you.</p></div></div>
          </Reveal>
        </div>
      </section>

      <section className="bg-[#F8F9FF] py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal className="grid gap-8 lg:grid-cols-3">
            <div className="lg:col-span-1"><p className="text-xs font-black uppercase tracking-[0.2em] text-[#56619C]">Technology with boundaries</p><h2 className="mt-5 font-serif text-4xl leading-tight">Warm enough for family. Clear enough for trust.</h2></div>
            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
              {[
                [ShieldCheck, "Always disclosed", "HugBack identifies itself as AI. A familiar voice should comfort—not deceive."],
                [LockKeyhole, "Consent comes first", "Voice creation, family context and wellbeing sharing require explicit choices."],
                [MessageCircleHeart, "Signals, not surveillance", "Children receive a bounded update, never raw private audio or hidden reasoning."],
                [Sparkles, "Built for natural conversation", "Gemini Live API and Google Cloud voice technology support responsive, voice-first check-ins."],
              ].map(([Icon, title, copy]) => <article key={String(title)} className="rounded-[1.7rem] border border-[#56619C]/10 bg-white p-6 shadow-sm"><Icon className="h-6 w-6 text-[#56619C]" /><h3 className="mt-5 text-lg font-bold">{String(title)}</h3><p className="mt-2 text-sm leading-6 text-[#56617F]">{String(copy)}</p></article>)}
            </div>
          </Reveal>
        </div>
      </section>

      <section className="px-5 pb-6 sm:px-8 sm:pb-8">
        <Reveal className="relative mx-auto max-w-7xl overflow-hidden rounded-[2.5rem] bg-[#293052] px-6 py-16 text-white sm:px-12 sm:py-20 lg:px-20">
          <div className="landing-night-grid absolute inset-0 opacity-40" aria-hidden="true" /><div className="landing-aurora landing-aurora-footer" aria-hidden="true" />
          <div className="relative grid gap-10 lg:grid-cols-[1fr_0.85fr] lg:items-end"><div><p className="text-xs font-black uppercase tracking-[0.2em] text-[#72B5FE]">Distant, but still close</p><h2 className="mt-5 max-w-3xl font-serif text-5xl leading-[1.02] tracking-[-0.04em] sm:text-6xl">Never let distance silence your bond.</h2><p className="mt-6 max-w-2xl text-lg leading-8 text-white/65">Give your parents the sound they miss. Give yourself a gentler way to stay present.</p></div><BetaForm /></div>
        </Reveal>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-10 text-sm text-[#737D9E] sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div className="flex items-center gap-3"><Image src="/logo.png" width={727} height={343} alt="" className="h-8 w-16 object-contain" /><span className="font-bold text-[#2D344E]">HugBack AI</span><span>· Distant, but still close.</span></div>
        <div className="flex gap-6"><Link href="/childportal" className="font-semibold hover:text-[#56619C]">Child portal</Link><a href="#how-it-works" className="font-semibold hover:text-[#56619C]">How it works</a></div>
      </footer>
    </main>
  );
}
