"use client";

import { ArrowRight, Check, Clapperboard, Copy, FileText, LinkIcon, Loader2, Sparkles, UploadCloud, WandSparkles } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { analyzeViralScript, checkVideoLink, continueReviewedViralPipeline, runUploadedViralPipeline, runViralPipeline, type ViralUploadProgress } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { ViralAnalyzeResult, ViralIndustry, ViralLinkErrorCode, ViralPipelineResult, VideoLinkResolveResult } from "@/lib/types";

type Locale = "zh" | "en";

export type ViralAnalyzerWorkflowState = {
  hasLink: boolean;
  hasAnalysis: boolean;
  hasRewrites: boolean;
};

export type SelectedViralScript = {
  title: string;
  script: string;
};

const SUPPORTED_LOCALES: Array<{ code: Locale; label: string }> = [
  { code: "zh", label: "中文" },
  { code: "en", label: "英文" },
];

const industries: Array<{ value: ViralIndustry; labels: Record<Locale, string> }> = [
  { value: "ecommerce", labels: { zh: "电商带货", en: "E-commerce" } },
  { value: "knowledge", labels: { zh: "知识口播", en: "Knowledge" } },
  { value: "training", labels: { zh: "企业培训", en: "Training" } },
  { value: "local", labels: { zh: "本地生活", en: "Local services" } },
  { value: "personal_brand", labels: { zh: "个人IP", en: "Personal brand" } },
  { value: "global", labels: { zh: "出海营销", en: "Global marketing" } },
];
const URL_RE = /https?:\/\/[^\s"'<>，。；、]+/i;

const analyzerCopy: Record<
  Locale,
  {
    eyebrow: string;
    title: string;
    subtitle: string;
    url: string;
    rawScript: string;
    upload: string;
    uploadHint: string;
    industry: string;
    language: string;
    start: string;
    analyzing: string;
    failedError: string;
    linkPlaceholder: string;
    scriptPlaceholder: string;
    fallback: string;
    topic: string;
    hook: string;
    sellingPoints: string;
    structure: string;
    template: string;
    rewrites: string;
    copy: string;
    copied: string;
    optimize: string;
    generate: string;
    quota: string;
    customQuota: string;
  }
> = {
  zh: {
    eyebrow: "爆款拆解",
    title: "爆款脚本拆解器",
    subtitle: "粘贴爆款链接或原始文案，AI 自动拆解结构、卖点与改写方向。",
    url: "短视频链接",
    rawScript: "原始视频文案",
    upload: "上传视频文件",
    uploadHint: "如需更完整拆解，可上传视频或补充原文案。",
    industry: "行业/场景",
    language: "输出语言",
    start: "开始拆解",
    analyzing: "拆解中",
    failedError: "拆解失败，请稍后重试。",
    linkPlaceholder: "抖音 / TikTok / YouTube Shorts 链接",
    scriptPlaceholder: "粘贴原视频文案，系统会学习结构并生成原创改写，不会逐字复制。",
    fallback: "优先读取链接；如平台限制下载，将基于链接公开信息先完成初步拆解。",
    topic: "视频核心主题",
    hook: "黄金开头",
    sellingPoints: "爆点拆解",
    structure: "文案结构",
    template: "可复用模板",
    rewrites: "原创改写版本",
    copy: "复制",
    copied: "已复制",
    optimize: "继续优化",
    generate: "使用此文案",
    quota: "本月拆解次数",
    customQuota: "自定义",
  },
  en: {
    eyebrow: "爆款拆解",
    title: "爆款脚本拆解器",
    subtitle: "粘贴爆款链接或原始文案，AI 自动拆解结构、卖点与改写方向。",
    url: "短视频链接",
    rawScript: "原始视频文案",
    upload: "上传视频文件",
    uploadHint: "如需更完整拆解，可上传视频或补充原文案。",
    industry: "行业/场景",
    language: "输出语言",
    start: "开始拆解",
    analyzing: "拆解中",
    failedError: "拆解失败，请稍后重试。",
    linkPlaceholder: "抖音 / TikTok / YouTube Shorts 链接",
    scriptPlaceholder: "粘贴原视频文案，系统会学习结构并生成原创改写，不会逐字复制。",
    fallback: "优先基于链接公开信息完成初步拆解；如可读取视频语音，会进一步增强分析。",
    topic: "视频核心主题",
    hook: "黄金开头",
    sellingPoints: "爆点拆解",
    structure: "文案结构",
    template: "可复用模板",
    rewrites: "原创改写版本",
    copy: "复制",
    copied: "已复制",
    optimize: "继续优化",
    generate: "使用此文案",
    quota: "本月拆解次数",
    customQuota: "自定义",
  },
};

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
    core_points: payload.analysis.core_points,
    arguments: payload.analysis.arguments,
    cases: payload.analysis.cases,
    data_points: payload.analysis.data_points,
    rewrites: payload.rewrites,
  };
}

function SegmentAudioPlayer({ src, start, end }: { src: string; start: number; end: number }) {
  const audioRef = useRef<HTMLAudioElement>(null);

  return (
    <audio
      ref={audioRef}
      className="mt-3 h-9 w-full"
      controls
      preload="metadata"
      src={src}
      onPlay={() => {
        const audio = audioRef.current;
        if (audio && (audio.currentTime < start || audio.currentTime >= end)) audio.currentTime = start;
      }}
      onTimeUpdate={() => {
        const audio = audioRef.current;
        if (audio && audio.currentTime >= end) audio.pause();
      }}
    />
  );
}

export function ViralAnalyzerClient({
  variant = "standalone",
  selectedScript,
  controlPanelFooter,
  onScriptSelect,
  onWorkflowStateChange,
}: {
  variant?: "standalone" | "workspace";
  selectedScript?: SelectedViralScript | null;
  controlPanelFooter?: ReactNode;
  onScriptSelect?: (script: SelectedViralScript) => void;
  onWorkflowStateChange?: (state: ViralAnalyzerWorkflowState) => void;
}) {
  const supabase = useMemo(() => createClient(), []);
  const isWorkspace = variant === "workspace";
  const [language, setLanguage] = useState<Locale>("zh");
  const [industry, setIndustry] = useState<ViralIndustry>("ecommerce");
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawScript, setRawScript] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [videoObjectUrl, setVideoObjectUrl] = useState("");
  const [uploadProgress, setUploadProgress] = useState<ViralUploadProgress | null>(null);
  const [rewriteLength, setRewriteLength] = useState<"short" | "medium" | "full">("short");
  const [result, setResult] = useState<ViralAnalyzeResult | null>(null);
  const [linkCheck, setLinkCheck] = useState<VideoLinkResolveResult | null>(null);
  const [pipelineMetadata, setPipelineMetadata] = useState<ViralPipelineResult["metadata"] | null>(null);
  const [pipelineSourceType, setPipelineSourceType] = useState<string>("");
  const [pipelineWarning, setPipelineWarning] = useState("");
  const [fullRewriteAvailable, setFullRewriteAvailable] = useState(true);
  const [pipelineTranscript, setPipelineTranscript] = useState("");
  const [pipelineRawTranscript, setPipelineRawTranscript] = useState("");
  const [pipelineTimeline, setPipelineTimeline] = useState<ViralPipelineResult["timeline"]>([]);
  const [pipelineCorrections, setPipelineCorrections] = useState<ViralPipelineResult["corrections"]>([]);
  const [pipelineReviewSegments, setPipelineReviewSegments] = useState<ViralPipelineResult["review_segments"]>([]);
  const [pipelineRequestId, setPipelineRequestId] = useState("");
  const [reviewContext, setReviewContext] = useState<Record<string, unknown> | null>(null);
  const [reviewToken, setReviewToken] = useState("");
  const [reviewDrafts, setReviewDrafts] = useState<Record<number, string>>({});
  const [reviewConfirmed, setReviewConfirmed] = useState<Record<number, boolean>>({});
  const [continuingReview, setContinuingReview] = useState(false);
  const [pipelineDiagnostics, setPipelineDiagnostics] = useState<ViralPipelineResult["diagnostics"]>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [runStage, setRunStage] = useState<"idle" | "checking" | "uploading" | "processing" | "pipeline" | "manual">("idle");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const t = analyzerCopy[language];
  const linkCheckCopy =
    language === "zh"
      ? {
          checkLink: "检查链接",
          checkingLink: "检查中",
          checkPassed: "链接可识别，可基于公开信息分析。",
          checkFailed: "链接暂时无法自动读取。",
          loginError: "请先登录后再检查链接。",
          pipelineEmpty: "链接已读取，但自动分析暂未返回拆解结果。请粘贴原文案继续分析。",
          redirectOk: "短链跳转：正常",
          redirectFailed: "短链跳转：失败",
          platformUnsupported: "平台：暂不支持",
          platform: "平台",
          pipelineReading: "正在读取视频",
          manualAnalyzing: "正在拆解文案",
        }
      : {
          checkLink: "检查链接",
          checkingLink: "检查中",
          checkPassed: "链接可识别，可基于公开信息分析。",
          checkFailed: "链接暂时无法自动读取。",
          loginError: "请先登录后再检查链接。",
          pipelineEmpty: "链接已读取，但自动分析暂未返回拆解结果。请粘贴原文案继续分析。",
          redirectOk: "短链跳转：正常",
          redirectFailed: "短链跳转：失败",
          platformUnsupported: "平台：暂不支持",
          platform: "平台",
          pipelineReading: "正在读取视频",
          manualAnalyzing: "正在拆解文案",
        };

  useEffect(() => {
    onWorkflowStateChange?.({
      hasLink: Boolean(linkCheck?.ok || pipelineMetadata || result),
      hasAnalysis: Boolean(result),
      hasRewrites: Boolean(result?.rewrites?.length),
    });
  }, [linkCheck, onWorkflowStateChange, pipelineMetadata, result]);

  useEffect(() => () => {
    if (videoObjectUrl) URL.revokeObjectURL(videoObjectUrl);
  }, [videoObjectUrl]);

  function applyPipelineReview(payload: ViralPipelineResult) {
    setPipelineRequestId(payload.request_id || "");
    setReviewContext(payload.review_context || null);
    setReviewToken(payload.review_token || "");
    const drafts: Record<number, string> = {};
    const confirmed: Record<number, boolean> = {};
    for (const item of payload.review_segments || []) {
      if (item.segment_index < 0) continue;
      drafts[item.segment_index] = item.suggested_text || item.text || item.original_text || "";
      confirmed[item.segment_index] = false;
    }
    setReviewDrafts(drafts);
    setReviewConfirmed(confirmed);
  }

  function applyPipelineResult(payload: ViralPipelineResult) {
    setPipelineMetadata(payload.metadata);
    setPipelineSourceType(payload.source_type || "");
    setPipelineWarning(payload.warning || "");
    setFullRewriteAvailable(payload.full_rewrite_available !== false);
    if (payload.full_rewrite_available === false) setRewriteLength("short");
    setPipelineTranscript(payload.transcript || "");
    setPipelineRawTranscript(payload.raw_transcript || "");
    setPipelineTimeline(payload.timeline || []);
    setPipelineCorrections(payload.corrections || []);
    setPipelineReviewSegments(payload.review_segments || []);
    setPipelineDiagnostics(payload.diagnostics);
    applyPipelineReview(payload);
  }

  function friendlyLinkMessage(payload?: Pick<VideoLinkResolveResult, "error_code" | "message" | "fallback_reason"> | null) {
    const code = payload?.error_code as ViralLinkErrorCode | undefined;
    const messages: Record<ViralLinkErrorCode, string> = {
      non_douyin_url: "请输入抖音 / TikTok / YouTube Shorts 链接，或直接上传视频。",
      redirect_failed: "短链跳转失败，请复制完整链接重试，或上传视频继续分析。",
      redirect_timeout: "短链跳转超时，请复制完整链接重试，或上传视频继续分析。",
      metadata_blocked: "链接可识别，但可读取内容不足。请粘贴原文案以获得完整拆解。",
      not_downloadable: "已基于链接公开信息完成初步拆解。由于平台限制，未读取完整视频语音，补充原文案可提升准确度。",
      insufficient_metadata: "链接可识别，但可读取内容不足。请粘贴原文案以获得完整拆解。",
      resolver_timeout: "链接检查超时，请稍后重试，或使用上传/粘贴方式。",
      unknown_error: "链接解析失败，请粘贴原文案继续分析。",
      parse_failed: "链接公开信息暂时不足。如粘贴内容包含分享文案，可直接开始拆解。",
      unsupported_page_structure: "链接公开信息暂时不足。如粘贴内容包含分享文案，可直接开始拆解。",
    };
    if (code) return messages[code];
    return payload?.message || payload?.fallback_reason || linkCheckCopy.checkFailed;
  }

  function friendlyPipelineMessage(
    payload: Pick<ViralPipelineResult, "failed_at" | "error_code" | "code" | "stage" | "message" | "fallback_reason" | "request_id" | "retryable">,
  ) {
    const code = payload.code || payload.error_code || "unknown_error";
    const stage = payload.stage || payload.failed_at || "failed";
    const stageLabels: Record<string, string> = {
      pending: "上传接收失败",
      resolving_link: "链接解析失败",
      downloading_video: "平台视频下载失败",
      extracting_audio: "音频提取失败",
      transcribing: "语音转写失败",
      analyzing: "AI 拆解失败",
      rewriting: "改写生成失败",
      processing: "视频处理失败",
      metadata_fallback: "公开信息拆解失败",
    };
    const codeLabels: Record<string, string> = {
      asr_dependency_missing: "ASR 依赖不可用",
      asr_model_unavailable: "ASR 模型不可用",
      asr_transcription_failed: "ASR 推理失败",
      asr_empty_transcript: "未识别到语音内容",
      transcript_review_required: "转写稿需要人工复核",
      audio_extraction_failed: "音频提取失败",
      media_probe_failed: "视频信息读取失败",
      video_too_long: "视频时长超过上限",
      llm_credentials_missing: "AI 服务凭据缺失",
      llm_timeout: "AI 服务调用超时",
      llm_network_error: "AI 服务网络失败",
      llm_http_error: "AI 服务调用失败",
      llm_rate_limited: "AI 服务请求过于频繁",
      llm_balance_insufficient: "AI 服务余额不足",
      llm_upstream_timeout: "AI 服务上游超时",
      llm_auth_error: "AI 服务凭据无效",
      llm_response_schema_error: "AI 响应结构错误",
      llm_response_parse_failed: "AI 响应格式错误",
      analysis_output_too_short: "AI 改写长度不足",
      pipeline_timeout: "处理超时",
    };
    const title = codeLabels[code] || stageLabels[stage] || "拆解失败";
    const detail = payload.message || payload.fallback_reason || "服务端未返回具体原因。";
    const requestLine = payload.request_id ? `请求 ID：${payload.request_id}` : "";
    const retryLine = payload.retryable === true ? "可重试：是" : payload.retryable === false ? "可重试：否" : "";
    if (
      payload.error_code === "not_downloadable" &&
      (payload.failed_at === "downloading_video" || payload.failed_at === "resolving_link")
    ) {
      return "已基于链接公开信息完成初步拆解。由于平台限制，未读取完整视频语音，补充原文案可提升准确度。";
    }
    return [`${title}（${code} / ${stage}）`, detail, retryLine, requestLine].filter(Boolean).join("\n");
  }

  function friendlyError(error: unknown) {
    const message = error instanceof Error ? error.message : "";
    return message || t.failedError;
  }

  function isPollutedRewrite(script: string) {
    return /可复用模板|可套用模板|模板是|结构是|这个版本适合|建议用户|分析如下|JSON|字段|\+（|\+【|（开头|（痛点|（行动号召|【热点事件】/i.test(script);
  }

  function loadingLabel() {
    if (runStage === "checking") return linkCheckCopy.checkingLink;
    if (runStage === "pipeline") return linkCheckCopy.pipelineReading;
    if (runStage === "uploading") return `正在上传 ${uploadProgress?.percent ?? 0}%`;
    if (runStage === "processing") return "上传完成，正在提取音频、分段 ASR 与分层汇总";
    if (runStage === "manual") return linkCheckCopy.manualAnalyzing;
    return t.analyzing;
  }

  function selectVideoFile(file: File | null) {
    setVideoFile(file);
    setVideoDuration(null);
    setUploadProgress(null);
    setVideoObjectUrl("");
    if (!file) return;
    const objectUrl = URL.createObjectURL(file);
    setVideoObjectUrl(objectUrl);
    const media = document.createElement("video");
    media.preload = "metadata";
    media.onloadedmetadata = () => {
      setVideoDuration(Number.isFinite(media.duration) ? media.duration : null);
    };
    media.onerror = () => setVideoDuration(null);
    media.src = objectUrl;
  }

  function persistReviewAudit(nextConfirmed: Record<number, boolean>, nextDrafts = reviewDrafts) {
    if (!pipelineRequestId || typeof window === "undefined") return;
    const entries = (pipelineReviewSegments || [])
      .filter((item) => item.segment_index >= 0)
      .map((item) => ({
        segment_index: item.segment_index,
        start: item.start ?? 0,
        end: item.end ?? item.start ?? 0,
        original_text: item.original_text || item.text || "",
        corrected_text: nextDrafts[item.segment_index] || "",
        source: "human_review",
        confirmed: Boolean(nextConfirmed[item.segment_index]),
        confirmed_at: nextConfirmed[item.segment_index] ? new Date().toISOString() : null,
      }));
    window.localStorage.setItem(`viral-review:${pipelineRequestId}`, JSON.stringify({ request_id: pipelineRequestId, entries }));
  }

  function confirmReviewSegment(segmentIndex: number) {
    const text = (reviewDrafts[segmentIndex] || "").trim();
    if (!text || text.includes("�")) {
      setError("该片段仍为空或包含 U+FFFD 乱码，请试听并修正后再确认。");
      return;
    }
    setError("");
    const next = { ...reviewConfirmed, [segmentIndex]: true };
    setReviewConfirmed(next);
    persistReviewAudit(next);
  }

  async function handleContinueReview() {
    const confirmable = (pipelineReviewSegments || []).filter((item) => item.segment_index >= 0);
    const hasGlobalFailure = (pipelineReviewSegments || []).some((item) => item.segment_index < 0);
    if (hasGlobalFailure || !reviewContext || !reviewToken) {
      setError("自动校正服务未完整返回，当前复核会话不能继续，请重新上传视频。");
      return;
    }
    if (confirmable.some((item) => !reviewConfirmed[item.segment_index])) {
      setError("请先逐段确认全部待复核片段。");
      return;
    }
    setContinuingReview(true);
    setLoading(true);
    setRunStage("pipeline");
    setError("");
    try {
      const accessToken = await getSessionToken();
      const pipeline = await continueReviewedViralPipeline(
        {
          review_context: reviewContext,
          review_token: reviewToken,
          confirmed_segments: confirmable.map((item) => ({
            segment_index: item.segment_index,
            corrected_text: (reviewDrafts[item.segment_index] || "").trim(),
            confirmed: true,
          })),
          source_url: sourceUrl.trim(),
          industry,
          language,
          rewrite_length: rewriteLength,
        },
        accessToken,
      );
      applyPipelineResult(pipeline);
      if (!pipeline.ok) throw new Error(friendlyPipelineMessage(pipeline));
      const pipelineResult = pipelineToAnalyzeResult(pipeline);
      if (!pipelineResult) throw new Error(linkCheckCopy.pipelineEmpty);
      setResult(pipelineResult);
      persistReviewAudit(
        Object.fromEntries(confirmable.map((item) => [item.segment_index, true])),
        reviewDrafts,
      );
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setContinuingReview(false);
      setLoading(false);
      setRunStage("idle");
      setUploadProgress(null);
    }
  }

  function formatFileSize(bytes: number) {
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
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
    setFullRewriteAvailable(true);
    setPipelineTranscript("");
    setPipelineRawTranscript("");
    setPipelineTimeline([]);
    setPipelineCorrections([]);
    setPipelineReviewSegments([]);
    setPipelineDiagnostics(undefined);
    setChecking(true);
    try {
      const accessToken = await getSessionToken();
      const payload = await checkVideoLink(linkCandidate, accessToken);
      setLinkCheck(payload);
      if (!payload.ok) {
        setError(friendlyLinkMessage(payload));
      }
    } catch (err) {
      setError(friendlyError(err));
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
    setFullRewriteAvailable(true);
    setPipelineTranscript("");
    setPipelineRawTranscript("");
    setPipelineTimeline([]);
    setPipelineCorrections([]);
    setPipelineReviewSegments([]);
    setPipelineDiagnostics(undefined);
    setLoading(true);
    try {
      const accessToken = await getSessionToken();
      const sourceLooksLikeUrl = looksLikeUrl(sourceUrl);
      const scriptLooksLikeUrl = looksLikeUrl(rawScript);
      const hasManualScript = rawScript.trim() && !scriptLooksLikeUrl;
      const linkCandidate = sourceLooksLikeUrl ? sourceUrl : scriptLooksLikeUrl ? rawScript : "";

      if (videoFile) {
        setRunStage("uploading");
        setUploadProgress({ loaded: 0, total: videoFile.size, percent: 0, stage: "uploading" });
        const formData = new FormData();
        formData.set("video_file", videoFile);
        formData.set("source_url", linkCandidate);
        formData.set("industry", industry);
        formData.set("language", language);
        formData.set("rewrite_length", rewriteLength);
        const pipeline = await runUploadedViralPipeline(formData, accessToken, (progress) => {
          setUploadProgress(progress);
          setRunStage(progress.stage);
        });
        applyPipelineResult(pipeline);
        if (!pipeline.ok) throw new Error(friendlyPipelineMessage(pipeline));
        const pipelineResult = pipelineToAnalyzeResult(pipeline);
        if (!pipelineResult) throw new Error(linkCheckCopy.pipelineEmpty);
        setResult(pipelineResult);
        return;
      }

      if (linkCandidate && !hasManualScript) {
        setRunStage("checking");
        const payload = await checkVideoLink(linkCandidate, accessToken);
        setLinkCheck(payload);
        if (!payload.ok && payload.error_code === "non_douyin_url") {
          throw new Error(friendlyLinkMessage(payload));
        }
        setRunStage("pipeline");
        const pipeline = await runViralPipeline(
          {
            source_url: linkCandidate,
            raw_input: sourceUrl.trim() || rawScript.trim() || linkCandidate,
            industry,
            language,
            rewrite_length: rewriteLength,
          },
          accessToken,
        );
        applyPipelineResult(pipeline);
        if (!pipeline.ok) {
          throw new Error(friendlyPipelineMessage(pipeline));
        }
        const pipelineResult = pipelineToAnalyzeResult(pipeline);
        if (!pipelineResult) {
          throw new Error(linkCheckCopy.pipelineEmpty);
        }
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
          rewrite_length: rewriteLength,
        },
        accessToken,
      );
      setResult(payload);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
      setRunStage("idle");
      setUploadProgress(null);
    }
  }

  async function copyScript(script: string, index: number) {
    await navigator.clipboard.writeText(script);
    setCopiedIndex(index);
    window.setTimeout(() => setCopiedIndex(null), 1400);
  }

  async function copyOptimizedScript(script: string, index: number) {
    const optimizedPrompt =
      language === "zh"
        ? `${script}\n\n继续优化方向：开头更强、痛点更具体、转化动作更明确。`
        : `${script}\n\nOptimize direction: stronger hook, sharper pain point, clearer conversion action.`;
    await copyScript(optimizedPrompt, index);
  }

  function handleUseScript(rewrite: SelectedViralScript) {
    onScriptSelect?.(rewrite);
  }

  return (
    <section className={isWorkspace ? "w-full max-w-full overflow-x-hidden text-slate-100" : "min-h-[calc(100vh-86px)] w-full max-w-full overflow-x-hidden bg-ink text-slate-100"}>
      <div
        className={
          isWorkspace
            ? "grid w-full max-w-full grid-cols-1 gap-6 overflow-hidden xl:grid-cols-[420px_minmax(0,1fr)]"
            : "mx-auto grid w-full max-w-7xl gap-6 overflow-hidden px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:py-10"
        }
      >
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
                  maxLength={120000}
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
                  onChange={(event) => selectVideoFile(event.target.files?.[0] ?? null)}
                />
                {videoFile ? (
                  <span className="mt-2 block text-xs leading-5 text-slate-400">
                    <span className="block truncate">{videoFile.name}</span>
                    <span>文件大小：{formatFileSize(videoFile.size)}；视频时长：{videoDuration !== null ? `${videoDuration.toFixed(1)} 秒` : "读取中"}</span>
                  </span>
                ) : null}
                {uploadProgress ? (
                  <div className="mt-3" aria-live="polite">
                    <div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-cyan transition-[width]" style={{ width: `${uploadProgress.percent}%` }} /></div>
                    <p className="mt-1 text-xs text-cyan">{uploadProgress.stage === "uploading" ? `上传进度：${uploadProgress.percent}%` : "上传完成，后端处理中"}</p>
                  </div>
                ) : null}
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-white">改写长度</span>
                <select
                  className="h-11 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none focus:border-cyan/60"
                  value={rewriteLength}
                  onChange={(event) => setRewriteLength(event.target.value as "short" | "medium" | "full")}
                >
                  <option value="short">短版（约 30–60 秒）</option>
                  <option value="medium">中版（约 60–120 秒）</option>
                  <option value="full" disabled={!fullRewriteAvailable}>完整版（尽量保留主要信息）</option>
                </select>
                {!fullRewriteAvailable ? <span className="mt-2 block text-xs leading-5 text-amber-100">当前仅能生成“仅公开信息摘要”，完整版已禁用。请上传视频或粘贴原文。</span> : null}
              </label>

              <div className={isWorkspace ? "grid gap-3" : "grid gap-3 sm:grid-cols-2"}>
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
                {isWorkspace ? null : (
                  <label className="block">
                    <span className="mb-2 block text-sm font-semibold text-white">{t.language}</span>
                    <select
                      className="h-11 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-slate-100 outline-none focus:border-cyan/60"
                      value={language}
                      onChange={(event) => setLanguage(event.target.value as Locale)}
                    >
                      {SUPPORTED_LOCALES.map((item) => (
                        <option key={item.code} value={item.code}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
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
              {error ? <p className="whitespace-pre-wrap rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">{error}</p> : null}
              {pipelineReviewSegments?.length ? (
                <div className="rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
                  <p className="font-semibold">需人工确认的转写片段：{pipelineReviewSegments.length}</p>
                  <div className="mt-3 space-y-4">
                    {pipelineReviewSegments.map((item, index) => (
                      <article key={`${item.segment_index}-${index}`} className="rounded-md border border-amber-100/15 bg-black/15 p-3">
                        <p className="font-semibold">
                          {item.segment_index >= 0 ? `原始分段 #${item.segment_index + 1}` : "校正服务异常"}
                          {item.start !== undefined ? ` · ${item.start.toFixed(1)}–${(item.end ?? item.start).toFixed(1)} 秒` : ""}
                        </p>
                        <p className="mt-1 text-xs text-amber-100/80">{item.reason}</p>
                        {item.segment_index >= 0 ? (
                          <>
                            {videoObjectUrl && item.start !== undefined ? (
                              <SegmentAudioPlayer src={videoObjectUrl} start={item.start} end={item.end ?? item.start + 8} />
                            ) : (
                              <p className="mt-2 text-xs">原本地视频已不可用，请重新选择同一文件后试听；不会自动提交。</p>
                            )}
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <div>
                                <p className="text-xs font-semibold">原始 ASR</p>
                                <p className="mt-1 min-h-20 whitespace-pre-wrap rounded border border-white/10 bg-black/20 p-2 text-amber-50">{item.original_text || item.text || ""}</p>
                              </div>
                              <label>
                                <span className="text-xs font-semibold">建议校正（可编辑）</span>
                                <textarea
                                  className="mt-1 min-h-20 w-full rounded border border-white/10 bg-ink/80 p-2 text-amber-50 outline-none focus:border-cyan/60"
                                  value={reviewDrafts[item.segment_index] ?? item.suggested_text ?? ""}
                                  disabled={Boolean(reviewConfirmed[item.segment_index])}
                                  onChange={(event) => {
                                    const next = { ...reviewDrafts, [item.segment_index]: event.target.value };
                                    setReviewDrafts(next);
                                    persistReviewAudit(reviewConfirmed, next);
                                  }}
                                />
                              </label>
                            </div>
                            <button
                              type="button"
                              className="mt-3 rounded-md border border-amber-100/30 px-3 py-1 text-xs font-semibold disabled:opacity-60"
                              disabled={Boolean(reviewConfirmed[item.segment_index])}
                              onClick={() => confirmReviewSegment(item.segment_index)}
                            >
                              {reviewConfirmed[item.segment_index] ? "已确认" : "确认此段"}
                            </button>
                          </>
                        ) : null}
                      </article>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="mt-4 inline-flex h-10 items-center gap-2 rounded-md bg-cyan px-4 text-sm font-semibold text-ink disabled:opacity-60"
                    disabled={
                      continuingReview ||
                      pipelineReviewSegments.some((item) => item.segment_index < 0) ||
                      pipelineReviewSegments.filter((item) => item.segment_index >= 0).some((item) => !reviewConfirmed[item.segment_index])
                    }
                    onClick={handleContinueReview}
                  >
                    {continuingReview ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
                    全部确认后继续拆解
                  </button>
                  {pipelineTranscript ? <details className="mt-3"><summary className="cursor-pointer font-semibold">查看AI校正稿</summary><p className="mt-2 whitespace-pre-wrap text-amber-50">{pipelineTranscript}</p></details> : null}
                  {pipelineRawTranscript ? <details className="mt-3"><summary className="cursor-pointer font-semibold">查看原始ASR转写</summary><p className="mt-2 whitespace-pre-wrap text-amber-50">{pipelineRawTranscript}</p></details> : null}
                </div>
              ) : null}
            </div>
          </div>
          {isWorkspace && controlPanelFooter ? <div className="space-y-5">{controlPanelFooter}</div> : null}
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
                <p className="rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100 break-words [overflow-wrap:anywhere]">{pipelineWarning}</p>
              ) : null}
              {pipelineMetadata ? (
                <div className="max-w-full overflow-hidden rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm leading-6 text-slate-300">
                  <div className="flex min-w-0 gap-3">
                    {pipelineMetadata.thumbnail ? <Image className="h-16 w-16 rounded-md object-cover" src={pipelineMetadata.thumbnail} alt="" width={64} height={64} unoptimized /> : null}
                    <div className="min-w-0 break-words [overflow-wrap:anywhere]">
                      {pipelineMetadata.title ? <p className="break-words font-semibold text-white [overflow-wrap:anywhere]">{pipelineMetadata.title}</p> : null}
                      <p>平台：{pipelineMetadata.platform || "douyin"}</p>
                      {pipelineMetadata.duration ? <p>时长：{pipelineMetadata.duration}秒</p> : null}
                      <p>文件大小：{videoFile ? formatFileSize(videoFile.size) : "链接模式"}</p>
                      <p>分析来源：{pipelineSourceType === "uploaded_video_asr" ? "上传视频完整音轨" : pipelineSourceType === "link_video_asr" ? "链接视频音轨" : "仅公开信息摘要（非完整拆解）"}</p>
                      <p>视频读取：{pipelineMetadata.downloadable ? "可用" : "受限，当前使用链接公开信息分析"}</p>
                      {pipelineDiagnostics ? <p>视频时长：{pipelineDiagnostics.video_duration_seconds.toFixed(1)} 秒；ASR 覆盖：{pipelineDiagnostics.asr_coverage_seconds.toFixed(1)} 秒；原始转写 {pipelineDiagnostics.raw_transcript_chars ?? pipelineDiagnostics.transcript_chars} 字；校正后 {pipelineDiagnostics.corrected_transcript_chars ?? pipelineDiagnostics.transcript_chars} 字；{pipelineDiagnostics.segment_count} 段；校正 {pipelineDiagnostics.correction_count ?? 0} 处；fallback：{pipelineDiagnostics.fallback ? "是" : "否"}</p> : null}
                    </div>
                  </div>
                </div>
              ) : null}
              {result.quota ? (
                <p className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-400 break-words [overflow-wrap:anywhere]">
                  {t.quota}: {result.quota.monthly_limit === null ? `${result.quota.used} / ${t.customQuota}` : `${result.quota.used} / ${result.quota.monthly_limit}`}
                </p>
              ) : null}
              <ResultCard title={t.topic}>{result.topic}</ResultCard>
              <ResultCard title={t.hook}>{result.hook}</ResultCard>
              <ListCard title={t.sellingPoints} items={result.selling_points} />
              <ListCard title={t.structure} items={result.structure} />
              {result.core_points?.length ? <ListCard title="核心观点" items={result.core_points} /> : null}
              {result.arguments?.length ? <ListCard title="论据与逻辑" items={result.arguments} /> : null}
              {result.cases?.length ? <ListCard title="案例" items={result.cases} /> : null}
              {result.data_points?.length ? <ListCard title="数据" items={result.data_points} /> : null}
              <ResultCard title={t.template}>{result.template}</ResultCard>
              {pipelineTimeline?.length ? <ListCard title="时间轴 / 分段" items={pipelineTimeline.map((item) => `${item.timestamp} ${item.text}`)} /> : null}
              {pipelineTranscript ? (
                <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
                  <h2 className="text-lg font-semibold text-white">自动转写稿（AI校正，建议人工复核）</h2>
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300">{pipelineTranscript}</p>
                  {pipelineCorrections?.length ? (
                    <details className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm text-slate-300">
                      <summary className="cursor-pointer font-semibold text-cyan">查看校正记录（{pipelineCorrections.length}条）</summary>
                      <div className="mt-3 space-y-2">
                        {pipelineCorrections.map((item, index) => <p key={`${item.segment_index}-${index}`}>{item.start !== undefined ? `${item.start.toFixed(1)}秒 ` : ""}{item.from} → {item.to}（{item.reason}）</p>)}
                      </div>
                    </details>
                  ) : null}
                  {pipelineRawTranscript ? (
                    <details className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm text-slate-300">
                      <summary className="cursor-pointer font-semibold text-cyan">查看原始ASR转写</summary>
                      <p className="mt-3 whitespace-pre-wrap leading-7">{pipelineRawTranscript}</p>
                    </details>
                  ) : null}
                </section>
              ) : null}

              <div className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
                <h2 className="text-lg font-semibold text-white">{t.rewrites}</h2>
                <div className="mt-4 grid gap-4">
                  {result.rewrites.map((rewrite, index) => (
                    <article key={`${rewrite.title}-${index}`} className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-white/[0.035] p-4">
                      {(() => {
                        const polluted = isPollutedRewrite(rewrite.script);
                        return (
                          <>
                      <h3 className="break-words text-base font-semibold text-cyan [overflow-wrap:anywhere]">{rewrite.title}</h3>
                      {polluted ? (
                        <p className="mt-3 rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
                          该版本文案格式异常，请点击继续优化或重新生成。
                        </p>
                      ) : (
                        <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300 [overflow-wrap:anywhere]">{rewrite.script}</p>
                      )}
                      <div className="mt-4 flex max-w-full flex-wrap justify-start gap-2 sm:justify-end">
                        <button
                          type="button"
                          onClick={() => copyScript(rewrite.script, index)}
                          className="inline-flex h-9 max-w-full items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
                        >
                          {copiedIndex === index ? <Check size={14} /> : <Copy size={14} />}
                          <span className="truncate">{copiedIndex === index ? t.copied : t.copy}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => copyOptimizedScript(rewrite.script, index)}
                          className="inline-flex h-9 max-w-full items-center gap-2 rounded-md border border-cyan/25 px-3 text-xs font-semibold text-cyan hover:bg-cyan/10"
                        >
                          <WandSparkles size={14} />
                          <span className="truncate">{t.optimize}</span>
                        </button>
                        {isWorkspace ? (
                          <button
                            type="button"
                            onClick={() => handleUseScript(rewrite)}
                            disabled={polluted}
                            className={[
                              "inline-flex h-9 max-w-full items-center gap-2 rounded-md px-3 text-xs font-semibold transition",
                              polluted
                                ? "cursor-not-allowed bg-slate-700 text-slate-400"
                                : selectedScript?.script === rewrite.script
                                  ? "bg-lime text-ink"
                                  : "bg-cyan text-ink hover:bg-cyan/90",
                            ].join(" ")}
                          >
                            <span className="truncate">{selectedScript?.script === rewrite.script ? "已选择" : t.generate}</span>
                            <ArrowRight size={14} />
                          </button>
                        ) : (
                          <Link
                            className="inline-flex h-9 max-w-full items-center gap-2 rounded-md bg-cyan px-3 text-xs font-semibold text-ink hover:bg-cyan/90"
                            href={`/studio/avatar?script_text=${encodeURIComponent(rewrite.script)}`}
                          >
                            <span className="truncate">{t.generate}</span>
                            <ArrowRight size={14} />
                          </Link>
                        )}
                      </div>
                          </>
                        );
                      })()}
                    </article>
                  ))}
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </section>
  );
}

function ResultCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
      <h2 className="break-words text-lg font-semibold text-white [overflow-wrap:anywhere]">{title}</h2>
      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300 [overflow-wrap:anywhere]">{children}</p>
    </section>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
      <h2 className="break-words text-lg font-semibold text-white [overflow-wrap:anywhere]">{title}</h2>
      <div className="mt-3 grid min-w-0 gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item} className="min-w-0 rounded-md border border-white/10 bg-white/[0.035] px-3 py-2 text-sm text-slate-300 break-words [overflow-wrap:anywhere]">
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}
