"use client";

import Image from "next/image";
import Link from "next/link";
import { Captions, Mic2, PlayCircle, Sparkles, Video, Zap } from "lucide-react";

import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    titlePrefix: "正在构建",
    titleAccent: "AI",
    titleSuffix: "内容创作的未来",
    subtitle: "Kaiqiang.ai 是一个专注于数字人、AI 视频生成与创作者工具的独立 AI 项目。",
    start: "立即开始",
    examples: "查看示例",
    badge: "AI 数字人口播视频创作平台",
    cards: [
      ["AI 数字人口播", "真实数字人口播视频", "一键生成"],
      ["AI 配音", "多种语音风格", "自然流畅"],
      ["自动字幕", "智能识别生成字幕", "支持多语言"],
      ["高效创作", "简单高效的创作流程", "节省时间成本"],
    ],
  },
  en: {
    titlePrefix: "Building the Future of",
    titleAccent: "AI",
    titleSuffix: "Content Creation",
    subtitle: "Kaiqiang.ai is an independent AI project focused on digital humans, AI video generation, and creator tools.",
    start: "Get Started",
    examples: "View Examples",
    badge: "AI Digital Human Video Creation Platform",
    cards: [
      ["Digital Human Videos", "Real digital human talking videos", "One-click generation"],
      ["AI Voiceover", "Multiple voice styles", "Natural and fluent"],
      ["Auto Captions", "Smart subtitle generation", "Multilingual support"],
      ["Efficient Creation", "A simpler creative workflow", "Save time and cost"],
    ],
  },
};

const icons = [Video, Mic2, Captions, Zap];

export function LandingPage({ startHref }: { startHref: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <main className="min-h-[calc(100vh-65px)] overflow-hidden bg-[#f8f9ff] text-slate-950">
      <section className="relative mx-auto grid min-h-[calc(100vh-65px)] max-w-[1440px] items-center gap-12 px-6 pb-12 pt-20 sm:px-10 lg:grid-cols-[0.86fr_1.14fr] lg:px-16 lg:pb-16 lg:pt-24">
        <div className="pointer-events-none absolute -right-24 top-0 size-[720px] rounded-full bg-[radial-gradient(circle,rgba(113,102,255,0.18),rgba(255,255,255,0)_68%)]" />
        <div className="pointer-events-none absolute right-10 top-14 hidden size-[560px] rounded-full border border-white/70 lg:block" />
        <div className="pointer-events-none absolute right-24 top-28 hidden size-[430px] rounded-full border border-white/80 lg:block" />

        <div className="relative z-10 space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white/75 px-4 py-2 text-sm font-medium text-slate-700 shadow-[0_12px_40px_rgba(79,70,229,0.08)] backdrop-blur">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-5">
            <h1 className="max-w-2xl text-5xl font-bold leading-[1.08] tracking-[-0.045em] text-slate-950 sm:text-6xl lg:text-[76px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block">
                <span className="bg-gradient-to-br from-blue-500 via-violet-500 to-indigo-600 bg-clip-text text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[560px] text-lg leading-9 text-slate-600 sm:text-xl">
              {current.subtitle}
            </p>
          </div>

          <div className="flex flex-wrap gap-5">
            <Link
              href={startHref}
              className="inline-flex h-14 items-center gap-2 rounded-xl bg-slate-950 px-8 text-base font-semibold text-white shadow-[0_18px_45px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              {current.start}
            </Link>
            <a
              href="#examples"
              className="inline-flex h-14 items-center gap-3 rounded-xl border border-slate-200 bg-white px-8 text-base font-semibold text-slate-900 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex justify-center lg:justify-end">
          <div className="relative flex size-[260px] items-center justify-center sm:size-[380px] lg:size-[560px]">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-white via-indigo-100 to-violet-100 shadow-[inset_0_0_60px_rgba(255,255,255,0.9),0_40px_110px_rgba(100,92,255,0.22)]" />
            <div className="absolute inset-10 rounded-full border border-white/80" />
            <div className="absolute -right-6 top-8 size-4 rounded-full bg-indigo-200" />
            <div className="absolute left-10 top-20 size-2 rounded-full bg-violet-300" />
            <div className="absolute bottom-24 right-2 size-3 rounded-full bg-blue-200" />
            <Image
              src="/logo.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 560px, (min-width: 640px) 380px, 260px"
              className="relative scale-110 object-contain drop-shadow-[0_28px_55px_rgba(80,76,150,0.22)]"
              priority
            />
          </div>
        </div>
      </section>

      <section id="examples" className="mx-auto max-w-[1320px] px-6 pb-16 sm:px-10 lg:pb-24">
        <div className="grid overflow-hidden rounded-3xl border border-slate-200 bg-white/80 shadow-[0_22px_70px_rgba(15,23,42,0.08)] backdrop-blur sm:grid-cols-2 lg:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="flex items-center gap-5 border-b border-slate-200 p-7 last:border-b-0 sm:odd:border-r lg:border-b-0 lg:border-r lg:last:border-r-0">
                <div className="grid size-20 shrink-0 place-items-center rounded-full bg-gradient-to-br from-indigo-50 to-white text-indigo-600 shadow-inner">
                  <Icon size={30} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-950">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{desc}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{current.cards[index][2]}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
