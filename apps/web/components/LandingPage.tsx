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
      className="min-h-[calc(100vh-80px)] overflow-hidden text-slate-950"
      style={{
        background:
          "radial-gradient(circle at 74% 25%, rgba(122, 114, 255, 0.13), transparent 40%), radial-gradient(circle at 58% 8%, rgba(191, 219, 254, 0.08), transparent 30%), radial-gradient(circle at 50% 84%, rgba(255, 255, 255, 0.96), transparent 44%), linear-gradient(180deg, #ffffff 0%, #fafbff 48%, #ffffff 100%)",
      }}
    >
      <section className="relative mx-auto grid min-h-[590px] max-w-[1536px] items-center gap-8 px-6 pb-2 pt-16 sm:px-10 lg:grid-cols-[0.46fr_0.54fr] lg:px-[92px] lg:pb-0 lg:pt-16">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-indigo-100 to-transparent" />
        <div className="pointer-events-none absolute right-[-12%] top-[-18%] size-[920px] rounded-full bg-[radial-gradient(circle,rgba(120,112,255,0.1),rgba(219,225,255,0.08)_42%,rgba(255,255,255,0)_72%)]" />
        <div className="pointer-events-none absolute right-[3%] top-[2%] hidden size-[740px] rounded-full border border-white/42 lg:block" />
        <div className="pointer-events-none absolute right-[10%] top-[12%] hidden size-[540px] rounded-full border border-indigo-100/35 lg:block" />
        <div className="pointer-events-none absolute right-[10%] top-[12%] hidden size-3 rounded-full bg-indigo-200/35 lg:block" />
        <div className="pointer-events-none absolute right-[44%] top-[25%] hidden size-1.5 rounded-full bg-violet-300/50 lg:block" />

        <div className="relative z-10 max-w-[650px] space-y-7 lg:-mt-7 lg:pl-0">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100/80 bg-[#f2f0ff]/70 px-5 py-2 text-base font-medium text-slate-800 shadow-[0_12px_40px_rgba(79,70,229,0.05)] backdrop-blur-xl max-sm:text-sm">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-6">
            <h1 className="max-w-[700px] text-5xl font-semibold leading-[1.14] tracking-[-0.043em] text-slate-900 sm:text-6xl lg:text-[68px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block whitespace-normal lg:whitespace-nowrap">
                <span className="bg-gradient-to-br from-blue-500 via-violet-500 to-indigo-600 bg-clip-text font-bold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[580px] whitespace-pre-line text-xl font-normal leading-[1.75] text-slate-500 max-sm:text-lg">
              {current.subtitle}
            </p>
          </div>

          <div className="flex flex-wrap gap-5 pt-1">
            <Link
              href={startHref}
              className="inline-flex h-14 min-w-[162px] items-center justify-center gap-2 rounded-xl bg-slate-950 px-7 text-lg font-semibold text-white shadow-[0_18px_45px_rgba(15,23,42,0.14)] transition hover:-translate-y-0.5 hover:bg-slate-800 max-sm:h-12 max-sm:min-w-0 max-sm:text-base"
            >
              {current.start}
              <ArrowUpRight size={18} />
            </Link>
            <a
              href="#examples"
              className="inline-flex h-14 min-w-[178px] items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white/70 px-7 text-lg font-semibold text-slate-900 shadow-[0_10px_35px_rgba(15,23,42,0.055)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white/90 max-sm:h-12 max-sm:min-w-0 max-sm:text-base"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex justify-center lg:justify-center lg:-ml-8 lg:pr-8">
          <div className="relative flex size-[220px] items-center justify-center sm:size-[350px] lg:size-[500px]">
            <div className="absolute inset-[-20%] rounded-full bg-[radial-gradient(circle,rgba(126,116,255,0.14)_0%,rgba(219,225,255,0.18)_38%,rgba(255,255,255,0)_72%)] blur-xl" />
            <div className="absolute inset-[-2%] rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.45)_0%,rgba(236,239,255,0.2)_42%,rgba(255,255,255,0)_68%)]" />
            <div className="absolute inset-0 rounded-full border border-white/42" />
            <div className="absolute inset-16 rounded-full border border-indigo-100/34" />
            <div className="absolute -right-3 top-12 size-3 rounded-full bg-indigo-200/38 shadow-[0_0_18px_rgba(99,102,241,0.18)]" />
            <div className="absolute bottom-28 right-6 size-2 rounded-full bg-blue-200/36" />
            <Image
              src="/logo-transparent.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 500px, (min-width: 640px) 350px, 220px"
              className="relative scale-[1.08] object-contain opacity-[0.92] drop-shadow-[0_26px_48px_rgba(80,76,150,0.18)]"
              priority
            />
          </div>
        </div>
      </section>

      <section id="examples" className="mx-auto -mt-4 max-w-[1384px] px-6 pb-14 sm:px-10 lg:-mt-7 lg:pb-20">
        <div className="grid gap-5 rounded-[28px] border border-slate-200/75 bg-white/62 p-4 shadow-[0_18px_58px_rgba(15,23,42,0.075)] backdrop-blur-xl sm:grid-cols-2 lg:gap-0 lg:p-0 min-[1180px]:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="group flex items-center gap-5 rounded-2xl border border-white/70 bg-white/62 p-6 shadow-[0_14px_40px_rgba(15,23,42,0.04)] backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:bg-white/82 hover:shadow-[0_24px_70px_rgba(79,70,229,0.1)] min-[1180px]:rounded-none min-[1180px]:border-0 min-[1180px]:border-r min-[1180px]:border-slate-200/80 min-[1180px]:shadow-none min-[1180px]:last:border-r-0">
                <div className="grid size-20 shrink-0 place-items-center rounded-full bg-gradient-to-br from-indigo-50 via-white to-violet-50 text-indigo-600 shadow-inner transition group-hover:scale-105">
                  <Icon size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-950">{title}</h2>
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
