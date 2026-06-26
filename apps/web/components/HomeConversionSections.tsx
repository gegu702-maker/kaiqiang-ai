"use client";

import Image from "next/image";
import { useActionState } from "react";
import { BriefcaseBusiness, CheckCircle2, ChevronDown, Clapperboard, Mail, Megaphone, PlayCircle, ShoppingBag, Sparkles, UsersRound } from "lucide-react";

import { joinWaitlistAction } from "@/app/actions/waitlist";
import { useLanguage, type Locale } from "@/components/LanguageProvider";
import { customerCases, getFeaturedCases, type CustomerCase } from "@/lib/cases";
import { landingCopy } from "@/lib/i18n/landing";

const initialWaitlistState = { ok: false, message: "" };

const exampleIcons = [Megaphone, Clapperboard, ShoppingBag, BriefcaseBusiness];
type HomeConversionCopy = (typeof landingCopy)[Locale];

export function HomeConversionSections() {
  const { locale, selectedLocale } = useLanguage();
  const current = landingCopy[selectedLocale] ?? landingCopy.en;

  return (
    <>
      <HeroDemoShowcase current={current} selectedLocale={selectedLocale} />
      <CustomerExamples current={current} selectedLocale={selectedLocale} />
      <TrustedByFutureCreators current={current} />
      <WaitlistForm current={current} locale={locale} />
      <HomeFAQ current={current} />
    </>
  );
}

function HeroDemoShowcase({ current, selectedLocale }: { current: HomeConversionCopy; selectedLocale: Locale }) {
  const featuredCases = getFeaturedCases();
  const beforeCase = featuredCases[0] ?? customerCases[0];
  const afterCase = featuredCases[1] ?? customerCases[1] ?? beforeCase;

  return (
    <section className="mx-auto max-w-[1280px] px-6 py-16 sm:px-10 lg:py-20">
      <div className="grid gap-9 lg:grid-cols-[0.38fr_0.62fr] lg:items-center">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.demoEyebrow}</p>
          <h2 className="mt-4 whitespace-pre-line text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.demoTitle}</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <DemoVideo label={current.before} item={beforeCase} locale={selectedLocale} placeholder={current.placeholder} />
          <DemoVideo label={current.after} item={afterCase} locale={selectedLocale} placeholder={current.placeholder} />
        </div>
      </div>
    </section>
  );
}

function DemoVideo({ label, item, locale, placeholder }: { label: string; item: CustomerCase; locale: Locale; placeholder: string }) {
  const title = item.title[locale] ?? item.title.en;

  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_14px_38px_rgba(15,23,42,0.06)]">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-950">{label}</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">{title}</p>
        </div>
        <Sparkles size={16} className="text-indigo-500" />
      </div>
      <div className="relative aspect-video overflow-hidden bg-slate-950">
        <video className="h-full w-full object-cover" src={item.videoUrl || undefined} poster={item.thumbnailUrl} controls muted autoPlay loop playsInline />
        {!item.videoUrl ? <p className="absolute bottom-3 left-3 right-3 rounded-md bg-slate-950/72 px-3 py-2 text-xs leading-5 text-white backdrop-blur">{placeholder}</p> : null}
      </div>
    </article>
  );
}

function CustomerExamples({ current, selectedLocale }: { current: HomeConversionCopy; selectedLocale: Locale }) {
  return (
    <section id="examples" className="border-y border-slate-200/70 bg-white/68 px-6 py-16 sm:px-10 lg:py-20">
      <div className="mx-auto max-w-[1280px]">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.examplesEyebrow}</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.examplesTitle}</h2>
        </div>
        <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {customerCases.map((item, index) => {
            const Icon = exampleIcons[index];
            const title = item.title[selectedLocale] ?? item.title.en;
            const desc = item.description[selectedLocale] ?? item.description.en;
            return (
              <article key={title} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_14px_38px_rgba(15,23,42,0.05)]">
                <div className="relative aspect-video bg-slate-100">
                  <Image src={item.thumbnailUrl} alt={title} fill sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw" className="object-cover" />
                  <div className="absolute left-3 top-3 grid size-9 place-items-center rounded-lg bg-white/90 text-slate-950 shadow-sm backdrop-blur">
                    {Icon ? <Icon size={18} /> : <PlayCircle size={18} />}
                  </div>
                </div>
                <div className="p-5">
                  <h3 className="text-base font-semibold text-slate-950">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{desc}</p>
                  <div className="mt-4 overflow-hidden rounded-md border border-slate-200 bg-slate-950">
                    <div className="relative aspect-video">
                      {item.videoUrl ? (
                        <video className="h-full w-full object-cover" src={item.videoUrl} poster={item.thumbnailUrl} controls muted playsInline />
                      ) : (
                        <Image src={item.thumbnailUrl} alt={`${title} preview`} fill sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw" className="object-cover opacity-70" />
                      )}
                      <div className="absolute inset-0 grid place-items-center bg-slate-950/30 text-white">
                        <div className="flex items-center gap-2 rounded-full bg-slate-950/70 px-3 py-2 text-xs font-semibold backdrop-blur">
                          <PlayCircle size={15} />
                          {item.videoUrl ? item.category : current.previewSoon}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function TrustedByFutureCreators({ current }: { current: HomeConversionCopy }) {
  return (
    <section className="mx-auto max-w-[1280px] px-6 py-14 sm:px-10">
      <div className="grid gap-5 rounded-lg border border-slate-200 bg-slate-950 p-6 text-white shadow-[0_16px_44px_rgba(15,23,42,0.13)] sm:p-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div className="flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-lg bg-white/10">
            <UsersRound size={22} />
          </div>
          <h2 className="text-2xl font-semibold">{current.trustedTitle}</h2>
        </div>
        <p className="text-base leading-7 text-slate-300">{current.trustedBody}</p>
      </div>
    </section>
  );
}

function WaitlistForm({ current, locale }: { current: HomeConversionCopy; locale: "zh" | "en" }) {
  const [state, action] = useActionState(joinWaitlistAction, initialWaitlistState);

  return (
    <section id="contact" className="mx-auto max-w-[1280px] px-6 py-16 sm:px-10 lg:py-20">
      <div className="grid gap-8 rounded-lg border border-slate-200 bg-white p-6 shadow-[0_14px_38px_rgba(15,23,42,0.05)] sm:p-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-start">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.waitlistEyebrow}</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.waitlistTitle}</h2>
          <p className="mt-4 text-base leading-7 text-slate-500">{current.waitlistBody}</p>
        </div>
        <form action={action} className="grid gap-4">
          <input type="hidden" name="locale" value={locale} />
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            {current.email}
            <input name="email" type="email" required className="h-12 rounded-md border border-slate-200 bg-white px-3 text-slate-950 outline-none ring-indigo-200 focus:ring-2" placeholder="you@example.com" />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            {current.industry}
            <input name="industry" required className="h-12 rounded-md border border-slate-200 bg-white px-3 text-slate-950 outline-none ring-indigo-200 focus:ring-2" placeholder={current.industryPlaceholder} />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            {current.useCase}
            <textarea name="use_case" required className="min-h-28 rounded-md border border-slate-200 bg-white px-3 py-3 text-slate-950 outline-none ring-indigo-200 focus:ring-2" placeholder={current.useCasePlaceholder} />
          </label>
          {state.message ? (
            <p className={`flex items-center gap-2 text-sm ${state.ok ? "text-emerald-700" : "text-rose-600"}`}>
              {state.ok ? <CheckCircle2 size={16} /> : <Mail size={16} />}
              {state.message}
            </p>
          ) : null}
          <button type="submit" className="inline-flex h-12 items-center justify-center rounded-md bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800">
            {current.submit}
          </button>
        </form>
      </div>
    </section>
  );
}

function HomeFAQ({ current }: { current: HomeConversionCopy }) {
  return (
    <section className="border-t border-slate-200/70 bg-white/68 px-6 py-16 sm:px-10 lg:py-20">
      <div className="mx-auto max-w-[980px]">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.faqEyebrow}</p>
        <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.faqTitle}</h2>
        <div className="mt-8 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {current.faq.map(([question, answer]) => (
            <details key={question} className="group p-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-semibold text-slate-950">
                {question}
                <ChevronDown size={18} className="shrink-0 text-slate-400 transition group-open:rotate-180" />
              </summary>
              <p className="mt-3 text-sm leading-6 text-slate-500">{answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
