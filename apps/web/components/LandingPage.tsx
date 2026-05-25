"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Captions, Mic2, PlayCircle, Sparkles, Video, Zap } from "lucide-react";

import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    titlePrefix: "正在构建",
    titleAccent: "AI",
    titleSuffix: "内容创作的未来",
    subtitle: "Kaiqiang.ai 专注于数字人、AI 视频生成与创作者工具，让 AI 内容创作更简单、更高效。",
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
    <main
      className="min-h-[calc(100vh-76px)] overflow-hidden text-slate-950"
      style={{
        background:
          "radial-gradient(circle at 72% 28%, rgba(99,102,241,0.09), transparent 36%), radial-gradient(circle at 15% 14%, rgba(191,219,254,0.08), transparent 28%), linear-gradient(180deg, #ffffff 0%, #fbfcff 58%, #ffffff 100%)",
      }}
    >
      <section className="relative mx-auto grid min-h-[620px] max-w-[1440px] items-center gap-10 px-6 pb-8 pt-16 sm:px-10 lg:grid-cols-[0.47fr_0.53fr] lg:px-20 lg:pb-10 lg:pt-20">
        <div className="pointer-events-none absolute right-[-8%] top-[4%] hidden size-[660px] rounded-full border border-slate-200/40 lg:block" />
        <div className="pointer-events-none absolute right-[10%] top-[18%] hidden size-[420px] rounded-full border border-indigo-100/40 lg:block" />
        <div className="pointer-events-none absolute right-[12%] top-[16%] hidden size-2 rounded-full bg-indigo-200/45 lg:block" />

        <div className="relative z-10 max-w-[650px] space-y-7 lg:-mt-5 lg:pl-0">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/72 px-4 py-2 text-sm font-medium text-slate-600 shadow-[0_8px_30px_rgba(15,23,42,0.04)] backdrop-blur-xl">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-6">
            <h1 className="max-w-[720px] text-5xl font-semibold leading-[1.08] tracking-[-0.045em] text-slate-950 sm:text-6xl lg:text-[72px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block whitespace-normal lg:whitespace-nowrap">
                <span className="bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-500 bg-clip-text font-semibold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[560px] whitespace-pre-line text-lg font-normal leading-8 text-slate-500 sm:text-xl">
              {current.subtitle}
            </p>
          </div>

          <div className="flex flex-wrap gap-5 pt-1">
            <Link
              href={startHref}
              className="inline-flex h-13 min-w-[152px] items-center justify-center gap-2 rounded-full bg-slate-950 px-6 text-base font-semibold text-white shadow-[0_16px_38px_rgba(15,23,42,0.13)] transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              {current.start}
              <ArrowUpRight size={18} />
            </Link>
            <a
              href="#examples"
              className="inline-flex h-13 min-w-[162px] items-center justify-center gap-3 rounded-full border border-slate-200 bg-white/72 px-6 text-base font-semibold text-slate-900 shadow-[0_10px_30px_rgba(15,23,42,0.045)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex justify-center lg:justify-center lg:-ml-4">
          <div className="relative flex size-[220px] items-center justify-center sm:size-[360px] lg:size-[500px]">
            <div className="absolute inset-[-16%] rounded-full bg-[radial-gradient(circle,rgba(99,102,241,0.11)_0%,rgba(219,225,255,0.14)_42%,rgba(255,255,255,0)_70%)] blur-xl" />
            <div className="absolute inset-8 rounded-full bg-white/28" />
            <Image
              src="/logo-transparent.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 500px, (min-width: 640px) 350px, 220px"
              className="relative scale-[1.04] object-contain opacity-[0.94] drop-shadow-[0_24px_42px_rgba(15,23,42,0.16)]"
              priority
            />
          </div>
        </div>
      </section>

      <section id="examples" className="mx-auto max-w-[1280px] px-6 pb-16 sm:px-10 lg:-mt-4 lg:pb-24">
        <div className="grid gap-4 sm:grid-cols-2 min-[1180px]:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="group rounded-3xl border border-slate-200/70 bg-white/72 p-6 shadow-[0_14px_42px_rgba(15,23,42,0.045)] backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:border-slate-300 hover:bg-white">
                <div className="grid size-12 place-items-center rounded-2xl bg-slate-950 text-white shadow-[0_10px_24px_rgba(15,23,42,0.12)] transition group-hover:scale-105">
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
    </main>
  );
}
