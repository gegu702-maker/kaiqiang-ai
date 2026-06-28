"use client";

import { ArrowRight, CheckCircle2, Copy, ExternalLink, FileText, Loader2, Play, Sparkles, Video } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { TaskForm } from "@/components/TaskForm";
import { useLanguage } from "@/components/LanguageProvider";
import { runViralPipeline } from "@/lib/api";
import { studioCopy } from "@/lib/i18n/studio";
import { createClient } from "@/lib/supabase/client";
import type { ViralPipelineResult, ViralRewrite, VideoLinkResolveResult, VoiceClone } from "@/lib/types";

type StepState = "idle" | "running" | "done";
type AnalysisStatus = "idle" | "resolving" | "needs_script" | "ready" | "error";
type StudioAnalysis = NonNullable<ViralPipelineResult["analysis"]>;

type StudioWorkspaceProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  quotaLoadFailed?: boolean;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
};

export function StudioWorkspace({
  userEmail,
  remainingQuota,
  quotaLoadFailed = false,
  voiceCloneEnabled = false,
  voiceClones = [],
}: StudioWorkspaceProps) {
  const { locale } = useLanguage();
  const t = studioCopy[locale];
  const supabase = useMemo(() => createClient(), []);
  const [sourceUrl, setSourceUrl] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [copied, setCopied] = useState<string | null>(null);
  const [resolveResult, setResolveResult] = useState<VideoLinkResolveResult | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [currentAnalysis, setCurrentAnalysis] = useState<StudioAnalysis | null>(null);
  const [rewriteVersions, setRewriteVersions] = useState<ViralRewrite[]>([]);
  const [transcript, setTranscript] = useState("");
  const [analysisSourceType, setAnalysisSourceType] = useState("");
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>("idle");
  const [analysisError, setAnalysisError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedScript, setSelectedScript] = useState("");
  const isRunning = activeStep >= 0 && activeStep < 3;
  const canShowDemo =
    !sourceUrl.trim() &&
    !hasStarted &&
    !resolveResult &&
    !currentAnalysis &&
    rewriteVersions.length === 0;
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
    setHasStarted(true);
    setNotice("");
    setResolveResult(null);
    setCurrentAnalysis(null);
    setRewriteVersions([]);
    setTranscript("");
    setAnalysisSourceType("");
    setAnalysisError("");
    setAnalysisStatus("resolving");
    setActiveStep(0);
    window.setTimeout(() => setActiveStep(1), 360);
    window.setTimeout(() => setActiveStep(2), 720);
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      setActiveStep(3);
      setAnalysisStatus("error");
      setAnalysisError(t.login);
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
      const metadata = result.metadata ?? {};
      const isMetadataFallback = result.source_type === "link_metadata_fallback";
      setResolveResult({
        ok: result.ok,
        platform: metadata.platform || "douyin",
        title: metadata.title || "",
        description: metadata.description || "",
        duration: metadata.duration || 0,
        thumbnail: metadata.thumbnail || "",
        webpage_url: metadata.webpage_url || sourceUrl,
        downloadable: Boolean(metadata.downloadable),
        fallback_reason: result.fallback_reason || "",
      });
      setTranscript(isMetadataFallback ? "" : result.transcript || "");
      setAnalysisSourceType(result.source_type || "");
      setActiveStep(3);
      if (!result.ok) {
        const message = result.fallback_reason || t.fallback;
        setAnalysisStatus("error");
        setAnalysisError(message);
        setNotice(message);
        return;
      }
      setCurrentAnalysis(result.analysis);
      setRewriteVersions(result.rewrites || []);
      if (result.analysis) {
        setAnalysisStatus("ready");
        setNotice(result.warning || "");
      } else {
        setAnalysisStatus("needs_script");
        setNotice(t.linkResolvedNeedsScript);
      }
    } catch (error) {
      setActiveStep(3);
      setAnalysisStatus("error");
      const message = error instanceof Error ? error.message : t.fallback;
      setAnalysisError(message);
      setNotice(message);
    }
  }

  async function copyRewrite(title: string, script: string) {
    await navigator.clipboard.writeText(script);
    setCopied(title);
    window.setTimeout(() => setCopied(null), 1400);
  }

  return (
    <main className="min-h-[calc(100vh-86px)] w-full max-w-full overflow-x-hidden bg-ink text-slate-100">
      <div className="mx-auto grid w-full max-w-[1500px] grid-cols-1 gap-6 overflow-hidden px-4 py-6 sm:px-6 xl:grid-cols-[minmax(0,1fr)_minmax(220px,320px)]">
        <section className="min-w-0 max-w-full space-y-5 overflow-hidden">
          <div className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/85 p-5 shadow-glow">
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-sm font-semibold text-cyan">
              <Sparkles size={15} />
              {t.badge}
            </p>
            <h1 className="mt-4 max-w-3xl break-words text-4xl font-semibold leading-tight text-white sm:text-5xl">{t.title}</h1>
            <p className="mt-3 max-w-2xl break-words text-base leading-7 text-slate-400">{t.subtitle}</p>
            <div className="mt-5 flex flex-wrap gap-2 text-xs font-semibold text-slate-400">
              {t.workflow.map((step, index) => (
                <span key={step} className="inline-flex max-w-full min-w-0 items-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 break-words">{step}</span>
                  {index < t.workflow.length - 1 ? <ArrowRight size={13} className="text-cyan" /> : null}
                </span>
              ))}
            </div>
            <div className="mt-6 grid min-w-0 gap-3 rounded-lg border border-cyan/20 bg-cyan/[0.06] p-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <input
                className="h-12 min-w-0 rounded-md border border-white/10 bg-ink/80 px-4 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan/60"
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
            <p className="mt-3 break-words text-sm text-slate-500">{t.supports}</p>
            {notice ? <p className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100 break-words [overflow-wrap:anywhere]">{notice}</p> : null}
          </div>

          {resolveResult ? (
            <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <h2 className="text-lg font-semibold text-white">{t.metadata}</h2>
              <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-[140px_minmax(0,1fr)]">
                {resolveResult.thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={resolveResult.thumbnail} alt={resolveResult.title || "Douyin thumbnail"} className="aspect-[3/4] w-full rounded-md border border-white/10 object-cover" />
                ) : (
                  <div className="grid aspect-[3/4] place-items-center rounded-md border border-white/10 bg-white/[0.035] text-xs text-slate-500">{t.noCover}</div>
                )}
                <div className="min-w-0 space-y-2 text-sm leading-6 text-slate-300">
                  <InfoRow label={t.metadataLabels.platform} value={resolveResult.platform || "douyin"} />
                  <InfoRow label={t.metadataLabels.title} value={resolveResult.title || "-"} />
                  <InfoRow label={t.metadataLabels.duration} value={resolveResult.duration ? `${resolveResult.duration}s` : "-"} />
                  <InfoRow label="链接状态" value="已识别" />
                  <InfoRow
                    label="视频读取"
                    value={resolveResult.downloadable ? "可用" : "受限，当前使用链接公开信息分析"}
                  />
                  {analysisSourceType === "link_metadata_fallback" ? <InfoRow label="分析来源" value="链接公开信息" /> : null}
                </div>
              </div>
            </section>
          ) : null}

          {transcript ? (
            <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <h2 className="text-lg font-semibold text-white">{t.transcript}</h2>
              <p className="mt-4 whitespace-pre-wrap rounded-md border border-white/10 bg-white/[0.035] p-4 text-sm leading-7 text-slate-300 break-words [overflow-wrap:anywhere]">{transcript}</p>
            </section>
          ) : null}

          <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <FileText className="text-cyan" size={20} />
              {t.topic}
            </h2>
            {currentAnalysis ? (
              <div className="mt-4 grid min-w-0 gap-3 text-sm leading-6 text-slate-300 sm:grid-cols-2">
                <InfoRow label={t.topic} value={currentAnalysis.topic || "-"} />
                <InfoRow label={t.hook} value={currentAnalysis.hook || "-"} />
                <InfoRow label={t.selling} value={(currentAnalysis.selling_points || []).join(" / ") || "-"} />
                <InfoRow label={t.structure} value={(currentAnalysis.structure || []).join(" → ") || "-"} />
                <InfoRow label={t.template} value={currentAnalysis.template || "-"} />
              </div>
            ) : hasStarted ? (
              <EmptyState message={analysisStatus === "error" ? analysisError || t.analysisUnavailable : t.linkResolvedNeedsScript} />
            ) : canShowDemo ? (
              <div className="mt-4 grid min-w-0 gap-3 text-sm leading-6 text-slate-300 sm:grid-cols-2">
                <InfoRow label={t.hook} value={t.sampleAnalysis.hook} />
                <InfoRow label={t.pain} value={t.sampleAnalysis.pain} />
                <InfoRow label={t.selling} value={t.sampleAnalysis.selling} />
                <InfoRow label={t.cta} value={t.sampleAnalysis.cta} />
                <InfoRow label={t.structure} value={t.sampleAnalysis.structure} />
                <InfoRow label={t.template} value={t.sampleAnalysis.template} />
              </div>
            ) : (
              <EmptyState message={t.analysisUnavailable} />
            )}
            <Link className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-cyan hover:text-cyan/80" href="/studio/viral-analyzer">
              {t.advancedAnalyzer}
              <ExternalLink size={15} />
            </Link>
          </section>

          <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
            <div className="mt-4 grid gap-3">
              {(rewriteVersions.length > 0
                ? rewriteVersions.map(({ title, script }) => [title, script] as const)
                : canShowDemo
                  ? t.rewriteSamples
                  : []
              ).map(([title, script]) => (
                <article key={title} className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-white/[0.035] p-4">
                  <h3 className="break-words font-semibold text-cyan [overflow-wrap:anywhere]">{title}</h3>
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300 [overflow-wrap:anywhere]">{script}</p>
                  <div className="mt-4 flex max-w-full flex-wrap justify-start gap-2 sm:justify-end">
                    <button
                      type="button"
                      className="inline-flex h-9 max-w-full items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
                      onClick={() => copyRewrite(title, script)}
                    >
                      <Copy size={14} />
                      <span className="truncate">{copied === title ? t.copied : t.copy}</span>
                    </button>
                    <button type="button" className="inline-flex h-9 max-w-full items-center gap-2 rounded-md border border-cyan/25 px-3 text-xs font-semibold text-cyan hover:bg-cyan/10">
                      <span className="truncate">{t.continue}</span>
                    </button>
                    <button
                      type="button"
                      className="inline-flex h-9 max-w-full items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                      onClick={() => {
                        setSelectedScript(script);
                        document.getElementById("avatar-studio")?.scrollIntoView({ behavior: "smooth", block: "start" });
                      }}
                    >
                      <span className="truncate">{t.avatar}</span>
                      <ArrowRight size={14} />
                    </button>
                  </div>
                </article>
              ))}
              {rewriteVersions.length === 0 && !canShowDemo ? <EmptyState message={hasStarted ? t.rewritesUnavailable : t.empty} /> : null}
            </div>
          </section>
        </section>

        <aside className="min-w-0 max-w-full space-y-5 overflow-hidden xl:w-[320px]">
          <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow xl:sticky xl:top-24">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Video className="text-cyan" size={20} />
              {t.preview}
            </h2>
            <p className="mt-2 text-sm text-lime">{t.dynamicReady}</p>
            <div className="mt-5 space-y-3">
              {steps.map((step, index) => (
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
                  <span className="grid size-7 shrink-0 place-items-center rounded-full border border-current/25 text-xs font-semibold">
                    {step.state === "running" ? <Loader2 className="animate-spin" size={15} /> : index + 1}
                  </span>
                  <span className="min-w-0 flex-1 break-words">{step.label}</span>
                  {step.state === "done" ? <CheckCircle2 size={16} /> : null}
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
      <section id="avatar-studio" className="mx-auto w-full max-w-[1500px] overflow-hidden px-4 pb-10 sm:px-6">
        <div className="mb-4">
          <h2 className="text-2xl font-semibold text-white">{t.avatarStudio}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">{t.avatarStudioSubtitle}</p>
        </div>
        <TaskForm
          userEmail={userEmail}
          remainingQuota={remainingQuota}
          quotaLoadFailed={quotaLoadFailed}
          voiceCloneEnabled={voiceCloneEnabled}
          voiceClones={voiceClones}
          initialScriptText={selectedScript}
        />
      </section>
    </main>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 max-w-full overflow-hidden rounded-md border border-white/10 bg-white/[0.035] p-3">
      <p className="break-words text-xs font-semibold text-slate-500 [overflow-wrap:anywhere]">{label}</p>
      <p className="mt-1 break-words text-slate-200 [overflow-wrap:anywhere]">{value}</p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="mt-4 rounded-md border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-400 break-words [overflow-wrap:anywhere]">{message}</p>;
}
