"use client";

import { ArrowRight, CheckCircle2, Clapperboard, Copy, ExternalLink, FileText, Loader2, Play, Sparkles, Video } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";
import { runViralPipeline } from "@/lib/api";
import { studioCopy } from "@/lib/i18n/studio";
import { createClient } from "@/lib/supabase/client";
import type { ViralPipelineResult, ViralPipelineStatus, ViralRewrite } from "@/lib/types";

type StepState = "idle" | "running" | "done";
type StudioCopy = (typeof studioCopy)[keyof typeof studioCopy];

const failedStepIndex: Record<ViralPipelineStatus, number> = {
  pending: 0,
  resolving_link: 0,
  downloading_video: 1,
  extracting_audio: 2,
  transcribing: 3,
  analyzing: 4,
  metadata_fallback: 4,
  rewriting: 5,
  ready: 6,
  failed: 0,
};

export function StudioWorkspace() {
  const { locale, selectedLocale } = useLanguage();
  const t = studioCopy[selectedLocale] ?? studioCopy.en;
  const supabase = useMemo(() => createClient(), []);
  const [sourceUrl, setSourceUrl] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [copied, setCopied] = useState<string | null>(null);
  const [pipelineResult, setPipelineResult] = useState<ViralPipelineResult | null>(null);
  const [notice, setNotice] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const hasStarted = activeStep >= 0;
  const rewrites = pipelineResult?.rewrites || [];
  const fallbackActions = notice && sourceUrl.trim() && pipelineResult?.ok === false ? getFallbackActions(t) : [];
  const steps = useMemo(
    () =>
      t.workflowSteps.map((label, index): { label: string; state: StepState } => ({
        label,
        state: activeStep > index ? "done" : activeStep === index ? "running" : "idle",
      })),
    [activeStep, t.workflowSteps],
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
            {notice ? (
              <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
                <p>{notice}</p>
                {sourceUrl ? <p className="mt-2 break-words text-xs text-amber-100/75">{sourceUrl}</p> : null}
                {fallbackActions.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {fallbackActions.map((action) =>
                      action.href ? (
                        <Link
                          key={action.label}
                          href={action.href}
                          className="inline-flex h-9 items-center gap-2 rounded-md border border-amber-200/25 px-3 text-xs font-semibold text-amber-50 hover:bg-amber-100/10"
                        >
                          <action.icon size={14} />
                          {action.label}
                        </Link>
                      ) : (
                        <button
                          key={action.label}
                          type="button"
                          onClick={action.onClick}
                          className="inline-flex h-9 items-center gap-2 rounded-md border border-amber-200/25 px-3 text-xs font-semibold text-amber-50 hover:bg-amber-100/10"
                        >
                          <action.icon size={14} />
                          {action.label}
                        </button>
                      ),
                    )}
                  </div>
                ) : null}
              </div>
            ) : null}
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
                  <div className="grid aspect-[3/4] place-items-center rounded-md border border-white/10 bg-white/[0.035] text-xs text-slate-500">{t.noCover}</div>
                )}
                <div className="space-y-2 text-sm leading-6 text-slate-300">
                  <InfoRow label={t.metadataLabels.platform} value={pipelineResult.metadata.platform || "douyin"} />
                  <InfoRow label={t.metadataLabels.title} value={pipelineResult.metadata.title || "-"} />
                  <InfoRow label={t.metadataLabels.duration} value={pipelineResult.metadata.duration ? `${pipelineResult.metadata.duration}s` : "-"} />
                  <InfoRow label={t.metadataLabels.downloadable} value={pipelineResult.metadata.downloadable ? "true" : "false"} />
                  <InfoRow label={t.metadataLabels.url} value={pipelineResult.metadata.webpage_url || sourceUrl} />
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
              {t.advancedAnalyzer}
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

function getFallbackActions(t: StudioCopy) {
  return [
    {
      label: t.fallbackActions.upload,
      icon: Video,
      href: "/studio/viral-analyzer",
    },
    {
      label: t.fallbackActions.paste,
      icon: FileText,
      href: "/studio/viral-analyzer",
    },
    {
      label: t.fallbackActions.check,
      icon: ExternalLink,
      onClick: () => document.querySelector<HTMLInputElement>("input")?.focus(),
    },
  ];
}
