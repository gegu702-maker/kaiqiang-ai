"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Captions, Database, Gauge, Mic2, MousePointerClick, PlayCircle, ShieldCheck, Sparkles, UserRoundCheck, Video, Zap } from "lucide-react";

import { useLanguage } from "@/components/LanguageProvider";
import { trackEvent } from "@/lib/analytics";

const copy = {
  zh: {
    titlePrefix: "正在构建",
    titleAccent: "AI",
    titleSuffix: "内容创作的未来",
    subtitle: "Kaiqiang.ai 专注于数字人、AI 视频生成与创作者工具，让 AI 内容创作更简单、更高效。",
    start: "立即开始",
    examples: "查看示例",
    badge: "AI 数字人口播视频创作平台",
    whyTitle: "为什么选择 Kaiqiang AI",
    whySubtitle: "围绕真实数字人口播生成流程打造，减少学习成本，让创作者更快得到可用成片。",
    cards: [
      ["AI 数字人口播", "真实数字人口播视频", "一键生成"],
      ["AI 配音", "多种语音风格", "自然流畅"],
      ["自动字幕", "智能识别生成字幕", "支持多语言"],
      ["高效创作", "简单高效的创作流程", "节省时间成本"],
    ],
    trust: [
      ["快速生成", "异步生成任务，清晰展示排队、生成和上传进度。"],
      ["真实数字人", "基于真实人物视频生成自然口型同步的 AI 数字人口播。"],
      ["安全存储", "生成素材和结果文件通过云端存储管理，访问更稳定。"],
      ["简单易用", "上传视频和音频即可开始，适合快速验证内容创意。"],
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
    whyTitle: "Why Kaiqiang AI",
    whySubtitle: "Built around a real avatar generation workflow so creators can move from upload to usable video with less friction.",
    cards: [
      ["Digital Human Videos", "Real digital human talking videos", "One-click generation"],
      ["AI Voiceover", "Multiple voice styles", "Natural and fluent"],
      ["Auto Captions", "Smart subtitle generation", "Multilingual support"],
      ["Efficient Creation", "A simpler creative workflow", "Save time and cost"],
    ],
    trust: [
      ["Fast Generation", "Async generation tasks with clear queue, render, and upload progress."],
      ["Real AI Avatar", "Create natural AI talking avatar videos from real person footage."],
      ["Secure Storage", "Uploaded assets and generated videos are managed with cloud storage."],
      ["Easy to Use", "Upload a video and audio file to quickly validate creative ideas."],
    ],
  },
};

const icons = [Video, Mic2, Captions, Zap];
const trustIcons = [Gauge, UserRoundCheck, ShieldCheck, MousePointerClick];

export function LandingPage({ startHref }: { startHref: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];

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
            <h1 className="max-w-[600px] text-5xl font-semibold leading-[1.12] tracking-[-0.045em] text-slate-900 sm:text-6xl lg:text-[60px]">
              <span className="block whitespace-nowrap">{current.titlePrefix}</span>
              <span className="block whitespace-nowrap">
                <span className="bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-500 bg-clip-text font-semibold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[500px] whitespace-pre-line text-lg font-normal leading-8 text-slate-500">
              {current.subtitle}
            </p>
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

      <section id="examples" className="mx-auto max-w-[1280px] px-6 pb-16 sm:px-10 lg:-mt-8 lg:pb-24">
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
