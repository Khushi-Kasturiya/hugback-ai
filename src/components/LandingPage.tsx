"use client";

import Image from "next/image";
import Link from "next/link";
import { ReactNode, useEffect, useRef } from "react";
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
    title: "Share the context",
    copy: "Upload notes or chats so HugBack learns your family's inside jokes, making every check-in feel like home.",
    detail: "100% private",
    icon: Upload,
  },
  {
    number: "02",
    title: "Carry your voice",
    copy: "A short recording captures your warmth and tone, so they never hear a cold synthetic assistant.",
    detail: "Consent-led",
    icon: Mic2,
  },
  {
    number: "03",
    title: "Close the loop",
    copy: "After a gentle tea-time chat, a quick summary lets you know if today was cheerful, or if they need a real call.",
    detail: "Thoughtful update",
    icon: PhoneCall,
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

export function LandingPage() {
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
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 pb-16 sm:px-8 lg:grid-cols-[0.92fr_1.08fr] lg:gap-16 lg:pb-20">
          <div className="relative z-10">
            <div className="landing-hero-enter inline-flex items-center gap-2 rounded-full border border-[#72B5FE]/30 bg-[#F2F8FF] px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-[#56619C]">
              <Heart className="h-4 w-4 fill-current" /> Close to home, no matter where you roam
            </div>
            <h1 className="landing-hero-enter mt-7 max-w-2xl font-serif text-[clamp(2.25rem,3.8vw,3.75rem)] font-medium leading-[1.08] tracking-[-0.035em] text-[#1F253B]" style={{ animationDelay: "90ms" }}>
              When you’re oceans apart, the best sound is <span className="landing-script text-[#56619C]">your voice.</span>
            </h1>
            <p className="landing-hero-enter mt-7 max-w-xl text-lg leading-8 text-[#56617F] sm:text-xl" style={{ animationDelay: "170ms" }}>
              HugBack lets your parents hear you checking in every day, even when time zones, work, and life get in the way.
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
              <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#56619C]" /> One-time voice setup (Consent-led)</span>
              <span className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-[#56619C]" /> Learns your family's inside context</span>
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
              <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-[#E5F2FF] text-[#56619C]"><Plane className="h-5 w-5" /></span><div><p className="text-[10px] font-black uppercase tracking-[0.14em] text-[#737D9E]">6,600 km away</p><p className="text-sm font-bold">Singapore → Pune</p></div></div>
            </div>
            <div className="landing-float-card landing-float-delay absolute -right-3 -bottom-5 hidden w-60 rounded-2xl border border-white/75 bg-[#F2F8FF]/95 p-4 shadow-2xl backdrop-blur sm:block">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-[#56619C]">Today's check-in</p>
              <p className="mt-2 text-sm font-bold text-[#2D344E]">Mum sounded cheerful and talked about the garden.</p>
            </div>
          </div>
        </div>
        <div className="mx-auto flex max-w-7xl items-center gap-5 border-t border-[#56619C]/10 px-5 py-6 text-xs font-bold uppercase tracking-[0.16em] text-[#737D9E] sm:px-8">
          <span>Built for families across distance</span><span className="h-px flex-1 bg-[#56619C]/10" /><span className="hidden sm:inline">Voice-first · real-time · consent-led</span>
        </div>
      </section>

      <section id="why" className="relative overflow-hidden bg-gradient-to-br from-[#3F4E7C] via-[#4B5A8D] to-[#526493] py-24 text-white sm:py-32">
        <div className="landing-night-grid absolute inset-0 opacity-50" aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal>
            <div className="mx-auto text-center"><p className="text-xs font-black uppercase tracking-[0.2em] text-[#A9D6FF]">The reality today</p><h2 className="mt-5 font-serif text-5xl leading-[1.02] tracking-[-0.035em] sm:text-6xl">The distance is hard. <span className="text-[#C9CEFF]">The guilt is harder.</span></h2></div>
          </Reveal>
          <div className="mt-16 grid gap-px overflow-hidden rounded-[2rem] border border-[#D5D9FF]/60 bg-[#D5D9FF]/60 shadow-[0_22px_55px_-32px_rgba(22,29,68,0.65)] md:grid-cols-3">
            {[
              [Clock3, "Time zones don’t care", "Their relaxed evening lands in the middle of your workday."],
              [MessageCircleHeart, "Love becomes a pending task", "You remember at the wrong hour, then carry the guilt into tomorrow."],
              [Globe2, "Small moments disappear", "The knee feeling better. The new neighbour. What they made for tea."],
             ].map(([Icon, title, copy], index) => (
              <Reveal key={String(title)} delay={index * 90} className="bg-[#F1EFFF] p-7 sm:p-8">
                <div className="flex items-center gap-3">
                  <Icon className="h-6 w-6 shrink-0 text-[#56619C]" />
                  <h3 className="font-serif text-lg font-medium leading-snug text-[#1F2550] sm:text-xl">{String(title)}</h3>
                </div>
                <p className="mt-4 leading-7 text-[#56617F]">{String(copy)}</p>
              </Reveal>
            ))}
          </div>
          <Reveal className="mt-12 flex flex-col items-start justify-between gap-6 rounded-[2rem] border border-[#D5D9FF]/70 bg-gradient-to-r from-[#E9E2FF] to-[#E5F2FF] p-7 text-[#1F2550] shadow-[0_22px_55px_-34px_rgba(22,29,68,0.6)] sm:flex-row sm:items-center sm:p-9">
            <p className="font-serif text-2xl leading-snug sm:text-3xl">HugBack doesn’t replace your calls. It just bridges the gap between them.</p>
            <Heart className="h-12 w-12 shrink-0 fill-[#6F75C9] text-[#6F75C9]" />
          </Reveal>
        </div>
      </section>

      <section id="how-it-works" className="relative bg-[#FCFAFF] py-24 sm:py-32">
        <div aria-hidden="true" className="pointer-events-none absolute left-[-9rem] top-40 h-80 w-80 rounded-full bg-[#72B5FE]/10 blur-[90px]" />
        <div aria-hidden="true" className="pointer-events-none absolute right-[-8rem] top-16 h-96 w-96 rounded-full bg-[#B69CF2]/10 blur-[100px]" />
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal className="relative mx-auto text-center"><p className="text-xs font-black uppercase tracking-[0.2em] text-[#56619C]">One bridge. Three thoughtful steps.</p><h2 className="mt-5 font-serif text-5xl leading-tight tracking-[-0.04em] text-[#1F2550] sm:text-6xl">From family memories to a familiar hello.</h2><p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-600">A gentle journey from the moments you share to the voice they know by heart.</p></Reveal>

          <div className="relative mt-16">
            <div aria-hidden="true" className="pointer-events-none absolute left-[14%] right-[14%] top-[3.9rem] hidden items-center lg:flex">
              <span className="h-2 w-2 rounded-full bg-[#72B5FE] shadow-[0_0_18px_rgba(114,181,254,0.8)]" />
              <span className="h-px flex-1 bg-gradient-to-r from-[#72B5FE]/60 via-[#9BA5FC]/60 to-[#B69CF2]/60" />
              {[0, 1, 2, 3, 4].map((dot) => <span key={dot} className="mx-1 h-1.5 w-1.5 rounded-full bg-[#9BA5FC]/70" />)}
              <span className="h-px flex-1 bg-gradient-to-r from-[#B69CF2]/60 via-[#9BA5FC]/60 to-[#72B5FE]/60" />
              <span className="h-2 w-2 rounded-full bg-[#B69CF2] shadow-[0_0_18px_rgba(182,156,242,0.8)]" />
            </div>
            <MessageCircleHeart aria-hidden="true" className="absolute -left-4 top-36 hidden h-9 w-9 -rotate-12 text-[#9BA5FC]/25 xl:block" />
            <Heart aria-hidden="true" className="absolute -right-3 top-24 hidden h-8 w-8 rotate-12 fill-[#B69CF2]/15 text-[#B69CF2]/25 xl:block" />
            <div className="relative grid gap-5 lg:grid-cols-3">
            {steps.map((step, index) => {
              const Icon = step.icon;
              return <Reveal key={step.number} delay={index * 110} className="h-full"><article className="group relative flex h-full min-h-[20rem] flex-col overflow-hidden rounded-[2rem] border border-[#56619C]/10 bg-white p-7 shadow-[0_20px_60px_-15px_rgba(139,92,246,0.15)] transition duration-500 hover:-translate-y-2 hover:border-[#9BA5FC]/45 hover:shadow-[0_28px_70px_-18px_rgba(86,97,156,0.28)] sm:p-8">
                <div aria-hidden="true" className="absolute -right-20 -top-20 h-48 w-48 rounded-full bg-gradient-to-br from-[#72B5FE]/14 to-[#B69CF2]/16 blur-2xl transition duration-500 group-hover:scale-125" />
                <div className="relative flex items-center justify-between">
                  <span className="font-mono text-xs font-black tracking-[0.2em] text-[#56619C]">STEP {step.number}</span>
                  <span className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-[#E5F2FF] to-[#EEE7FF] text-[#56619C] shadow-[0_10px_30px_rgba(155,165,252,0.2)] transition duration-300 group-hover:rotate-3 group-hover:scale-105">
                    {index === 1 ? <div className="voice-bars flex h-7 items-center gap-0.5" aria-hidden="true">{[9, 17, 25, 14, 22, 11].map((height, bar) => <span key={bar} className="w-0.5 rounded-full bg-[#56619C]" style={{ height, animationDelay: `${bar * 90}ms` }} />)}</div> : <Icon className="h-6 w-6" />}
                  </span>
                </div>
                <h3 className="relative mt-2 font-serif text-3xl leading-tight text-[#1F2550]">{step.title}</h3>
                <p className="relative mt-5 leading-7 text-slate-600">{step.copy}</p>
                <div className="relative mt-auto"><span className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3.5 py-2 text-xs font-bold text-indigo-700"><Check className="h-3.5 w-3.5" />{step.detail}</span></div>
              </article></Reveal>;
            })}
            </div>
          </div>
        </div>
      </section>

      <section id="for-families" className="relative overflow-hidden bg-gradient-to-br from-[#455584] via-[#506193] to-[#465783] py-24 text-white sm:py-32">
        <div className="landing-night-grid absolute inset-0 opacity-40" aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal className="grid gap-12 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
            <div className="relative"><div className="aspect-[4/3] overflow-hidden rounded-[2.5rem] border-8 border-white/90 shadow-[0_30px_90px_rgba(12,18,50,0.35)]"><Image src="/hugback-japac-family-story.jpg" width={1448} height={1086} alt="An Indian mother in Pune smiling during a familiar voice check-in at tea time" className="h-full w-full object-cover object-center" /></div><div className="absolute -bottom-5 left-5 right-5 rounded-2xl bg-white/90 p-5 text-[#1F2550] shadow-xl backdrop-blur sm:left-auto sm:right-7 sm:w-72"><p className="text-[10px] font-black uppercase tracking-[0.17em] text-[#56619C]">THE SOUND OF HOME</p><p className="mt-2 font-serif text-md">A familiar voice when the house feels a little too quiet.</p></div></div>
            <div className="lg:pl-8"><p className="text-xs font-black uppercase tracking-[0.2em] text-[#72B5FE]">A familiar rhythm, restored</p><blockquote className="mt-6 font-serif text-4xl leading-[1.18] tracking-[-0.03em] sm:text-5xl">“It feels like my child is sitting right across from me, asking about my day.”</blockquote><p className="mt-6 text-lg leading-8 text-white/65">As parents age, they simply crave your voice. HugBack fills the quiet hours with your exact warmth and language. Whenever they miss you, they can reach out and hear you instantly.</p><div className="mt-8 border-l-2 border-[#72B5FE] pl-5"><p className="font-bold">The goal is connection, not screen time.</p><p className="mt-1 text-white/65">No confusing apps or tiny buttons to navigate. Just a simple, voice-first conversation whenever they want to hear you.</p></div></div>
          </Reveal>
        </div>
      </section>

      <section className="bg-[#F4F1FF] py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="grid gap-8 lg:grid-cols-[0.62fr_1.38fr] lg:items-center lg:gap-10">
            <Reveal><p className="text-[11px] font-black uppercase tracking-[0.2em] text-[#56619C]">Technology with boundaries</p><h2 className="mt-3 font-serif text-3xl leading-tight tracking-[-0.025em] text-[#1F2550] sm:text-4xl">Warm enough for family. Clear enough for trust.</h2></Reveal>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                [ShieldCheck, "AI disclosed, not impersonated", "Every call begins with HugBack identifying itself as AI. Even with a familiar voice, it never pretends to be the child."],
                [LockKeyhole, "Consent is specific, never assumed", "Voice creation, conversation memory, and daily updates each require explicit permission. The AI cannot enable them on its own."],
                [MessageCircleHeart, "Family conversations stay secure", "Each parent has their own separate memory history. You receive a gentle summary—never raw transcripts, private audio, or hidden data."],
                [Sparkles, "Uncertain means nothing is shared", "If an update is unclear, nothing is sent. And if a parent ever says “don’t share this,” HugBack instantly respects their privacy and clears the signal."],
              ].map(([Icon, title, copy], index) => <Reveal key={String(title)} delay={index * 90} className="h-full"><div className="group h-full rounded-[1.5rem] bg-[#DEE1EE] p-px transition duration-300 hover:-translate-y-1 hover:bg-gradient-to-r hover:from-[#72B5FE] hover:via-[#9BA5FC] hover:to-[#B69CF2] hover:shadow-[0_16px_40px_-20px_rgba(86,97,156,0.35)]"><article className="h-full rounded-[calc(1.5rem-1px)] bg-white p-5"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#E5F2FF] to-[#EEE7FF] text-[#56619C] transition duration-300 group-hover:scale-105"><Icon className="h-[18px] w-[18px]" /></span><div><h3 className="text-base font-bold leading-6 text-[#1F2550]">{String(title)}</h3><p className="mt-1.5 text-[13px] leading-5 text-slate-600">{String(copy)}</p></div></div></article></div></Reveal>)}
            </div>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-10 text-sm text-[#737D9E] sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div className="flex items-center gap-3"><Image src="/logo.png" width={727} height={343} alt="" className="h-8 w-16 object-contain" /><span className="font-bold text-[#2D344E]">HugBack AI</span><span>· Close to home, no matter where you roam.</span></div>
        <div className="flex gap-6"><Link href="/childportal" className="font-semibold hover:text-[#56619C]">Child portal</Link><a href="#how-it-works" className="font-semibold hover:text-[#56619C]">How it works</a></div>
      </footer>
    </main>
  );
}
