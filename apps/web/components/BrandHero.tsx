"use client";

import Image from "next/image";
import { Sparkles } from "lucide-react";

import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    eyebrow: "Independent AI Studio",
    title: "正在构建 AI 内容创作的未来",
    subtitle: "Kaiqiang.ai 是一个专注于数字人、AI 视频生成与创作者工具的独立 AI 项目。",
  },
  en: {
    eyebrow: "Independent AI Studio",
    title: "Building the Future of AI Content Creation",
    subtitle: "Kaiqiang.ai is an independent AI project focused on digital humans, AI video generation, and creator tools.",
  },
};

export function BrandHero() {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <section className="space-y-5">
      <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-sm text-slate-300">
        <Sparkles size={15} />
        {current.eyebrow}
      </div>

      <div className="relative mx-auto flex size-[180px] items-center justify-center sm:size-[220px] xl:size-[340px]">
        <div className="absolute inset-0 rounded-full bg-white/[0.03] blur-3xl" />
        <Image
          src="/logo.png"
          alt="KAIQIANG.AI brand logo"
          fill
          sizes="(min-width: 1280px) 340px, (min-width: 640px) 220px, 180px"
          className="relative rounded-2xl object-contain"
          priority
        />
      </div>

      <div className="space-y-3">
        <h1 className="max-w-xl text-4xl font-semibold leading-[1.06] text-white sm:text-5xl xl:text-[48px]">
          {current.title}
        </h1>
        <p className="max-w-xl text-base leading-7 text-slate-300">
          {current.subtitle}
        </p>
      </div>
    </section>
  );
}
