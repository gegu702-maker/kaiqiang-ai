"use client";

import { ArrowRight, CheckCircle2, Clapperboard, Copy, ExternalLink, FileText, Loader2, Play, Sparkles, Video } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";
import { resolveVideoLink } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { VideoLinkResolveResult } from "@/lib/types";

type StepState = "idle" | "running" | "done";

const workflowSteps = [
  "正在识别抖音链接",
  "正在展开短链接",
  "正在读取视频信息",
  "解析成功 / 需要手动补充文案",
  "等待 ASR 转写",
  "等待爆点拆解",
  "等待生成数字人",
  "等待导出视频",
];

const rewrites = [
  ["版本A", "别只盯着表面的爆款数据，真正能复制的是它背后的开头、痛点和转化节奏。先抓住用户最在意的问题，再给出一个具体解决路径。"],
  ["版本B", "很多视频火起来，不是因为文案更长，而是前三秒就把矛盾讲清楚了。你要做的不是照搬，而是复用它的结构。"],
  ["版本C", "如果你也想做同类型内容，先别急着拍。把爆款拆成钩子、痛点、卖点和行动号召，再换成你的产品场景。"],
  ["老板IP版", "我做内容这么久，最大的感受是：爆款不是凭感觉来的，而是有结构、有节奏、有成交路径的。"],
  ["知识分享版", "一个短视频能不能留住人，关键看它有没有在开头提出一个强问题，并在后面持续给出答案。"],
  ["成交版", "如果你正在找更稳定的短视频转化方式，先从拆解爆款开始，把有效结构变成自己的原创表达。"],
  ["故事版", "之前我也以为爆款靠灵感，后来才发现，真正厉害的内容都在重复一套可复用的叙事结构。"],
  ["直播版", "家人们，今天不讲空话，直接拆一个爆款为什么能火，以及你怎么把它变成自己的口播脚本。"],
];

const copy = {
  zh: {
    badge: "AI Video Agent Studio",
    title: "AI 短视频生产工厂",
    subtitle: "粘贴爆款链接，AI 自动拆解、仿写并生成数字人口播视频。",
    placeholder: "粘贴爆款视频链接，AI自动拆解并生成原创口播",
    analyze: "开始分析",
    analyzing: "分析中",
    supports: "支持 抖音 / TikTok / YouTube Shorts",
    fallback: "当前抖音链接暂时无法自动解析，请粘贴视频文案或上传视频继续分析。",
    login: "请先登录后再分析爆款链接。",
    status: "Agent 执行状态",
    preview: "实时预览",
    metadata: "链接解析结果",
    topic: "视频主题",
    hook: "黄金3秒",
    pain: "痛点",
    selling: "卖点",
    cta: "行动号召",
    structure: "结构拆解",
    template: "模板",
    rewrites: "AI仿写区",
    copy: "复制",
    copied: "已复制",
    continue: "继续仿写",
    avatar: "生成数字人",
    empty: "粘贴一个爆款链接后开始。",
  },
  en: {
    badge: "AI Video Agent Studio",
    title: "AI Short Video Factory",
    subtitle: "Paste a viral link. AI analyzes, rewrites, and turns it into a talking-avatar video.",
    placeholder: "Paste a viral video link. AI will analyze and rewrite it.",
    analyze: "Start analysis",
    analyzing: "Analyzing",
    supports: "Supports Douyin / TikTok / YouTube Shorts",
    fallback: "This Douyin link cannot be parsed yet. Paste the script or upload the video to continue.",
    login: "Please sign in before analyzing viral links.",
    status: "Agent status",
    preview: "Live preview",
    metadata: "Link metadata",
    topic: "Video topic",
    hook: "Golden 3 seconds",
    pain: "Pain points",
    selling: "Selling points",
    cta: "CTA",
    structure: "Structure",
    template: "Template",
    rewrites: "AI rewrites",
    copy: "Copy",
    copied: "Copied",
    continue: "Rewrite more",
    avatar: "Generate avatar",
    empty: "Paste a viral link to begin.",
  },
};

export function StudioWorkspace() {
  const { locale } = useLanguage();
  const t = copy[locale];
  const supabase = useMemo(() => createClient(), []);
  const [sourceUrl, setSourceUrl] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [copied, setCopied] = useState<string | null>(null);
  const [resolveResult, setResolveResult] = useState<VideoLinkResolveResult | null>(null);
  const [notice, setNotice] = useState("");
  const isRunning = activeStep >= 0 && activeStep < 3;
  const hasStarted = activeStep >= 0;
  const steps = useMemo(
    () =>
      workflowSteps.map((label, index): { label: string; state: StepState } => ({
        label,
        state: activeStep > index ? "done" : activeStep === index ? "running" : "idle",
      })),
    [activeStep],
  );

  async function startWorkflow() {
    if (!sourceUrl.trim()) return;
    setNotice("");
    setResolveResult(null);
    setActiveStep(0);
    window.setTimeout(() => setActiveStep(1), 360);
    window.setTimeout(() => setActiveStep(2), 720);
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      setActiveStep(3);
      setNotice(t.login);
      return;
    }
    try {
      const result = await resolveVideoLink(sourceUrl, session.access_token);
      setResolveResult(result);
      setActiveStep(3);
      if (!result.ok) {
        setNotice(result.fallback_reason || t.fallback);
      }
    } catch (error) {
      setActiveStep(3);
      setNotice(error instanceof Error ? error.message : t.fallback);
    }
  }

  async function copyRewrite(title: string, script: string) {
    await navigator.clipboard.writeText(script);
    setCopied(title);
    window.setTimeout(() => setCopied(null), 1400);
  }

  return (
    <main className="min-h-[calc(100vh-86px)] bg-ink text-slate-100">
      <div className="mx-auto grid max-w-[1500px] gap-6 px-4 py-6 sm:px-6 xl:grid-cols-[1.08fr_0.92fr]">
        <section className="space-y-5">
          <div className="rounded-lg border border-white/10 bg-panel/85 p-5 shadow-glow">
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-sm font-semibold text-cyan">
              <Sparkles size={15} />
              {t.badge}
            </p>
            <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-tight text-white sm:text-5xl">{t.title}</h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-400">{t.subtitle}</p>
            <div className="mt-6 grid gap-3 rounded-lg border border-cyan/20 bg-cyan/[0.06] p-3 sm:grid-cols-[1fr_auto]">
              <input
                className="h-12 rounded-md border border-white/10 bg-ink/80 px-4 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan/60"
                value={sourceUrl}
                onChange={(event) => setSourceUrl(event.target.value)}
                placeholder={t.placeholder}
              />
              <button
                type="button"
                disabled={!sourceUrl.trim() || isRunning}
                onClick={startWorkflow}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-cyan px-5 text-sm font-semibold text-ink transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-55"
              >
                {isRunning ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
                {isRunning ? t.analyzing : t.analyze}
              </button>
            </div>
            <p className="mt-3 text-sm text-slate-500">{t.supports}</p>
            {notice ? <p className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">{notice}</p> : null}
          </div>

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-lg font-semibold text-white">{t.status}</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {steps.map((step) => (
                <div
                  key={step.label}
                  className={[
                    "flex items-center gap-3 rounded-md border px-3 py-3 text-sm",
                    step.state === "done"
                      ? "border-lime/25 bg-lime/10 text-lime"
                      : step.state === "running"
                        ? "border-cyan/35 bg-cyan/10 text-cyan"
                        : "border-white/10 bg-white/[0.03] text-slate-500",
                  ].join(" ")}
                >
                  {step.state === "running" ? <Loader2 className="animate-spin" size={17} /> : <CheckCircle2 size={17} />}
                  {step.label}
                </div>
              ))}
            </div>
          </section>

          {resolveResult ? (
            <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <h2 className="text-lg font-semibold text-white">{t.metadata}</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-[140px_1fr]">
                {resolveResult.thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={resolveResult.thumbnail} alt={resolveResult.title || "Douyin thumbnail"} className="aspect-[3/4] w-full rounded-md border border-white/10 object-cover" />
                ) : (
                  <div className="grid aspect-[3/4] place-items-center rounded-md border border-white/10 bg-white/[0.035] text-xs text-slate-500">No cover</div>
                )}
                <div className="space-y-2 text-sm leading-6 text-slate-300">
                  <InfoRow label="platform" value={resolveResult.platform || "douyin"} />
                  <InfoRow label="title" value={resolveResult.title || "-"} />
                  <InfoRow label="duration" value={resolveResult.duration ? `${resolveResult.duration}s` : "-"} />
                  <InfoRow label="downloadable" value={resolveResult.downloadable ? "true" : "false"} />
                  <InfoRow label="url" value={resolveResult.webpage_url || sourceUrl} />
                </div>
              </div>
            </section>
          ) : null}

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
            <div className="mt-4 grid gap-3">
              {rewrites.map(([title, script]) => (
                <article key={title} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="font-semibold text-cyan">{title}</h3>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
                        onClick={() => copyRewrite(title, script)}
                      >
                        <Copy size={14} />
                        {copied === title ? t.copied : t.copy}
                      </button>
                      <button type="button" className="inline-flex h-9 items-center gap-2 rounded-md border border-cyan/25 px-3 text-xs font-semibold text-cyan hover:bg-cyan/10">
                        {t.continue}
                      </button>
                      <Link
                        className="inline-flex h-9 items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                        href={`/studio/avatar?script_text=${encodeURIComponent(script)}`}
                      >
                        {t.avatar}
                        <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-300">{script}</p>
                </article>
              ))}
            </div>
          </section>
        </section>

        <aside className="space-y-5">
          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Video className="text-cyan" size={20} />
              {t.preview}
            </h2>
            <div className="mt-4 grid aspect-[9/16] max-h-[620px] place-items-center rounded-lg border border-white/10 bg-black/45">
              <div className="px-8 text-center">
                <Clapperboard className="mx-auto text-cyan" size={36} />
                <p className="mt-4 text-sm leading-6 text-slate-500">{hasStarted ? sourceUrl : t.empty}</p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <FileText className="text-cyan" size={20} />
              {t.topic}
            </h2>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
              <InfoRow label={t.topic} value="工商业储能为什么越来越赚钱" />
              <InfoRow label={t.hook} value="不要再傻傻卖储能了" />
              <InfoRow label={t.pain} value="电费上涨 / 利润下滑 / 产能受限" />
              <InfoRow label={t.selling} value="峰谷套利 / 降低用电成本 / 快速回本" />
              <InfoRow label={t.cta} value="留言领取方案" />
              <InfoRow label={t.structure} value="钩子 -> 痛点放大 -> 解决方案 -> 案例证明 -> 行动号召" />
              <InfoRow label={t.template} value="不是 X 不赚钱，而是你没有找到 Y 的方法。" />
            </div>
            <Link className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-cyan hover:text-cyan/80" href="/studio/viral-analyzer">
              Viral Analyzer
              <ExternalLink size={15} />
            </Link>
          </section>
        </aside>
      </div>
    </main>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.035] p-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-slate-200">{value}</p>
    </div>
  );
}
