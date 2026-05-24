"use client";

import Image from "next/image";
import Link from "next/link";
import { Captions, Mic2, PlayCircle, Sparkles, UserRound, Zap } from "lucide-react";

import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    title: "正在构建 AI 内容创作的未来",
    subtitle: "Kaiqiang.ai 是一个专注于数字人、AI 视频生成与创作者工具的独立 AI 项目。",
    start: "立即开始",
    examples: "查看示例",
    cards: [
      ["AI 数字人口播", "把商品信息转成数字人口播视频流程。"],
      ["AI 配音", "生成适合短视频的自然口播音频。"],
      ["自动字幕", "自动生成清晰、适合移动端观看的字幕。"],
      ["高效创作", "从脚本、配音到视频合成，减少重复工作。"],
    ],
  },
  en: {
    title: "Building the Future of AI Content Creation",
    subtitle: "Kaiqiang.ai is an independent AI project focused on digital humans, AI video generation, and creator tools.",
    start: "Get Started",
    examples: "View Examples",
    cards: [
      ["Digital Human Videos", "Turn product information into a digital human video workflow."],
      ["AI Voiceover", "Generate natural voiceovers for short-form videos."],
      ["Auto Captions", "Create clean captions designed for mobile viewing."],
      ["Efficient Creation", "Reduce repetitive work from script to final video."],
    ],
  },
};

const icons = [UserRound, Mic2, Captions, Zap];

export function LandingPage({ startHref }: { startHref: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <main className="min-h-[calc(100vh-65px)] bg-[#f7f7f4] text-neutral-950">
      <section className="mx-auto grid min-h-[calc(100vh-65px)] max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[0.92fr_1.08fr] lg:py-20">
        <div className="space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-2 text-sm text-neutral-600 shadow-sm">
            <Sparkles size={15} />
            KAIQIANG.AI
          </div>

          <div className="space-y-5">
            <h1 className="max-w-2xl text-5xl font-semibold leading-[1.02] tracking-[-0.03em] text-neutral-950 sm:text-6xl lg:text-7xl">
              {current.title}
            </h1>
            <p className="max-w-xl text-lg leading-8 text-neutral-600">
              {current.subtitle}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              href={startHref}
              className="inline-flex items-center gap-2 rounded-full bg-neutral-950 px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-800"
            >
              {current.start}
              <PlayCircle size={17} />
            </Link>
            <a
              href="#examples"
              className="inline-flex items-center rounded-full border border-neutral-300 bg-white px-6 py-3 text-sm font-medium text-neutral-800 transition hover:border-neutral-950"
            >
              {current.examples}
            </a>
          </div>
        </div>

        <div className="flex justify-center lg:justify-end">
          <div className="relative flex size-[220px] items-center justify-center sm:size-[320px] lg:size-[420px]">
            <div className="absolute inset-0 rounded-full bg-white blur-2xl" />
            <Image
              src="/logo.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 420px, (min-width: 640px) 320px, 220px"
              className="relative object-contain drop-shadow-[0_24px_60px_rgba(0,0,0,0.10)]"
              priority
            />
          </div>
        </div>
      </section>

      <section id="examples" className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:pb-24">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
                <Icon className="text-neutral-950" size={22} />
                <h2 className="mt-5 text-base font-semibold text-neutral-950">{title}</h2>
                <p className="mt-2 text-sm leading-6 text-neutral-600">{desc}</p>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
