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
      className="min-h-[calc(100vh-65px)] overflow-hidden text-slate-950"
      style={{
        background:
          "radial-gradient(circle at 78% 28%, rgba(125, 111, 255, 0.24), transparent 34%), radial-gradient(circle at 58% 8%, rgba(147, 197, 253, 0.18), transparent 30%), radial-gradient(circle at 16% 74%, rgba(199, 210, 254, 0.22), transparent 26%), linear-gradient(180deg, #fbfcff 0%, #f7f8ff 52%, #ffffff 100%)",
      }}
    >
      <section className="relative mx-auto grid min-h-[calc(100vh-65px)] max-w-[1440px] items-center gap-14 px-6 pb-14 pt-20 sm:px-10 lg:grid-cols-[0.45fr_0.55fr] lg:px-16 lg:pb-20 lg:pt-24">
        <div className="pointer-events-none absolute left-6 top-16 h-px w-48 bg-gradient-to-r from-transparent via-indigo-200 to-transparent" />
        <div className="pointer-events-none absolute right-0 top-0 size-[760px] rounded-full bg-[radial-gradient(circle,rgba(108,99,255,0.16),rgba(255,255,255,0)_66%)] blur-sm" />
        <div className="pointer-events-none absolute right-12 top-20 hidden size-[620px] rounded-full border border-white/70 lg:block" />
        <div className="pointer-events-none absolute right-28 top-36 hidden size-[460px] rounded-full border border-white/80 lg:block" />
        <div className="pointer-events-none absolute right-52 top-52 hidden size-[300px] rounded-full border border-indigo-100/50 lg:block" />
        <div className="pointer-events-none absolute right-[12%] top-[18%] hidden size-2 rounded-full bg-indigo-300/60 lg:block" />
        <div className="pointer-events-none absolute right-[7%] top-[42%] hidden size-3 rounded-full bg-blue-200/80 lg:block" />
        <div className="pointer-events-none absolute right-[42%] top-[31%] hidden size-1.5 rounded-full bg-violet-300/70 lg:block" />

        <div className="relative z-10 max-w-[620px] space-y-9 lg:pl-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100/80 bg-white/60 px-4 py-2 text-sm font-medium text-slate-700 shadow-[0_12px_40px_rgba(79,70,229,0.07)] backdrop-blur-xl">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-6">
            <h1 className="max-w-[620px] text-5xl font-semibold leading-[1.08] tracking-[-0.045em] text-slate-900 sm:text-6xl lg:text-[74px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block">
                <span className="bg-gradient-to-br from-blue-500 via-violet-500 to-indigo-600 bg-clip-text font-bold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[560px] text-lg font-normal leading-9 text-slate-500 sm:text-xl">
              {current.subtitle}
            </p>
          </div>

          <div className="flex flex-wrap gap-5">
            <Link
              href={startHref}
              className="inline-flex h-13 items-center gap-2 rounded-xl bg-slate-950 px-7 py-4 text-base font-semibold text-white shadow-[0_18px_45px_rgba(15,23,42,0.16)] transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              {current.start}
              <ArrowUpRight size={18} />
            </Link>
            <a
              href="#examples"
              className="inline-flex h-13 items-center gap-3 rounded-xl border border-white/70 bg-white/55 px-7 py-4 text-base font-semibold text-slate-900 shadow-[0_10px_35px_rgba(15,23,42,0.06)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white/80"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex justify-center lg:justify-end lg:pr-4">
          <div className="relative flex size-[230px] items-center justify-center sm:size-[360px] lg:size-[520px]">
            <div className="absolute inset-[-18%] rounded-full bg-[radial-gradient(circle,rgba(126,116,255,0.24)_0%,rgba(219,225,255,0.32)_38%,rgba(255,255,255,0)_70%)] blur-xl" />
            <div className="absolute inset-0 rounded-full border border-white/75" />
            <div className="absolute inset-12 rounded-full border border-white/80" />
            <div className="absolute inset-24 hidden rounded-full border border-indigo-100/70 sm:block" />
            <div className="absolute -right-3 top-10 size-4 rounded-full bg-indigo-200/80 shadow-[0_0_24px_rgba(99,102,241,0.35)]" />
            <div className="absolute left-12 top-24 size-2 rounded-full bg-violet-300/80" />
            <div className="absolute bottom-28 right-4 size-3 rounded-full bg-blue-200/80" />
            <Image
              src="/logo-transparent.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 520px, (min-width: 640px) 360px, 230px"
              className="relative scale-110 object-contain drop-shadow-[0_28px_55px_rgba(80,76,150,0.22)]"
              priority
            />
          </div>
        </div>
      </section>

      <section id="examples" className="mx-auto max-w-[1320px] px-6 pb-16 sm:px-10 lg:pb-24">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="group rounded-3xl border border-white/70 bg-white/60 p-7 shadow-[0_18px_50px_rgba(15,23,42,0.07)] backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:bg-white/78 hover:shadow-[0_24px_70px_rgba(79,70,229,0.12)]">
                <div className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-indigo-50 via-white to-violet-50 text-indigo-600 shadow-inner transition group-hover:scale-105">
                  <Icon size={30} />
                </div>
                <div className="mt-6">
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
