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
      className="min-h-[calc(100vh-96px)] overflow-hidden text-slate-950"
      style={{
        background:
          "radial-gradient(circle at 73% 29%, rgba(122, 114, 255, 0.24), transparent 34%), radial-gradient(circle at 56% 10%, rgba(191, 219, 254, 0.18), transparent 28%), radial-gradient(circle at 23% 80%, rgba(238, 242, 255, 0.9), transparent 35%), linear-gradient(180deg, #fbfcff 0%, #f8f9ff 55%, #ffffff 100%)",
      }}
    >
      <section className="relative mx-auto grid min-h-[660px] max-w-[1536px] items-center gap-10 px-6 pb-8 pt-[92px] sm:px-10 lg:grid-cols-[0.48fr_0.52fr] lg:px-[92px] lg:pb-8 lg:pt-[92px]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-indigo-100 to-transparent" />
        <div className="pointer-events-none absolute right-[-6%] top-[-8%] size-[820px] rounded-full bg-[radial-gradient(circle,rgba(120,112,255,0.18),rgba(255,255,255,0)_68%)] blur-sm" />
        <div className="pointer-events-none absolute right-[5.5%] top-[7%] hidden size-[690px] rounded-full border border-white/70 lg:block" />
        <div className="pointer-events-none absolute right-[10.5%] top-[14%] hidden size-[540px] rounded-full border border-white/75 lg:block" />
        <div className="pointer-events-none absolute right-[15.5%] top-[21%] hidden size-[405px] rounded-full border border-indigo-100/55 lg:block" />
        <div className="pointer-events-none absolute right-[11%] top-[12%] hidden size-4 rounded-full bg-indigo-200/80 lg:block" />
        <div className="pointer-events-none absolute right-[4.8%] top-[39%] hidden size-3.5 rounded-full bg-blue-200/80 lg:block" />
        <div className="pointer-events-none absolute right-[43%] top-[25%] hidden size-2 rounded-full bg-violet-300/70 lg:block" />
        <div className="pointer-events-none absolute right-[20%] top-[41%] hidden size-1.5 rounded-full bg-indigo-300/70 lg:block" />

        <div className="relative z-10 max-w-[690px] space-y-8 lg:pl-0">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100/80 bg-[#f2f0ff]/70 px-5 py-2.5 text-lg font-medium text-slate-800 shadow-[0_12px_40px_rgba(79,70,229,0.06)] backdrop-blur-xl max-sm:text-sm">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-7">
            <h1 className="max-w-[740px] text-5xl font-semibold leading-[1.1] tracking-[-0.045em] text-slate-900 sm:text-6xl lg:text-[76px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block whitespace-normal lg:whitespace-nowrap">
                <span className="bg-gradient-to-br from-blue-500 via-violet-500 to-indigo-600 bg-clip-text font-bold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[600px] whitespace-pre-line text-[22px] font-normal leading-[1.75] text-slate-500 max-sm:text-lg">
              {current.subtitle}
            </p>
          </div>

          <div className="flex flex-wrap gap-5">
            <Link
              href={startHref}
              className="inline-flex h-[62px] min-w-[170px] items-center justify-center gap-2 rounded-xl bg-slate-950 px-8 text-xl font-semibold text-white shadow-[0_18px_45px_rgba(15,23,42,0.16)] transition hover:-translate-y-0.5 hover:bg-slate-800 max-sm:h-12 max-sm:min-w-0 max-sm:text-base"
            >
              {current.start}
              <ArrowUpRight size={18} />
            </Link>
            <a
              href="#examples"
              className="inline-flex h-[62px] min-w-[190px] items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white/70 px-8 text-xl font-semibold text-slate-900 shadow-[0_10px_35px_rgba(15,23,42,0.06)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white/90 max-sm:h-12 max-sm:min-w-0 max-sm:text-base"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex justify-center lg:justify-end lg:pr-2">
          <div className="relative flex size-[230px] items-center justify-center sm:size-[380px] lg:size-[570px]">
            <div className="absolute inset-[-20%] rounded-full bg-[radial-gradient(circle,rgba(126,116,255,0.24)_0%,rgba(219,225,255,0.34)_38%,rgba(255,255,255,0)_70%)] blur-2xl" />
            <div className="absolute inset-0 rounded-full border border-white/75" />
            <div className="absolute inset-14 rounded-full border border-white/80" />
            <div className="absolute inset-28 hidden rounded-full border border-indigo-100/70 sm:block" />
            <div className="absolute -right-4 top-14 size-4 rounded-full bg-indigo-200/80 shadow-[0_0_24px_rgba(99,102,241,0.35)]" />
            <div className="absolute left-20 top-28 size-2 rounded-full bg-violet-300/80" />
            <div className="absolute bottom-32 right-6 size-3 rounded-full bg-blue-200/80" />
            <Image
              src="/logo-transparent.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 570px, (min-width: 640px) 380px, 230px"
              className="relative scale-[1.08] object-contain drop-shadow-[0_30px_58px_rgba(80,76,150,0.24)]"
              priority
            />
          </div>
        </div>
      </section>

      <section id="examples" className="mx-auto max-w-[1384px] px-6 pb-16 sm:px-10 lg:pb-24">
        <div className="grid gap-5 rounded-3xl border border-slate-200/80 bg-white/58 p-4 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:grid-cols-2 lg:grid-cols-4 lg:gap-0 lg:p-0">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="group flex items-center gap-6 rounded-2xl border border-white/70 bg-white/62 p-7 shadow-[0_14px_40px_rgba(15,23,42,0.045)] backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:bg-white/82 hover:shadow-[0_24px_70px_rgba(79,70,229,0.11)] lg:rounded-none lg:border-0 lg:border-r lg:border-slate-200/80 lg:shadow-none lg:last:border-r-0">
                <div className="grid size-[86px] shrink-0 place-items-center rounded-full bg-gradient-to-br from-indigo-50 via-white to-violet-50 text-indigo-600 shadow-inner transition group-hover:scale-105">
                  <Icon size={30} />
                </div>
                <div>
                  <h2 className="text-[22px] font-bold text-slate-950">{title}</h2>
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
