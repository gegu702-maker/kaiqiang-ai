"use client";

import { CheckCircle2, Mic2, PlayCircle, Sparkles, Video } from "lucide-react";
import Link from "next/link";

import { ViralAnalyzerClient } from "@/components/ViralAnalyzerClient";

const workflow = ["爆款链接", "AI拆解", "口播文案", "声音", "生成视频"];

export function StudioWorkspace() {
  return (
    <main className="min-h-[calc(100vh-86px)] w-full max-w-full overflow-x-hidden bg-ink text-slate-100">
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
        <section className="min-w-0 rounded-lg border border-white/10 bg-panel/85 p-5 shadow-glow">
          <p className="inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-sm font-semibold text-cyan">
            <Sparkles size={15} />
            AI 视频智能体工作台
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">AI 短视频工厂</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400 sm:text-base">
            粘贴爆款视频链接，AI 自动拆解、改写，并衔接声音与数字人口播视频生成。
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-5">
            {workflow.map((step, index) => (
              <div key={step} className="min-w-0 rounded-md border border-white/10 bg-white/[0.035] px-3 py-3">
                <p className="text-xs font-semibold text-cyan">0{index + 1}</p>
                <p className="mt-1 truncate text-sm font-semibold text-white">{step}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-6 grid w-full max-w-full grid-cols-1 gap-6 overflow-hidden xl:grid-cols-[minmax(0,1fr)_260px]">
          <section className="min-w-0 max-w-full overflow-hidden">
            <ViralAnalyzerClient variant="workspace" />
          </section>

          <aside className="min-w-0 max-w-full space-y-4 xl:w-[260px]">
            <section className="rounded-lg border border-white/10 bg-panel/80 p-4 shadow-glow">
              <h2 className="text-base font-semibold text-white">流程进度</h2>
              <div className="mt-4 space-y-3">
                {workflow.map((step, index) => (
                  <div key={step} className="flex min-w-0 items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-slate-300">
                    <CheckCircle2 size={17} className={index === 0 ? "text-cyan" : "text-slate-500"} />
                    <span className="min-w-0 truncate">{step}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-panel/80 p-4 shadow-glow">
              <h2 className="text-base font-semibold text-white">下一步</h2>
              <div className="mt-4 space-y-3 text-sm leading-6 text-slate-400">
                <p className="flex gap-2">
                  <PlayCircle className="mt-1 shrink-0 text-cyan" size={16} />
                  先确认一条口播文案，再进入数字人口播生成。
                </p>
                <p className="flex gap-2">
                  <Mic2 className="mt-1 shrink-0 text-cyan" size={16} />
                  可在生成页选择声音或使用默认声音。
                </p>
                <Link
                  href="/studio/avatar"
                  className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-cyan/30 px-3 text-sm font-semibold text-cyan hover:bg-cyan/10"
                >
                  <Video size={16} />
                  进入视频生成
                </Link>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
