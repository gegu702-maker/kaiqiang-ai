"use client";

import { ArrowRight, Check, Clapperboard, Copy, FileText, LinkIcon, Loader2, Sparkles, UploadCloud, WandSparkles } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

import { SUPPORTED_LOCALES, type Locale } from "@/components/LanguageProvider";
import { analyzeViralScript, checkVideoLink, runViralPipeline } from "@/lib/api";
import { advancedAnalyzerCopy } from "@/lib/i18n/studio";
import { createClient } from "@/lib/supabase/client";
import type { ViralAnalyzeResult, ViralIndustry, ViralLinkErrorCode, ViralPipelineResult, VideoLinkResolveResult } from "@/lib/types";

const industries: Array<{ value: ViralIndustry; labels: Record<Locale, string> }> = [
  { value: "ecommerce", labels: { zh: "电商带货", en: "E-commerce", ja: "EC販売", ko: "커머스", es: "E-commerce", fr: "E-commerce", ru: "E-commerce" } },
  { value: "knowledge", labels: { zh: "知识口播", en: "Knowledge", ja: "知識解説", ko: "지식 콘텐츠", es: "Conocimiento", fr: "Expertise", ru: "Обучение" } },
  { value: "training", labels: { zh: "企业培训", en: "Training", ja: "企業研修", ko: "기업 교육", es: "Formacion", fr: "Formation", ru: "Тренинг" } },
  { value: "local", labels: { zh: "本地生活", en: "Local services", ja: "ローカルサービス", ko: "로컬 서비스", es: "Servicios locales", fr: "Services locaux", ru: "Локальные услуги" } },
  { value: "personal_brand", labels: { zh: "个人IP", en: "Personal brand", ja: "個人ブランド", ko: "개인 브랜드", es: "Marca personal", fr: "Marque personnelle", ru: "Личный бренд" } },
  { value: "global", labels: { zh: "出海营销", en: "Global marketing", ja: "海外マーケティング", ko: "글로벌 마케팅", es: "Marketing global", fr: "Marketing global", ru: "Глобальный маркетинг" } },
];
const URL_RE = /https?:\/\/[^\s"'<>，。；、]+/i;

function looksLikeUrl(value: string) {
  return URL_RE.test(value.trim());
}

function pipelineToAnalyzeResult(payload: ViralPipelineResult): ViralAnalyzeResult | null {
  if (!payload.analysis) return null;
  return {
    project_id: payload.project_id,
    topic: payload.analysis.topic,
    hook: payload.analysis.hook,
    selling_points: payload.analysis.selling_points,
    structure: payload.analysis.structure,
    template: payload.analysis.template,
    rewrites: payload.rewrites,
  };
}

export function ViralAnalyzerClient() {
  const supabase = useMemo(() => createClient(), []);
  const [language, setLanguage] = useState<Locale>("zh");
  const [industry, setIndustry] = useState<ViralIndustry>("ecommerce");
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawScript, setRawScript] = useState("");
  const [videoFileName, setVideoFileName] = useState("");
  const [result, setResult] = useState<ViralAnalyzeResult | null>(null);
  const [linkCheck, setLinkCheck] = useState<VideoLinkResolveResult | null>(null);
  const [pipelineMetadata, setPipelineMetadata] = useState<ViralPipelineResult["metadata"] | null>(null);
  const [pipelineSourceType, setPipelineSourceType] = useState<string>("");
  const [pipelineWarning, setPipelineWarning] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [runStage, setRunStage] = useState<"idle" | "checking" | "pipeline" | "manual">("idle");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const t = advancedAnalyzerCopy[language];
  const linkCheckCopy =
    language === "zh"
      ? {
          checkLink: "检查链接",
          checkingLink: "检查中",
          checkPassed: "链接可自动读取，可以开始分析。",
          checkFailed: "链接暂时无法自动读取。",
          loginError: "请先登录后再检查链接。",
          pipelineEmpty: "链接已读取，但自动分析暂未返回拆解结果。请上传视频或粘贴原文案继续分析。",
          redirectOk: "短链跳转：正常",
          redirectFailed: "短链跳转：失败",
          platformUnsupported: "平台：暂不支持",
          platform: "平台",
          pipelineReading: "正在读取视频",
          manualAnalyzing: "正在拆解文案",
        }
      : {
          checkLink: "Check link",
          checkingLink: "Checking",
          checkPassed: "This link can be read automatically. You can start analysis.",
          checkFailed: "This link cannot be read automatically right now.",
          loginError: "Please sign in before checking links.",
          pipelineEmpty: "The link was read, but automatic analysis did not return a result. Upload the video or paste the original script to continue.",
          redirectOk: "Redirect: OK",
          redirectFailed: "Redirect: failed",
          platformUnsupported: "Platform: unsupported",
          platform: "Platform",
          pipelineReading: "Reading video",
          manualAnalyzing: "Analyzing script",
        };

  function friendlyLinkMessage(payload?: Pick<VideoLinkResolveResult, "error_code" | "message" | "fallback_reason"> | null) {
    const code = payload?.error_code as ViralLinkErrorCode | undefined;
    const messages: Record<ViralLinkErrorCode, string> = {
      non_douyin_url: "请输入抖音 / TikTok / YouTube Shorts 链接，或直接上传视频。",
      redirect_failed: "短链跳转失败，请复制完整链接重试，或上传视频继续分析。",
      redirect_timeout: "短链跳转超时，请复制完整链接重试，或上传视频继续分析。",
      metadata_blocked: "链接可以识别，但平台可能限制视频读取。如失败，请上传视频或粘贴原文案继续分析。",
      not_downloadable: "链接可以识别，但视频下载受限，请上传视频或粘贴原文案继续分析。",
      insufficient_metadata: "链接可识别，但可读取内容不足。请粘贴原文案或上传视频以获得完整拆解。",
      resolver_timeout: "链接检查超时，请稍后重试，或使用上传/粘贴方式。",
      unknown_error: "链接解析失败，请上传视频或粘贴原文案继续分析。",
      parse_failed: "页面可打开，但未能解析到视频信息，请上传视频或粘贴原文案继续分析。",
      unsupported_page_structure: "页面结构暂不支持自动读取，请上传视频或粘贴原文案继续分析。",
    };
    if (code) return messages[code];
    return payload?.message || payload?.fallback_reason || linkCheckCopy.checkFailed;
  }

  function friendlyPipelineMessage(payload: Pick<ViralPipelineResult, "failed_at" | "error_code" | "message" | "fallback_reason">) {
    if (
      payload.error_code === "not_downloadable" &&
      (payload.failed_at === "downloading_video" || payload.failed_at === "resolving_link")
    ) {
      return "链接可以识别，但视频下载受限，请上传视频或粘贴原文案继续分析。";
    }
    if (payload.failed_at === "transcribing") {
      return "视频读取成功，但语音转文字失败，请上传更清晰的视频或粘贴原文案继续分析。";
    }
    if (payload.failed_at === "analyzing") {
      return "文案提取成功，但拆解失败，请稍后重试或粘贴文案继续分析。";
    }
    return friendlyLinkMessage({
      error_code: payload.error_code,
      message: payload.message,
      fallback_reason: payload.fallback_reason,
    });
  }

  function loadingLabel() {
    if (runStage === "checking") return linkCheckCopy.checkingLink;
    if (runStage === "pipeline") return linkCheckCopy.pipelineReading;
    if (runStage === "manual") return linkCheckCopy.manualAnalyzing;
    return t.analyzing;
  }

  async function getSessionToken() {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      throw new Error(linkCheckCopy.loginError);
    }
    return session.access_token;
  }

  async function handleCheckLink() {
    const linkCandidate = sourceUrl.trim() || rawScript.trim();
    if (!linkCandidate || !looksLikeUrl(linkCandidate)) return;
    setError("");
    setResult(null);
    setLinkCheck(null);
    setPipelineMetadata(null);
    setPipelineSourceType("");
    setPipelineWarning("");
    setChecking(true);
    try {
      const accessToken = await getSessionToken();
      const payload = await checkVideoLink(linkCandidate, accessToken);
      setLinkCheck(payload);
      if (!payload.ok) {
        setError(friendlyLinkMessage(payload));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.failedError);
    } finally {
      setChecking(false);
    }
  }

  async function handleAnalyze() {
    setError("");
    setResult(null);
    setLinkCheck(null);
    setPipelineMetadata(null);
    setPipelineSourceType("");
    setPipelineWarning("");
    setLoading(true);
    try {
      const accessToken = await getSessionToken();
      const sourceLooksLikeUrl = looksLikeUrl(sourceUrl);
      const scriptLooksLikeUrl = looksLikeUrl(rawScript);
      const hasManualScript = rawScript.trim() && !scriptLooksLikeUrl;
      const linkCandidate = sourceLooksLikeUrl ? sourceUrl : scriptLooksLikeUrl ? rawScript : "";

      if (linkCandidate && !hasManualScript) {
        setRunStage("checking");
        const payload = await checkVideoLink(linkCandidate, accessToken);
        setLinkCheck(payload);
        if (!payload.ok) {
          throw new Error(friendlyLinkMessage(payload));
        }
        setRunStage("pipeline");
        const pipeline = await runViralPipeline(
          {
            source_url: linkCandidate,
            industry,
            language,
          },
          accessToken,
        );
        if (!pipeline.ok) {
          throw new Error(friendlyPipelineMessage(pipeline));
        }
        const pipelineResult = pipelineToAnalyzeResult(pipeline);
        if (!pipelineResult) {
          throw new Error(linkCheckCopy.pipelineEmpty);
        }
        setPipelineMetadata(pipeline.metadata);
        setPipelineSourceType(pipeline.source_type || "");
        setPipelineWarning(pipeline.warning || "");
        setResult(pipelineResult);
        return;
      }

      if (!hasManualScript && !linkCandidate) {
        throw new Error("请粘贴短视频链接，或粘贴原始视频文案继续分析。");
      }

      setRunStage("manual");
      const payload = await analyzeViralScript(
        {
          source_url: sourceLooksLikeUrl ? sourceUrl : "",
          raw_script: rawScript,
          industry,
          language,
        },
        accessToken,
      );
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.failedError);
    } finally {
      setLoading(false);
      setRunStage("idle");
    }
  }

  async function copyScript(script: string, index: number) {
    await navigator.clipboard.writeText(script);
    setCopiedIndex(index);
    window.setTimeout(() => setCopiedIndex(null), 1400);
  }

  return (
    <main className="min-h-[calc(100vh-86px)] overflow-x-hidden bg-ink text-slate-100">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:py-10">
        <section className="min-w-0 max-w-full space-y-5 overflow-hidden">
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
                  className="h-11 w-full min-w-0 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan/60"
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
                  className="min-h-44 w-full min-w-0 resize-y rounded-md border border-white/10 bg-ink/70 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan/60"
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
                  className="mt-3 block w-full min-w-0 text-sm text-slate-400 file:mr-4 file:rounded-md file:border-0 file:bg-cyan file:px-4 file:py-2 file:text-sm file:font-semibold file:text-ink hover:file:bg-cyan/90"
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
                      <option key={item.value} value={item.value}>
                        {item.labels[language] ?? item.labels.en}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-white">{t.language}</span>
                  <select
                    className="h-11 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none focus:border-cyan/60"
                    value={language}
                    onChange={(event) => setLanguage(event.target.value as Locale)}
                  >
                    {SUPPORTED_LOCALES.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.nativeName}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <p className="rounded-md border border-amber-300/15 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">{t.fallback}</p>
              <div className="grid gap-3 sm:grid-cols-[auto_1fr]">
                <button
                  type="button"
                  disabled={checking || loading || !looksLikeUrl(sourceUrl || rawScript)}
                  onClick={handleCheckLink}
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-md border border-cyan/30 px-5 text-sm font-semibold text-cyan transition hover:bg-cyan/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {checking ? <Loader2 className="animate-spin" size={18} /> : <LinkIcon size={18} />}
                  {checking ? linkCheckCopy.checkingLink : linkCheckCopy.checkLink}
                </button>
                <button
                  type="button"
                  disabled={loading || checking}
                  onClick={handleAnalyze}
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-cyan px-5 text-sm font-semibold text-ink transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? <Loader2 className="animate-spin" size={18} /> : <WandSparkles size={18} />}
                  {loading ? loadingLabel() : t.start}
                </button>
              </div>
              {linkCheck ? (
                <div className={linkCheck.ok ? "max-w-full overflow-hidden rounded-md border border-lime/20 bg-lime/10 p-3 text-sm leading-6 text-lime" : "max-w-full overflow-hidden rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100"}>
                  <p className="break-words">{linkCheck.ok ? linkCheckCopy.checkPassed : friendlyLinkMessage(linkCheck)}</p>
                  <p className="mt-1 text-xs opacity-80">
                    {linkCheck.redirect_ok === false ? linkCheckCopy.redirectFailed : linkCheckCopy.redirectOk} /{" "}
                    {linkCheck.supported_platform === false ? linkCheckCopy.platformUnsupported : `${linkCheckCopy.platform}: ${linkCheck.platform || "douyin"}`}
                  </p>
                  {linkCheck.ok ? (
                    <div className="mt-3 flex gap-3 text-xs text-lime/85">
                      {linkCheck.thumbnail ? <Image className="h-14 w-14 rounded-md object-cover" src={linkCheck.thumbnail} alt="" width={56} height={56} unoptimized /> : null}
                      <div className="min-w-0 space-y-1">
                        {linkCheck.title ? <p className="truncate font-semibold text-lime">{linkCheck.title}</p> : null}
                        {linkCheck.duration ? <p>时长：{linkCheck.duration}秒</p> : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {error ? <p className="rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">{error}</p> : null}
            </div>
          </div>
        </section>

        <section className="min-w-0 max-w-full space-y-5 overflow-hidden">
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
              {pipelineWarning ? (
                <p className="rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100 break-words">{pipelineWarning}</p>
              ) : null}
              {pipelineMetadata ? (
                <div className="max-w-full overflow-hidden rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm leading-6 text-slate-300">
                  <div className="flex min-w-0 gap-3">
                    {pipelineMetadata.thumbnail ? <Image className="h-16 w-16 rounded-md object-cover" src={pipelineMetadata.thumbnail} alt="" width={64} height={64} unoptimized /> : null}
                    <div className="min-w-0 break-words">
                      {pipelineMetadata.title ? <p className="break-words font-semibold text-white">{pipelineMetadata.title}</p> : null}
                      <p>平台：{pipelineMetadata.platform || "douyin"}</p>
                      {pipelineMetadata.duration ? <p>时长：{pipelineMetadata.duration}秒</p> : null}
                      {pipelineSourceType === "link_metadata_fallback" ? <p>分析来源：链接公开信息</p> : null}
                      <p>视频下载：{pipelineMetadata.downloadable ? "可读取" : "受限"}</p>
                    </div>
                  </div>
                </div>
              ) : null}
              {result.quota ? (
                <p className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-400 break-words">
                  {t.quota}: {result.quota.monthly_limit === null ? `${result.quota.used} / ${t.customQuota}` : `${result.quota.used} / ${result.quota.monthly_limit}`}
                </p>
              ) : null}
              <ResultCard title={t.topic}>{result.topic}</ResultCard>
              <ResultCard title={t.hook}>{result.hook}</ResultCard>
              <ListCard title={t.sellingPoints} items={result.selling_points} />
              <ListCard title={t.structure} items={result.structure} />
              <ResultCard title={t.template}>{result.template}</ResultCard>

              <div className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
                <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
                <div className="mt-4 grid gap-4">
                  {result.rewrites.map((rewrite, index) => (
                    <article key={`${rewrite.title}-${index}`} className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-white/[0.035] p-4">
                      <h3 className="break-words text-base font-semibold text-cyan">{rewrite.title}</h3>
                      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">{rewrite.script}</p>
                      <div className="mt-4 flex max-w-full flex-wrap justify-start gap-2 sm:justify-end">
                        <button
                          type="button"
                          onClick={() => copyScript(rewrite.script, index)}
                          className="inline-flex h-9 max-w-full items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
                        >
                          {copiedIndex === index ? <Check size={14} /> : <Copy size={14} />}
                          <span className="truncate">{copiedIndex === index ? t.copied : t.copy}</span>
                        </button>
                        <Link
                          className="inline-flex h-9 max-w-full items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                          href={`/studio/avatar?script_text=${encodeURIComponent(rewrite.script)}`}
                        >
                          <span className="truncate">{t.generate}</span>
                          <ArrowRight size={14} />
                        </Link>
                      </div>
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

function ResultCard({ title, children }: { title: string; children: string }) {
  return (
    <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
      <h2 className="break-words text-lg font-semibold text-white">{title}</h2>
      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">{children}</p>
    </section>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
      <h2 className="break-words text-lg font-semibold text-white">{title}</h2>
      <div className="mt-3 grid min-w-0 gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item} className="min-w-0 rounded-md border border-white/10 bg-white/[0.035] px-3 py-2 text-sm text-slate-300 break-words">
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}
