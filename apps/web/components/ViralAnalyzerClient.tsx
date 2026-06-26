"use client";

import { ArrowRight, Check, Clapperboard, Copy, FileText, LayoutDashboard, LinkIcon, Loader2, Sparkles, UploadCloud, WandSparkles } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";
import { analyzeViralScript, runViralPipeline } from "@/lib/api";
import { studioCopy, viralAnalyzerCopy } from "@/lib/i18n/studio";
import { createClient } from "@/lib/supabase/client";
import type { ViralAnalyzeResult, ViralIndustry, ViralPipelineResult } from "@/lib/types";

const industries: ViralIndustry[] = ["ecommerce", "knowledge", "training", "local", "personal_brand", "global"];

const LINK_PIPELINE_TIMEOUT_MS = 40000;
const VISIBLE_VIDEO_URL_RE = /(?:https?:\/\/|(?:v\.)?douyin\.com|(?:www\.)?iesdouyin\.com)/i;

export function ViralAnalyzerClient() {
  const { selectedLocale } = useLanguage();
  const supabase = useMemo(() => createClient(), []);
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [industry, setIndustry] = useState<ViralIndustry>("ecommerce");
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawScript, setRawScript] = useState("");
  const [videoFileName, setVideoFileName] = useState("");
  const [result, setResult] = useState<ViralAnalyzeResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const t = viralAnalyzerCopy[selectedLocale] ?? viralAnalyzerCopy.en;
  const studio = studioCopy[selectedLocale] ?? studioCopy.en;

  async function handleAnalyze() {
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error(t.authRequired);
      }
      const trimmedSourceUrl = sourceUrl.trim();
      const trimmedRawScript = rawScript.trim();
      const shouldRunLinkPipeline = Boolean(trimmedSourceUrl && !trimmedRawScript && hasVisibleVideoUrl(trimmedSourceUrl));
      const payload =
        shouldRunLinkPipeline
          ? mapPipelineResult(
              await runPipelineWithTimeout(
                {
                  source_url: trimmedSourceUrl,
                  industry,
                  language,
                },
                session.access_token,
                t.pipelineFallback,
              ),
              t.pipelineFallback,
            )
          : await analyzeViralScript(
              {
                source_url: hasVisibleVideoUrl(trimmedSourceUrl) ? trimmedSourceUrl : "",
                raw_script: trimmedRawScript || trimmedSourceUrl,
                industry,
                language,
              },
              session.access_token,
            );
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.genericError);
    } finally {
      setLoading(false);
    }
  }

  async function copyScript(script: string, index: number) {
    await navigator.clipboard.writeText(script);
    setCopiedIndex(index);
    window.setTimeout(() => setCopiedIndex(null), 1400);
  }

  return (
    <main className="min-h-[calc(100vh-86px)] bg-ink text-slate-100">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:py-10">
        <nav className="rounded-lg border border-white/10 bg-panel/80 p-3 shadow-glow lg:col-span-2" aria-label="Studio navigation">
          <div className="flex flex-wrap gap-2">
            <Link className="inline-flex h-10 items-center gap-2 rounded-md border border-white/10 px-3 text-sm font-semibold text-slate-200 transition hover:bg-white/[0.06]" href="/studio">
              <LayoutDashboard size={16} />
              {studio.backToStudio}
            </Link>
            <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-cyan px-3 text-sm font-semibold text-ink transition hover:bg-cyan/90" href="/studio/avatar">
              <Clapperboard size={16} />
              {studio.switchToAvatar}
              <ArrowRight size={15} />
            </Link>
          </div>
        </nav>
        <section className="space-y-5">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-sm font-semibold text-cyan">
              <Sparkles size={15} />
              {t.eyebrow}
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">{t.title}</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">{t.subtitle}</p>
          </div>

          <div className="rounded-lg border border-white/10 bg-panel/85 p-5 shadow-glow">
            <div className="grid gap-4">
              <label className="block">
                <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                  <LinkIcon size={16} className="text-cyan" />
                  {t.url}
                </span>
                <input
                  className="h-11 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan/60"
                  value={sourceUrl}
                  onChange={(event) => setSourceUrl(event.target.value)}
                  placeholder={t.linkPlaceholder}
                />
              </label>

              <label className="block">
                <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                  <FileText size={16} className="text-cyan" />
                  {t.rawScript}
                </span>
                <textarea
                  className="min-h-44 w-full resize-y rounded-md border border-white/10 bg-ink/70 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan/60"
                  maxLength={6000}
                  value={rawScript}
                  onChange={(event) => setRawScript(event.target.value)}
                  placeholder={t.scriptPlaceholder}
                />
              </label>

              <label className="block rounded-md border border-dashed border-white/15 bg-white/[0.03] p-4">
                <span className="flex items-center gap-2 text-sm font-semibold text-white">
                  <UploadCloud size={16} className="text-cyan" />
                  {t.upload}
                </span>
                <span className="mt-1 block text-xs leading-5 text-slate-500">{t.uploadHint}</span>
                <input
                  className="mt-3 block w-full text-sm text-slate-400 file:mr-4 file:rounded-md file:border-0 file:bg-cyan file:px-4 file:py-2 file:text-sm file:font-semibold file:text-ink hover:file:bg-cyan/90"
                  type="file"
                  accept="video/mp4,video/quicktime,video/webm"
                  onChange={(event) => setVideoFileName(event.target.files?.[0]?.name ?? "")}
                />
                {videoFileName ? <span className="mt-2 block truncate text-xs text-slate-500">{videoFileName}</span> : null}
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-white">{t.industry}</span>
                  <select
                    className="h-11 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none focus:border-cyan/60"
                    value={industry}
                    onChange={(event) => setIndustry(event.target.value as ViralIndustry)}
                  >
                    {industries.map((item) => (
                      <option key={item} value={item}>
                        {t.industries[item]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-white">{t.language}</span>
                  <select
                    className="h-11 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none focus:border-cyan/60"
                    value={language}
                    onChange={(event) => setLanguage(event.target.value as "zh" | "en")}
                  >
                    <option value="zh">中文</option>
                    <option value="en">English</option>
                  </select>
                </label>
              </div>

              <p className="rounded-md border border-amber-300/15 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">{t.fallback}</p>
              <button
                type="button"
                disabled={loading}
                onClick={handleAnalyze}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-cyan px-5 text-sm font-semibold text-ink transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? <Loader2 className="animate-spin" size={18} /> : <WandSparkles size={18} />}
                {loading ? t.analyzing : t.start}
              </button>
              {error ? <p className="rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">{error}</p> : null}
            </div>
          </div>
        </section>

        <section className="space-y-5">
          {!result ? (
            <div className="grid min-h-[560px] place-items-center rounded-lg border border-white/10 bg-panel/60 p-8 text-center shadow-glow">
              <div>
                <Clapperboard className="mx-auto text-cyan" size={34} />
                <h2 className="mt-4 text-xl font-semibold text-white">{t.rewrites}</h2>
                <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{t.subtitle}</p>
              </div>
            </div>
          ) : (
            <>
              {result.quota ? (
                <p className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-400">
                  {t.quota}: {result.quota.monthly_limit === null ? `${result.quota.used} / ${t.quotaCustom}` : `${result.quota.used} / ${result.quota.monthly_limit}`}
                </p>
              ) : null}
              <ResultCard title={t.topic}>{result.topic}</ResultCard>
              <ResultCard title={t.hook}>{result.hook}</ResultCard>
              <ListCard title={t.sellingPoints} items={result.selling_points} />
              <ListCard title={t.structure} items={result.structure} />
              <ResultCard title={t.template}>{result.template}</ResultCard>

              <div className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
                <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
                <div className="mt-4 grid gap-4">
                  {result.rewrites.map((rewrite, index) => (
                    <article key={`${rewrite.title}-${index}`} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-base font-semibold text-cyan">{rewrite.title}</h3>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => copyScript(rewrite.script, index)}
                            className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
                          >
                            {copiedIndex === index ? <Check size={14} /> : <Copy size={14} />}
                            {copiedIndex === index ? t.copied : t.copy}
                          </button>
                          <Link
                            className="inline-flex h-9 items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                            href={`/studio/avatar?script_text=${encodeURIComponent(rewrite.script)}`}
                          >
                            {t.generate}
                            <ArrowRight size={14} />
                          </Link>
                        </div>
                      </div>
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-300">{rewrite.script}</p>
                    </article>
                  ))}
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function hasVisibleVideoUrl(input: string): boolean {
  return VISIBLE_VIDEO_URL_RE.test(input);
}

async function runPipelineWithTimeout(
  payload: {
    source_url: string;
    industry: ViralIndustry;
    language: "zh" | "en";
  },
  accessToken: string,
  fallbackMessage: string,
): Promise<ViralPipelineResult> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), LINK_PIPELINE_TIMEOUT_MS);
  try {
    return await runViralPipeline(payload, accessToken, { signal: controller.signal });
  } catch {
    throw new Error(fallbackMessage);
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function mapPipelineResult(payload: ViralPipelineResult, fallbackMessage: string): ViralAnalyzeResult {
  if (!payload.ok || !payload.analysis) {
    throw new Error(fallbackMessage);
  }
  return {
    project_id: payload.project_id || undefined,
    topic: payload.analysis.topic,
    hook: payload.analysis.hook,
    selling_points: payload.analysis.selling_points,
    structure: payload.analysis.structure,
    template: payload.analysis.template,
    rewrites: payload.rewrites,
  };
}

function ResultCard({ title, children }: { title: string; children: string }) {
  return (
    <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <p className="mt-3 text-sm leading-7 text-slate-300">{children}</p>
    </section>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item} className="rounded-md border border-white/10 bg-white/[0.035] px-3 py-2 text-sm text-slate-300">
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}
