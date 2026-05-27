"use client";

import { ArrowRight, ImagePlus, Languages, Layers3, Mic2, ShieldCheck, UserRound } from "lucide-react";

import { HomeVideoAgentPreview } from "@/components/HomeVideoAgentPreview";
import { StudioNavigation } from "@/components/StudioNavigation";
import { TaskForm } from "@/components/TaskForm";
import { useLanguage } from "@/components/LanguageProvider";
import type { VoiceClone } from "@/lib/types";

const copy = {
  zh: {
    title: "AI 带货视频生成工作台",
    subtitle: "上传商品信息、图片和参考声音，自动生成脚本、配音、字幕和可下载视频。",
    language: "语言选择",
    storage: "Supabase Storage 自动返回素材和视频 URL",
    cards: [
      ["AI Agent", "卖点、标题、脚本自动拆解"],
      ["Storyboard", "生成可复制的镜头和视觉 prompt"],
      ["Video Factory", "TTS、字幕、FFmpeg 视频合成"],
    ],
    assets: [
      ["产品图", "jpg / png / webp"],
      ["形象素材", "真人或品牌人物"],
      ["参考语音", "mp3 / wav / m4a"],
    ],
  },
  en: {
    title: "AI Product Video Studio",
    subtitle: "Upload product information, images, and reference audio to generate scripts, voiceovers, subtitles, and downloadable videos.",
    language: "Language",
    storage: "Supabase Storage automatically returns asset and video URLs",
    cards: [
      ["AI Agent", "Automatically breaks down selling points, titles, and scripts"],
      ["Storyboard", "Generate reusable shots and visual prompts"],
      ["Video Factory", "TTS, subtitles, and FFmpeg video rendering"],
    ],
    assets: [
      ["Product Image", "jpg / png / webp"],
      ["Personal Avatar Asset", "person or brand character"],
      ["Reference Audio", "mp3 / wav / m4a"],
    ],
  },
};

type StudioWorkspaceProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  quotaLoadFailed?: boolean;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
  livePortraitEnabled?: boolean;
};

export function StudioWorkspace({ userEmail, remainingQuota, quotaLoadFailed = false, voiceCloneEnabled = false, voiceClones = [], livePortraitEnabled = false }: StudioWorkspaceProps) {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <main className="grid min-h-[calc(100vh-86px)] lg:grid-cols-[72px_1fr]">
      <StudioNavigation />
      <div className="mx-auto grid w-full max-w-[1500px] gap-5 px-4 py-5 sm:px-6 xl:grid-cols-[0.92fr_0.98fr_0.9fr] xl:py-6">
        <section className="space-y-4">
          <div className="inline-flex w-fit rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 text-sm text-cyan">
            AI Video Agent Studio
          </div>
          <h1 className="max-w-xl text-4xl font-semibold leading-[1.04] text-white sm:text-5xl xl:text-[48px]">
            {current.title}
          </h1>
          <p className="max-w-xl text-base leading-7 text-slate-300">{current.subtitle}</p>

          <div className="grid gap-3">
            {current.cards.map(([title, desc]) => (
              <div
                key={title}
                className="group rounded-lg border border-white/10 bg-white/[0.04] p-3 transition hover:-translate-y-0.5 hover:border-cyan/25 hover:bg-cyan/[0.06]"
              >
                <Layers3 className="mb-2 text-cyan transition group-hover:scale-110" size={17} />
                <h2 className="font-medium text-white">{title}</h2>
                <p className="mt-1 text-sm text-slate-400">{desc}</p>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-cyan/15 bg-cyan/[0.06] p-4">
            <label className="space-y-2">
              <span className="flex items-center gap-2 text-sm font-medium text-slate-200">
                <Languages size={15} /> {current.language}
              </span>
              <select
                required
                name="language"
                form="task-submit-form"
                className="h-10 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm outline-none ring-cyan/40 focus:ring-2"
                key={locale}
                defaultValue={locale}
              >
                <option value="zh">中文</option>
                <option value="en">English</option>
              </select>
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            {current.assets.map(([title, desc], index) => {
              const Icon = [ImagePlus, UserRound, Mic2][index];
              return (
                <div key={title} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <Icon className="mb-2 text-cyan" size={17} />
                  <p className="text-sm font-medium text-slate-100">{title}</p>
                  <p className="mt-1 text-xs text-slate-500">{desc}</p>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-3 text-sm text-slate-400">
            <ShieldCheck className="text-lime" size={18} />
            {current.storage}
            <ArrowRight size={16} />
          </div>
        </section>
        <section>
          <TaskForm
            userEmail={userEmail}
            remainingQuota={remainingQuota}
            quotaLoadFailed={quotaLoadFailed}
            voiceCloneEnabled={voiceCloneEnabled}
            voiceClones={voiceClones}
            livePortraitEnabled={livePortraitEnabled}
          />
        </section>
        <section>
          <HomeVideoAgentPreview />
        </section>
      </div>
    </main>
  );
}
