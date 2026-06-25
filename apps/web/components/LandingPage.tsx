"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Captions, Database, Gauge, Mic2, MousePointerClick, PlayCircle, ShieldCheck, Sparkles, UserRoundCheck, Video, Zap } from "lucide-react";

import { HomeConversionSections } from "@/components/HomeConversionSections";
import { useLanguage } from "@/components/LanguageProvider";
import { trackEvent } from "@/lib/analytics";
import { landingCopy } from "@/lib/i18n/landing";

const icons = [Video, Mic2, Captions, Zap];
const trustIcons = [Gauge, UserRoundCheck, ShieldCheck, MousePointerClick];

export function LandingPage({ startHref }: { startHref: string }) {
  const { selectedLocale } = useLanguage();
  const current = landingCopy[selectedLocale] ?? landingCopy.en;

  return (
    <main
      className="min-h-screen overflow-hidden text-slate-950"
      style={{
        background:
          "radial-gradient(circle at 73% 38%, rgba(99,102,241,0.12), transparent 34%), radial-gradient(circle at 18% 12%, rgba(219,234,254,0.42), transparent 24%), linear-gradient(180deg, #ffffff 0%, #fbfcff 58%, #ffffff 100%)",
      }}
    >
      <section className="relative mx-auto grid min-h-[680px] max-w-[1440px] items-center gap-10 px-6 pb-10 pt-14 sm:px-10 lg:grid-cols-[0.42fr_0.58fr] lg:px-20 lg:pb-8 lg:pt-16">
        <div className="pointer-events-none absolute right-[-7%] top-[5%] hidden size-[760px] rounded-full border border-slate-200/35 lg:block" />
        <div className="pointer-events-none absolute right-[8%] top-[20%] hidden size-[500px] rounded-full border border-indigo-100/35 lg:block" />
        <div className="pointer-events-none absolute right-[32%] top-[17%] hidden size-1.5 rounded-full bg-indigo-200/60 lg:block" />

        <div className="relative z-20 max-w-[540px] space-y-8 lg:-mt-10 lg:min-w-[540px] lg:pl-0">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/72 px-4 py-2 text-sm font-medium text-slate-600 shadow-[0_8px_30px_rgba(15,23,42,0.035)] backdrop-blur-xl">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-6">
            <h1 className="max-w-[640px] text-4xl font-semibold leading-[1.12] text-slate-900 sm:text-6xl lg:text-[54px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block">
                <span className="bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-500 bg-clip-text font-semibold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[500px] whitespace-pre-line text-lg font-normal leading-8 text-slate-500">
              {current.subtitle}
            </p>
            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700">
              {current.flow.map((item, index) => (
                <div key={item} className="flex items-center gap-2">
                  <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 shadow-sm">{item}</span>
                  {index < current.flow.length - 1 ? <span className="text-slate-300">→</span> : null}
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-5 pt-1">
            <Link
              href={startHref}
              onClick={() => trackEvent("click_start_button", { source: "home_hero", href: startHref })}
              className="inline-flex h-13 min-w-[152px] items-center justify-center gap-2 rounded-full bg-slate-950 px-6 text-base font-semibold text-white shadow-[0_16px_38px_rgba(15,23,42,0.13)] transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              {current.start}
              <ArrowUpRight size={18} />
            </Link>
            <a
              href="#examples"
              onClick={() => trackEvent("click_view_demo", { source: "home_hero" })}
              className="inline-flex h-13 min-w-[162px] items-center justify-center gap-3 rounded-full border border-slate-200 bg-white/72 px-6 text-base font-semibold text-slate-900 shadow-[0_10px_30px_rgba(15,23,42,0.045)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex min-h-[360px] justify-center lg:min-h-[620px] lg:justify-end lg:overflow-visible">
          <div className="relative flex size-[260px] items-center justify-center sm:size-[420px] lg:size-[600px]">
            <div className="absolute inset-[-16%] rounded-full bg-[radial-gradient(circle,rgba(99,102,241,0.16)_0%,rgba(219,225,255,0.18)_36%,rgba(255,255,255,0)_70%)] blur-2xl" />
            <div className="absolute inset-[8%] rounded-full bg-white/32 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]" />
            <div className="absolute inset-[3%] rounded-full border border-white/70" />
            <div className="absolute inset-[18%] rounded-full border border-slate-200/55" />
            <Image
              src="/logo-transparent.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 600px, (min-width: 640px) 420px, 260px"
              className="relative scale-[1.02] object-contain opacity-[0.96] drop-shadow-[0_30px_52px_rgba(15,23,42,0.18)]"
              priority
            />
          </div>
        </div>
      </section>

      <HomeConversionSections />

      <section className="mx-auto max-w-[1280px] px-6 py-16 sm:px-10 lg:py-24">
        <div className="grid gap-4 sm:grid-cols-2 min-[1180px]:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="group rounded-lg border border-slate-200/65 bg-white/66 p-6 shadow-[0_12px_36px_rgba(15,23,42,0.04)] backdrop-blur-xl transition duration-300 hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white/86">
                <div className="grid size-12 place-items-center rounded-lg bg-slate-950 text-white shadow-[0_10px_24px_rgba(15,23,42,0.11)] transition group-hover:scale-[1.03]">
                  <Icon size={22} />
                </div>
                <div className="mt-6">
                  <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-500">{desc}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{current.cards[index][2]}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="border-y border-slate-200/70 bg-white/62 px-6 py-16 sm:px-10 lg:py-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="max-w-2xl">
            <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              <Database size={16} className="text-indigo-500" />
              {current.whyTitle}
            </p>
            <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.whyTitle}</p>
            <p className="mt-4 text-base leading-7 text-slate-500">{current.whySubtitle}</p>
          </div>
          <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {current.trust.map(([title, desc], index) => {
              const Icon = trustIcons[index];
              return (
                <article key={title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-[0_14px_36px_rgba(15,23,42,0.045)]">
                  <div className="grid size-11 place-items-center rounded-lg bg-slate-100 text-slate-900">
                    <Icon size={21} />
                  </div>
                  <h2 className="mt-5 text-lg font-semibold text-slate-950">{title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-500">{desc}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
