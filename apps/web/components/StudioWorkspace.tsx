"use client";

import { ArrowRight, CheckCircle2, Clapperboard, Copy, ExternalLink, FileText, Loader2, Play, Sparkles, Video } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { HomeVideoAgentPreview } from "@/components/HomeVideoAgentPreview";
import { TaskForm } from "@/components/TaskForm";
import { useLanguage } from "@/components/LanguageProvider";
import { runViralPipeline } from "@/lib/api";
import { studioCopy } from "@/lib/i18n/studio";
import { createClient } from "@/lib/supabase/client";
import type { ViralPipelineResult, ViralRewrite, VideoLinkResolveResult, VoiceClone } from "@/lib/types";

type StepState = "idle" | "running" | "done";
type CurrentAnalysis = NonNullable<ViralPipelineResult["analysis"]>;
type AnalysisRows = readonly (readonly [string, string])[];

const STALE_STUDIO_DEMO_MARKERS = [
  [24037, 21830, 19994, 20648, 33021],
  [21334, 20648, 33021],
  [23792, 35895, 22871, 21033],
  [30005, 36153, 19978, 28072],
  [21033, 28070, 19979, 28369],
  [20135, 33021, 21463, 38480],
  [19981, 35201, 20877, 20667, 20667],
].map((codes) => String.fromCharCode(...codes));

type StudioWorkspaceProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  quotaLoadFailed?: boolean;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
  livePortraitEnabled?: boolean;
};

export function StudioWorkspace({
  userEmail,
  remainingQuota,
  quotaLoadFailed = false,
  voiceCloneEnabled = false,
  voiceClones = [],
  livePortraitEnabled = false,
}: StudioWorkspaceProps) {
  const { locale } = useLanguage();
  const t = studioCopy[locale];
  const supabase = useMemo(() => createClient(), []);
  const [sourceUrl, setSourceUrl] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [copied, setCopied] = useState<string | null>(null);
  const [resolveResult, setResolveResult] = useState<VideoLinkResolveResult | null>(null);
  const [currentAnalysis, setCurrentAnalysis] = useState<CurrentAnalysis | null>(null);
  const [rewriteVersions, setRewriteVersions] = useState<ViralRewrite[]>([]);
  const [notice, setNotice] = useState("");
  const [selectedScript, setSelectedScript] = useState("");
  const [avatarFormVersion, setAvatarFormVersion] = useState(0);
  const isRunning = activeStep >= 0 && activeStep < 3;
  const hasStarted = activeStep >= 0;
  const sampleLabel = locale === "zh" ? "示例预览" : "Sample preview";
  const waitingLabel = isRunning ? t.analyzing : locale === "zh" ? "等待当前分析结果" : "Waiting for current analysis";
  const showDemoPreview = !sourceUrl.trim() && !hasStarted && !resolveResult && !currentAnalysis && rewriteVersions.length === 0;
  const demoAnalysisRows: AnalysisRows =
    locale === "zh"
      ? [
          [t.topic, "AI口播智能体，两小时卖50W"],
          [t.hook, "别再只靠人工写口播了"],
          [t.pain, "选题慢 / 文案弱 / 转化低"],
          [t.selling, "自动拆解爆款 / 快速仿写 / 一键进入数字人口播"],
          [t.cta, "上传链接，生成你的第一条 AI 口播视频"],
          [t.structure, "钩子 → 痛点 → 解决方案 → 场景证明 → 行动号召"],
          [t.template, "不是你不会做口播，而是你缺少一套从爆款到成交的生产流程。"],
        ]
      : [
          [t.topic, "AI talking agent sells 500K in two hours"],
          [t.hook, "Stop writing every talking script by hand"],
          [t.pain, "Slow topic selection / weak scripts / low conversion"],
          [t.selling, "Analyze viral videos / rewrite quickly / send to talking avatar in one flow"],
          [t.cta, "Paste a link and generate your first AI talking-avatar video"],
          [t.structure, "Hook → Pain point → Solution → Use case proof → CTA"],
          [t.template, "It is not that you cannot make talking videos. You need a repeatable flow from viral structure to conversion."],
        ];
  const currentAnalysisRows = currentAnalysis
    ? [
        [t.topic, currentAnalysis.topic],
        [t.hook, currentAnalysis.hook],
        [t.pain, ""],
        [t.selling, currentAnalysis.selling_points.join(" / ")],
        [t.cta, ""],
        [t.structure, currentAnalysis.structure.join(" → ")],
        [t.template, currentAnalysis.template],
      ]
    : [];
  const displayRewrites = rewriteVersions.map((item) => [item.title, item.script] as const);

  useEffect(() => {
    [window.localStorage, window.sessionStorage].forEach((storage) => {
      for (let index = storage.length - 1; index >= 0; index -= 1) {
        const key = storage.key(index);
        if (!key) continue;
        const value = storage.getItem(key) || "";
        if (STALE_STUDIO_DEMO_MARKERS.some((marker) => value.includes(marker))) {
          storage.removeItem(key);
        }
      }
    });
  }, []);
  const steps = useMemo(
    () =>
      t.steps.map((label, index): { label: string; state: StepState } => ({
        label,
        state: activeStep > index ? "done" : activeStep === index ? "running" : "idle",
      })),
    [activeStep, t.steps],
  );

  async function startWorkflow() {
    if (!sourceUrl.trim()) return;
    setNotice("");
    setResolveResult(null);
    setCurrentAnalysis(null);
    setRewriteVersions([]);
    setSelectedScript("");
    setAvatarFormVersion((version) => version + 1);
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
      const result = await runViralPipeline({ source_url: sourceUrl, language: locale }, session.access_token);
      setResolveResult({
        ok: result.ok,
        platform: result.metadata?.platform || "douyin",
        title: result.metadata?.title || "",
        description: result.metadata?.description || "",
        duration: result.metadata?.duration || 0,
        thumbnail: result.metadata?.thumbnail || "",
        webpage_url: result.metadata?.webpage_url || sourceUrl,
        downloadable: Boolean(result.metadata?.downloadable),
        fallback_reason: result.fallback_reason,
      });
      setCurrentAnalysis(result.analysis);
      setRewriteVersions(result.rewrites || []);
      setActiveStep(3);
      if (!result.ok) {
        setCurrentAnalysis(null);
        setRewriteVersions([]);
        setNotice(result.fallback_reason || t.fallback);
      }
    } catch (error) {
      setActiveStep(3);
      setCurrentAnalysis(null);
      setRewriteVersions([]);
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
            <div className="mt-5 flex flex-wrap gap-2 text-xs font-semibold text-slate-400">
              {t.workflow.map((step, index) => (
                <span key={step} className="inline-flex items-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">{step}</span>
                  {index < t.workflow.length - 1 ? <ArrowRight size={13} className="text-cyan" /> : null}
                </span>
              ))}
            </div>
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
                  <div className="grid aspect-[3/4] place-items-center rounded-md border border-white/10 bg-white/[0.035] text-xs text-slate-500">{t.noCover}</div>
                )}
                <div className="space-y-2 text-sm leading-6 text-slate-300">
                  <InfoRow label={t.metadataLabels.platform} value={resolveResult.platform || "douyin"} />
                  <InfoRow label={t.metadataLabels.title} value={resolveResult.title || "-"} />
                  <InfoRow label={t.metadataLabels.duration} value={resolveResult.duration ? `${resolveResult.duration}s` : "-"} />
                  <InfoRow label={t.metadataLabels.downloadable} value={resolveResult.downloadable ? "true" : "false"} />
                  <InfoRow label={t.metadataLabels.url} value={resolveResult.webpage_url || sourceUrl} />
                </div>
              </div>
            </section>
          ) : null}

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
            <div className="mt-4 grid gap-3">
              {displayRewrites.length > 0 ? (
                displayRewrites.map(([title, script]) => (
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
                      <button
                        type="button"
                        className="inline-flex h-9 items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                        onClick={() => {
                          setSelectedScript(script);
                          document.getElementById("avatar-studio")?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }}
                      >
                        {t.avatar}
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-300">{script}</p>
                </article>
                ))
              ) : (
                <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-500">{hasStarted ? waitingLabel : t.empty}</div>
              )}
            </div>
          </section>
        </section>

        <aside className="space-y-5">
          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Video className="text-cyan" size={20} />
              {t.preview}
            </h2>
            <div className="mt-4">
              {hasStarted ? (
                <div className="grid aspect-[9/16] max-h-[620px] place-items-center rounded-lg border border-white/10 bg-black/45">
                  <div className="px-8 text-center">
                    <Clapperboard className="mx-auto text-cyan" size={36} />
                    <p className="mt-4 text-sm leading-6 text-slate-500">{sourceUrl}</p>
                  </div>
                </div>
              ) : (
                <HomeVideoAgentPreview />
              )}
            </div>
          </section>

          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <FileText className="text-cyan" size={20} />
              {t.topic}
            </h2>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
              {showDemoPreview ? (
                <DemoAnalysisPreview label={sampleLabel} rows={demoAnalysisRows} />
              ) : currentAnalysis ? (
                currentAnalysisRows.map(([label, value]) => <InfoRow key={label} label={label} value={value || waitingLabel} />)
              ) : (
                <div className="rounded-md border border-white/10 bg-white/[0.035] p-3 text-slate-500">{waitingLabel}</div>
              )}
            </div>
            <Link className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-cyan hover:text-cyan/80" href="/studio/viral-analyzer">
              {t.advancedAnalyzer}
              <ExternalLink size={15} />
            </Link>
          </section>
        </aside>
      </div>
      <section id="avatar-studio" className="mx-auto max-w-[1500px] px-4 pb-10 sm:px-6">
        <div className="mb-4">
          <h2 className="text-2xl font-semibold text-white">{t.avatarStudio}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">{t.avatarStudioSubtitle}</p>
        </div>
        <TaskForm
          key={avatarFormVersion}
          userEmail={userEmail}
          remainingQuota={remainingQuota}
          quotaLoadFailed={quotaLoadFailed}
          voiceCloneEnabled={voiceCloneEnabled}
          voiceClones={voiceClones}
          livePortraitEnabled={livePortraitEnabled}
          initialScriptText={selectedScript}
        />
      </section>
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

function DemoAnalysisPreview({ label, rows }: { label: string; rows: readonly (readonly [string, string])[] }) {
  return (
    <>
      <p className="inline-flex rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">{label}</p>
      {rows.map(([rowLabel, value]) => (
        <InfoRow key={rowLabel} label={rowLabel} value={value} />
      ))}
    </>
  );
}
