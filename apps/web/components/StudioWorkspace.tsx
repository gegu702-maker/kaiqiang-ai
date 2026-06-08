"use client";

import { ArrowRight, CheckCircle2, Clapperboard, Copy, ExternalLink, FileText, Loader2, Play, Sparkles, Video } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { HomeVideoAgentPreview } from "@/components/HomeVideoAgentPreview";
import { useLanguage } from "@/components/LanguageProvider";
import { StudioNavigation } from "@/components/StudioNavigation";
import { TaskForm } from "@/components/TaskForm";
import { runViralPipeline } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { ViralPipelineResult, ViralPipelineStatus, ViralRewrite, VoiceClone } from "@/lib/types";

type StepState = "idle" | "running" | "done";

const workflowSteps = ["解析链接", "下载视频", "提取音频", "自动转写", "拆解爆点", "生成原创版本", "分析完成"];

const failedStepIndex: Record<ViralPipelineStatus, number> = {
  pending: 0,
  resolving_link: 0,
  downloading_video: 1,
  extracting_audio: 2,
  transcribing: 3,
  analyzing: 4,
  rewriting: 5,
  ready: 6,
  failed: 0,
};

type StudioWorkspaceProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  quotaLoadFailed?: boolean;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
  livePortraitEnabled?: boolean;
};

const copy = {
  zh: {
    badge: "AI Video Agent Studio",
    title: "AI 短视频生产工厂",
    subtitle: "粘贴爆款链接，AI 自动拆解、仿写并生成数字人口播视频。",
    placeholder: "粘贴爆款视频链接，AI自动拆解并生成原创口播",
    analyze: "开始分析",
    analyzing: "分析中",
    supports: "支持 抖音 / TikTok / YouTube Shorts",
    fallback: "该视频暂不支持自动解析，请上传视频继续分析。",
    login: "请先登录后再分析爆款链接。",
    status: "Agent 执行状态",
    preview: "实时预览",
    metadata: "视频信息",
    transcript: "自动转写文案",
    topic: "视频主题",
    hook: "黄金3秒",
    selling: "卖点",
    structure: "结构拆解",
    template: "模板",
    rewrites: "AI仿写区",
    copy: "复制",
    copied: "已复制",
    continue: "继续仿写",
    useScript: "使用此文案",
    avatar: "生成数字人",
    avatarStudio: "数字人口播工作台",
    avatarStudioSubtitle: "选择固定数字人模板、火山引擎音色、声音试听或克隆声音，然后生成口播视频。",
    deepAvatar: "打开深度 MuseTalk 上传生成页",
    empty: "粘贴一个爆款链接后开始。",
    noResult: "完成分析后，这里会显示自动拆解结果和原创仿写版本。",
  },
  en: {
    badge: "AI Video Agent Studio",
    title: "AI Short Video Factory",
    subtitle: "Paste a viral link. AI analyzes, rewrites, and turns it into a talking-avatar video.",
    placeholder: "Paste a viral video link. AI will analyze and rewrite it.",
    analyze: "Start analysis",
    analyzing: "Analyzing",
    supports: "Supports Douyin / TikTok / YouTube Shorts",
    fallback: "This video is not supported for automatic parsing yet. Upload a video to continue.",
    login: "Please sign in before analyzing viral links.",
    status: "Agent status",
    preview: "Live preview",
    metadata: "Video metadata",
    transcript: "Transcript",
    topic: "Video topic",
    hook: "Golden 3 seconds",
    selling: "Selling points",
    structure: "Structure",
    template: "Template",
    rewrites: "AI rewrites",
    copy: "Copy",
    copied: "Copied",
    continue: "Rewrite more",
    useScript: "Use script",
    avatar: "Generate avatar",
    avatarStudio: "Avatar Studio",
    avatarStudioSubtitle: "Choose a fixed avatar template, Volcengine voice, preview or cloned voice, then generate a talking-avatar video.",
    deepAvatar: "Open advanced MuseTalk uploader",
    empty: "Paste a viral link to begin.",
    noResult: "Analysis results and original rewrites will appear here after the run.",
  },
};

export function StudioWorkspace({ userEmail, remainingQuota, quotaLoadFailed = false, voiceCloneEnabled = false, voiceClones = [], livePortraitEnabled = false }: StudioWorkspaceProps) {
  const { locale } = useLanguage();
  const t = copy[locale];
  const supabase = useMemo(() => createClient(), []);
  const [sourceUrl, setSourceUrl] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [copied, setCopied] = useState<string | null>(null);
  const [selectedScript, setSelectedScript] = useState("");
  const [pipelineResult, setPipelineResult] = useState<ViralPipelineResult | null>(null);
  const [notice, setNotice] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const hasStarted = activeStep >= 0;
  const rewrites = pipelineResult?.rewrites || [];
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
    setPipelineResult(null);
    setActiveStep(0);
    setIsRunning(true);
    const progressTimer = window.setInterval(() => {
      setActiveStep((current) => (current >= 0 && current < 5 ? current + 1 : current));
    }, 1400);

    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      window.clearInterval(progressTimer);
      setIsRunning(false);
      setNotice(t.login);
      return;
    }

    try {
      const result = await runViralPipeline(
        {
          source_url: sourceUrl,
          industry: "personal_brand",
          language: locale,
        },
        session.access_token,
      );
      setPipelineResult(result);
      setActiveStep(result.ok ? 6 : failedStepIndex[result.failed_at || "failed"]);
      if (!result.ok) {
        setNotice(result.fallback_reason || t.fallback);
      }
    } catch (error) {
      setActiveStep(0);
      setNotice(error instanceof Error ? error.message : t.fallback);
    } finally {
      window.clearInterval(progressTimer);
      setIsRunning(false);
    }
  }

  async function copyRewrite(title: string, script: string) {
    await navigator.clipboard.writeText(script);
    setCopied(title);
    window.setTimeout(() => setCopied(null), 1400);
  }

  function continueRewrite(rewrite: ViralRewrite) {
    const nextScript = `${rewrite.script}\n\n换一个更适合数字人口播的角度：先用一句强钩子开场，再把痛点讲具体，最后给出明确行动。`;
    void copyRewrite(rewrite.title, nextScript);
  }

  function selectRewriteScript(script: string) {
    setSelectedScript(script);
    window.requestAnimationFrame(() => {
      document.getElementById("avatar-studio")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <main className="grid min-h-[calc(100vh-86px)] bg-ink text-slate-100 lg:grid-cols-[72px_1fr]">
      <StudioNavigation />
      <div className="w-full">
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
                  {step.state === "running" && isRunning ? <Loader2 className="animate-spin" size={17} /> : <CheckCircle2 size={17} />}
                  {step.label}
                </div>
              ))}
            </div>
          </section>

          {pipelineResult?.metadata ? (
            <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <h2 className="text-lg font-semibold text-white">{t.metadata}</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-[140px_1fr]">
                {pipelineResult.metadata.thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={pipelineResult.metadata.thumbnail} alt={pipelineResult.metadata.title || "Douyin thumbnail"} className="aspect-[3/4] w-full rounded-md border border-white/10 object-cover" />
                ) : (
                  <div className="grid aspect-[3/4] place-items-center rounded-md border border-white/10 bg-white/[0.035] text-xs text-slate-500">No cover</div>
                )}
                <div className="space-y-2 text-sm leading-6 text-slate-300">
                  <InfoRow label="platform" value={pipelineResult.metadata.platform || "douyin"} />
                  <InfoRow label="title" value={pipelineResult.metadata.title || "-"} />
                  <InfoRow label="duration" value={pipelineResult.metadata.duration ? `${pipelineResult.metadata.duration}s` : "-"} />
                  <InfoRow label="downloadable" value={pipelineResult.metadata.downloadable ? "true" : "false"} />
                  <InfoRow label="url" value={pipelineResult.metadata.webpage_url || sourceUrl} />
                </div>
              </div>
            </section>
          ) : null}

          {pipelineResult?.transcript ? (
            <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <h2 className="text-lg font-semibold text-white">{t.transcript}</h2>
              <p className="mt-3 max-h-56 overflow-auto rounded-md border border-white/10 bg-white/[0.035] p-3 text-sm leading-7 text-slate-300">
                {pipelineResult.transcript}
              </p>
            </section>
          ) : null}

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
            <div className="mt-4 grid gap-3">
              {rewrites.length === 0 ? <p className="rounded-md border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">{t.noResult}</p> : null}
              {rewrites.map((rewrite) => (
                <article key={rewrite.title} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="font-semibold text-cyan">{rewrite.title}</h3>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
                        onClick={() => copyRewrite(rewrite.title, rewrite.script)}
                      >
                        <Copy size={14} />
                        {copied === rewrite.title ? t.copied : t.copy}
                      </button>
                      <button type="button" className="inline-flex h-9 items-center gap-2 rounded-md border border-cyan/25 px-3 text-xs font-semibold text-cyan hover:bg-cyan/10" onClick={() => continueRewrite(rewrite)}>
                        {t.continue}
                      </button>
                      <button
                        type="button"
                        className="inline-flex h-9 items-center gap-2 rounded-md border border-lime/25 px-3 text-xs font-semibold text-lime hover:bg-lime/10"
                        onClick={() => selectRewriteScript(rewrite.script)}
                      >
                        {t.useScript}
                      </button>
                      <Link
                        className="inline-flex h-9 items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                        href={`/studio/avatar?script_text=${encodeURIComponent(rewrite.script)}`}
                      >
                        {t.avatar}
                        <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-300">{rewrite.script}</p>
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
                <p className="mt-4 text-sm leading-6 text-slate-500">{hasStarted ? pipelineResult?.metadata.title || sourceUrl : t.empty}</p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <FileText className="text-cyan" size={20} />
              {t.topic}
            </h2>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
              {pipelineResult?.analysis ? (
                <>
                  <InfoRow label={t.topic} value={pipelineResult.analysis.topic || "-"} />
                  <InfoRow label={t.hook} value={pipelineResult.analysis.hook || "-"} />
                  <InfoRow label={t.selling} value={pipelineResult.analysis.selling_points.join(" / ") || "-"} />
                  <InfoRow label={t.structure} value={pipelineResult.analysis.structure.join(" -> ") || "-"} />
                  <InfoRow label={t.template} value={pipelineResult.analysis.template || "-"} />
                </>
              ) : (
                <p className="rounded-md border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">{t.noResult}</p>
              )}
            </div>
            <Link className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-cyan hover:text-cyan/80" href="/studio/viral-analyzer">
              Viral Analyzer
              <ExternalLink size={15} />
            </Link>
          </section>
        </aside>
      </div>
      <section id="avatar-studio" className="mx-auto w-full max-w-[1500px] px-4 pb-8 sm:px-6">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-cyan">Avatar Studio</p>
            <h2 className="mt-2 text-3xl font-semibold text-white">{t.avatarStudio}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{t.avatarStudioSubtitle}</p>
          </div>
          <Link className="inline-flex h-10 items-center gap-2 rounded-md border border-white/10 px-3 text-sm font-semibold text-slate-200 hover:bg-white/[0.06]" href="/studio/avatar">
            {t.deepAvatar}
            <ExternalLink size={15} />
          </Link>
        </div>
        <div className="grid gap-5 xl:grid-cols-[1.08fr_0.92fr]">
          <TaskForm
            userEmail={userEmail}
            remainingQuota={remainingQuota}
            quotaLoadFailed={quotaLoadFailed}
            voiceCloneEnabled={voiceCloneEnabled}
            voiceClones={voiceClones}
            livePortraitEnabled={livePortraitEnabled}
            initialScriptText={selectedScript}
          />
          <HomeVideoAgentPreview />
        </div>
      </section>
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
