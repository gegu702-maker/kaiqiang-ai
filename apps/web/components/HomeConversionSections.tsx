"use client";

import Image from "next/image";
import { useActionState } from "react";
import { BriefcaseBusiness, CheckCircle2, ChevronDown, Clapperboard, Mail, Megaphone, PlayCircle, ShoppingBag, Sparkles, UsersRound } from "lucide-react";

import { joinWaitlistAction } from "@/app/actions/waitlist";
import { useLanguage } from "@/components/LanguageProvider";
import { customerCases, getFeaturedCases, type CaseLocale, type CustomerCase } from "@/lib/cases";

const initialWaitlistState = { ok: false, message: "" };

const copy = {
  zh: {
    demoEyebrow: "演示案例",
    demoTitle: "输入文案，\n生成真实 AI 数字人口播视频。",
    before: "真实演示",
    after: "产品介绍",
    placeholder: "真实案例生成中",
    previewSoon: "真实视频",
    examplesEyebrow: "案例展示",
    examplesTitle: "生产环境生成的真实案例视频",
    trustedTitle: "面向未来创作者",
    trustedBody: "为创作者、营销团队和企业提供真实数字人口播能力。",
    waitlistEyebrow: "抢先体验",
    waitlistTitle: "加入等待名单",
    waitlistBody: "告诉我们你的使用场景，优先获取新模板、案例和商业化功能。",
    email: "邮箱",
    industry: "行业",
    useCase: "使用场景",
    industryPlaceholder: "行业，例如电商 / 教育 / SaaS",
    useCasePlaceholder: "使用场景，例如产品介绍、课程视频、企业培训",
    submit: "加入等待名单",
    faqEyebrow: "FAQ",
    faqTitle: "常见问题",
    faq: [
      ["如何生成数字人视频？", "上传人物视频和音频后，系统会创建异步任务并生成口型同步的数字人口播视频。"],
      ["支持哪些格式？", "人物视频支持 mp4 / mov / webm，音频支持 wav / mp3 / m4a 等常见格式。"],
      ["免费额度是多少？", "当前 Free 套餐默认每月 3 次生成额度，适合先验证效果。"],
      ["视频生成需要多久？", "通常几分钟内完成，具体取决于素材时长、排队情况和 GPU 状态。"],
      ["是否支持商业用途？", "支持用于商业内容验证。请确保上传素材、肖像和音频拥有合法授权。"],
    ],
  },
  en: {
    demoEyebrow: "Hero Demo",
    demoTitle: "Enter a script,\ngenerate a real AI talking avatar video.",
    before: "Real Demo",
    after: "Product Demo",
    placeholder: "Real case generating",
    previewSoon: "Real video",
    examplesEyebrow: "Examples",
    examplesTitle: "Real production-generated customer examples",
    trustedTitle: "Trusted By Future Creators",
    trustedBody: "Built for creators, marketers, and businesses.",
    waitlistEyebrow: "Get Early Access",
    waitlistTitle: "Join the waitlist",
    waitlistBody: "Share your use case to get early access to new templates, demos, and commercial features.",
    email: "Email",
    industry: "Industry",
    useCase: "Use Case",
    industryPlaceholder: "Industry, e.g. e-commerce / education / SaaS",
    useCasePlaceholder: "Use case, e.g. product demos, course videos, training",
    submit: "Join waitlist",
    faqEyebrow: "FAQ",
    faqTitle: "Frequently Asked Questions",
    faq: [
      ["How do I generate an AI avatar video?", "Upload a person video and an audio file. Kaiqiang AI creates an async task and generates a lip-synced talking avatar video."],
      ["Which formats are supported?", "Person videos support mp4 / mov / webm, and audio supports common formats such as wav / mp3 / m4a."],
      ["How many free credits are included?", "The current Free plan includes 3 generations per month, designed for validating results first."],
      ["How long does generation take?", "Most videos complete within minutes, depending on media length, queue status, and GPU availability."],
      ["Can I use the videos commercially?", "Commercial validation is supported. Make sure you have proper rights for uploaded footage, likeness, and audio."],
    ],
  },
};

const exampleIcons = [Megaphone, Clapperboard, ShoppingBag, BriefcaseBusiness];

export function HomeConversionSections() {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <>
      <HeroDemoShowcase current={current} />
      <CustomerExamples current={current} />
      <TrustedByFutureCreators current={current} />
      <WaitlistForm current={current} locale={locale} />
      <HomeFAQ current={current} />
    </>
  );
}

function HeroDemoShowcase({ current }: { current: (typeof copy)["zh"] }) {
  const { locale } = useLanguage();
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
          <DemoVideo label={current.before} item={beforeCase} locale={locale} placeholder={current.placeholder} />
          <DemoVideo label={current.after} item={afterCase} locale={locale} placeholder={current.placeholder} />
        </div>
      </div>
    </section>
  );
}

function DemoVideo({ label, item, locale, placeholder }: { label: string; item: CustomerCase; locale: CaseLocale; placeholder: string }) {
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_14px_38px_rgba(15,23,42,0.06)]">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-950">{label}</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">{item.title[locale]}</p>
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

function CustomerExamples({ current }: { current: (typeof copy)["zh"] }) {
  const { locale } = useLanguage();

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
            const title = item.title[locale];
            const desc = item.description[locale];
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

function TrustedByFutureCreators({ current }: { current: (typeof copy)["zh"] }) {
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

function WaitlistForm({ current, locale }: { current: (typeof copy)["zh"]; locale: "zh" | "en" }) {
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

function HomeFAQ({ current }: { current: (typeof copy)["zh"] }) {
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
