"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Check, Clapperboard, Film, Loader2, Scissors, Sparkles, Subtitles, UserRound, WandSparkles } from "lucide-react";

const scenes = [
  {
    time: "0-3s",
    title: "黄金开头",
    subtitle: "别急着买，先看这 3 点",
    platform: "Hook",
  },
  {
    time: "3-12s",
    title: "痛点场景",
    subtitle: "AI 正在匹配用户需求",
    platform: "即梦",
  },
  {
    time: "12-28s",
    title: "商品特写",
    subtitle: "镜头推进到核心卖点",
    platform: "可灵",
  },
  {
    time: "28-45s",
    title: "数字人口播",
    subtitle: "HeyGen 口播片段生成中",
    platform: "HeyGen",
  },
];

const workflow = [
  ["AI卖点分析", "done", Sparkles],
  ["AI脚本生成", "done", WandSparkles],
  ["AI分镜生成", "done", Film],
  ["视觉Prompt", "done", Clapperboard],
  ["数字人口播", "active", UserRound],
  ["视频剪辑", "next", Scissors],
  ["字幕合成", "next", Subtitles],
  ["视频导出", "next", Check],
];

export function HomeVideoAgentPreview() {
  const [activeScene, setActiveScene] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveScene((value) => (value + 1) % scenes.length);
    }, 2200);
    return () => window.clearInterval(timer);
  }, []);

  const scene = scenes[activeScene];

  return (
    <div className="space-y-4">
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-[#080c16]/95 p-4 shadow-glow">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(49,215,255,0.18),transparent_36%)]" />
        <div className="relative flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-cyan">AI Video Agent</p>
            <h2 className="mt-1 text-lg font-semibold text-white">实时导演预览</h2>
          </div>
          <div className="rounded-full border border-lime/25 bg-lime/10 px-3 py-1 text-xs text-lime">
            Rendering 68%
          </div>
        </div>

        <div className="relative mt-4 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="mx-auto w-full max-w-[230px]">
            <div className="relative aspect-[9/16] overflow-hidden rounded-[28px] border border-white/15 bg-black shadow-2xl">
              <motion.div
                key={activeScene}
                initial={{ opacity: 0, scale: 1.06, y: 12 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.55, ease: "easeOut" }}
                className="absolute inset-0"
              >
                <div className="absolute inset-0 bg-[linear-gradient(140deg,#07111d,#102332_42%,#18211d_70%,#05070c)]" />
                <div className="absolute left-5 right-5 top-6 h-28 rounded-2xl border border-cyan/25 bg-cyan/10 blur-[1px]" />
                <div className="absolute left-9 top-12 size-20 rounded-full border border-white/20 bg-white/10" />
                <div className="absolute bottom-28 left-4 right-4 rounded-2xl border border-white/15 bg-white/[0.08] p-3 backdrop-blur">
                  <p className="text-[10px] text-cyan">{scene.time} · {scene.platform}</p>
                  <p className="mt-1 text-sm font-semibold text-white">{scene.title}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-300">{scene.subtitle}</p>
                </div>
                <div className="absolute bottom-8 left-3 right-3 rounded-xl bg-black/65 px-3 py-2 text-center text-sm font-bold leading-5 text-white [text-shadow:_0_2px_0_rgb(0_0_0)]">
                  {scene.subtitle}
                </div>
              </motion.div>
              <div className="absolute left-1/2 top-3 h-1.5 w-16 -translate-x-1/2 rounded-full bg-white/20" />
            </div>
          </div>

          <div className="flex flex-col justify-between gap-4">
            <div className="grid gap-2">
              {workflow.map(([label, status, Icon]) => (
                <div key={String(label)} className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
                  <span
                    className={[
                      "grid size-7 place-items-center rounded-full border",
                      status === "done" ? "border-lime/35 bg-lime/15 text-lime" : "",
                      status === "active" ? "border-cyan/40 bg-cyan/15 text-cyan" : "",
                      status === "next" ? "border-white/10 bg-white/5 text-slate-500" : "",
                    ].join(" ")}
                  >
                    {status === "active" ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
                  </span>
                  <span className={status === "next" ? "text-sm text-slate-500" : "text-sm text-slate-200"}>{String(label)}</span>
                  {status === "active" ? <span className="ml-auto text-xs text-cyan">生成中</span> : null}
                </div>
              ))}
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
                <span>Scene Pipeline</span>
                <span>45s / 9:16</span>
              </div>
              <div className="flex gap-1.5">
                {scenes.map((item, index) => (
                  <button
                    key={item.time}
                    type="button"
                    onClick={() => setActiveScene(index)}
                    className={[
                      "h-12 flex-1 rounded-md border transition",
                      index === activeScene ? "border-cyan/50 bg-cyan/20" : "border-white/10 bg-white/[0.04] hover:bg-white/[0.08]",
                    ].join(" ")}
                  >
                    <span className="block text-[10px] text-slate-300">{item.time}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {["爆款标题", "封面Prompt", "剪映清单"].map((item, index) => (
          <motion.div
            key={item}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.08 }}
            className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-300 transition hover:-translate-y-0.5 hover:border-cyan/25 hover:bg-cyan/[0.06]"
          >
            <p className="font-medium text-white">{item}</p>
            <p className="mt-1 text-xs text-slate-500">AI Agent output</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
