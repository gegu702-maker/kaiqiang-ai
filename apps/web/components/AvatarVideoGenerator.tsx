"use client";

import { Check, Copy, Download, Film, Loader2, Trash2, UploadCloud, Video } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";
import { avatarTemplates } from "@/lib/avatarTemplates";
import { avatarCopy, avatarTemplateCopy, type AvatarCopy } from "@/lib/i18n/avatar";
import { createClient } from "@/lib/supabase/client";
import type { UsageSummary } from "@/lib/types";
import {
  DEFAULT_DUBBING_LANGUAGE,
  DEFAULT_DUBBING_VOICE,
  dubbingLanguages,
  getDefaultVoiceForLanguage,
  getEnabledDubbingVoices,
  type DubbingLanguage,
  type DubbingLanguageCode,
} from "@/lib/voiceRegistry";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type GenerateState = "idle" | "queued" | "running" | "completed" | "failed";
type AvatarHealthStatus = "checking" | "ready" | "unavailable";
type AvatarSubtitleStatus = "burned" | "fallback_original" | "disabled" | "unknown";
type ProgressStage =
  | "waiting_gpu"
  | "autodl_starting"
  | "musetalk_loading"
  | "gpu_starting"
  | "model_loading"
  | "video_generating"
  | "uploading_result"
  | "completed"
  | "failed";
type AvatarTask = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress_stage?: string;
  video_url?: string;
  audio_url?: string;
  result_url?: string;
  result_video_url?: string;
  subtitle_status?: AvatarSubtitleStatus;
  error_message?: string;
  created_at?: string;
};
type AvatarHealthPayload = {
  status?: string;
  musetalk?: {
    status?: string;
    message?: string;
    status_code?: number;
  };
};
type DeleteTaskError = Error & { status?: number };
type PreviewState = "idle" | "generating" | "completed" | "failed";

const AVATAR_HEALTH_READY_STATUSES = new Set(["ok", "ready", "healthy", "success"]);
const TTS_SPEED_OPTIONS = [
  { value: 0.9, labelKey: "stable" },
  { value: 1, labelKey: "standard" },
  { value: 1.1, labelKey: "faster" },
] as const;

export function AvatarVideoGenerator({
  initialTemplateId,
  initialScriptText = "",
}: {
  initialTemplateId?: string;
  initialScriptText?: string;
}) {
  const { selectedLocale } = useLanguage();
  const current = avatarCopy[selectedLocale] ?? avatarCopy.en;
  const supabase = useMemo(() => createClient(), []);
  const initialAvatarTemplate = avatarTemplates.some((template) => template.id === initialTemplateId) ? initialTemplateId : "business_female_01";
  const [avatarTemplateId, setAvatarTemplateId] = useState(initialAvatarTemplate);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [scriptText, setScriptText] = useState(initialScriptText);
  const [state, setState] = useState<GenerateState>("idle");
  const [progressStage, setProgressStage] = useState<ProgressStage>("waiting_gpu");
  const [progress, setProgress] = useState(0);
  const [resultUrl, setResultUrl] = useState("");
  const [resultSubtitleStatus, setResultSubtitleStatus] = useState<AvatarSubtitleStatus>("unknown");
  const [error, setError] = useState("");
  const [voiceRegistry, setVoiceRegistry] = useState<DubbingLanguage[]>(dubbingLanguages);
  const [ttsLanguage, setTtsLanguage] = useState<DubbingLanguageCode>(DEFAULT_DUBBING_LANGUAGE);
  const [selectedVoiceType, setSelectedVoiceType] = useState<string>(DEFAULT_DUBBING_VOICE);
  const [ttsSpeedRatio, setTtsSpeedRatio] = useState(0.9);
  const enabledVoices = getEnabledDubbingVoices(voiceRegistry, ttsLanguage);
  const [previewState, setPreviewState] = useState<PreviewState>("idle");
  const [previewAudioUrl, setPreviewAudioUrl] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [tasks, setTasks] = useState<AvatarTask[]>([]);
  const [copied, setCopied] = useState(false);
  const [avatarHealthStatus, setAvatarHealthStatus] = useState<AvatarHealthStatus>("checking");
  const [avatarHealthMessage, setAvatarHealthMessage] = useState("");
  const [avatarHealthCheckedAt, setAvatarHealthCheckedAt] = useState<Date | null>(null);
  const progressTimer = useRef<number | null>(null);
  const stageTimers = useRef<number[]>([]);

  const checkAvatarHealth = useCallback(async () => {
    setAvatarHealthStatus("checking");
    setAvatarHealthMessage("");
    try {
      const response = await fetch(`${API_URL}/api/avatar/health`, { cache: "no-store" });
      const payload = (await response.json().catch(() => null)) as AvatarHealthPayload | null;
      const musetalkStatus = String(payload?.musetalk?.status ?? "").trim().toLowerCase();
      const isReady = response.ok && AVATAR_HEALTH_READY_STATUSES.has(musetalkStatus);
      setAvatarHealthStatus(isReady ? "ready" : "unavailable");
      setAvatarHealthMessage(isReady ? current.healthReady : current.healthUnavailable);
    } catch {
      setAvatarHealthStatus("unavailable");
      setAvatarHealthMessage(current.healthUnavailable);
    } finally {
      setAvatarHealthCheckedAt(new Date());
    }
  }, [current.healthReady, current.healthUnavailable]);

  const refreshTasks = useCallback(async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    const response = await fetch(`${API_URL}/api/avatar/tasks`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    if (!response.ok) return;
    const payload = (await response.json().catch(() => [])) as AvatarTask[];
    setTasks(Array.isArray(payload) ? payload : []);
  }, [supabase]);

  const refreshUsage = useCallback(async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    const response = await fetch(`${API_URL}/api/billing/usage`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    if (!response.ok) return;
    const payload = (await response.json().catch(() => null)) as UsageSummary | null;
    setUsage(payload);
  }, [supabase]);

  const pollTaskUntilDone = useCallback(
    async (taskId: string, token: string) => {
      const deadline = Date.now() + 25 * 60 * 1000;
      while (Date.now() < deadline) {
        const response = await fetch(`${API_URL}/api/avatar/tasks/${taskId}`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(current.failed);
        }
        const task = (await response.json()) as AvatarTask;
        setState(task.status === "queued" ? "queued" : task.status === "running" ? "running" : task.status);
        if (task.progress_stage) setProgressStage(task.progress_stage as ProgressStage);
        const taskResultUrl = task.result_video_url || task.result_url;
        if (task.status === "completed" && taskResultUrl) {
          return { url: taskResultUrl, subtitleStatus: normalizeSubtitleStatus(task.subtitle_status) };
        }
        if (task.status === "failed") {
          throw new Error(task.error_message || current.failed);
        }
        await new Promise((resolve) => window.setTimeout(resolve, 5000));
      }
      throw new Error(current.serviceUnavailable);
    },
    [current.failed, current.serviceUnavailable],
  );

  useEffect(() => {
    void refreshTasks();
    void refreshUsage();
    void checkAvatarHealth();
    return () => {
      if (progressTimer.current) window.clearInterval(progressTimer.current);
      stageTimers.current.forEach((timer) => window.clearTimeout(timer));
    };
  }, [checkAvatarHealth, refreshTasks, refreshUsage]);

  useEffect(() => {
    let active = true;
    void fetch(`${API_URL}/api/avatar/tts-voices`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!active || !Array.isArray(payload?.languages)) return;
        const languages = payload.languages as DubbingLanguage[];
        setVoiceRegistry(languages);
        const currentLanguage = languages.find((language) => language.code === ttsLanguage && language.enabled);
        const fallbackLanguage = currentLanguage ?? languages.find((language) => language.code === DEFAULT_DUBBING_LANGUAGE && language.enabled) ?? languages.find((language) => language.enabled);
        if (fallbackLanguage) {
          setTtsLanguage(fallbackLanguage.code);
          setSelectedVoiceType(getDefaultVoiceForLanguage(languages, fallbackLanguage.code));
        }
      })
      .catch(() => {
        // The bundled registry keeps the selector usable when the API is unavailable.
      });
    return () => {
      active = false;
    };
  }, [ttsLanguage]);

  function startProgress() {
    setProgress(8);
    progressTimer.current = window.setInterval(() => {
      setProgress((value) => Math.min(value + Math.max(1, Math.round((92 - value) / 10)), 92));
    }, 1800);
  }

  function stopProgress(value: number) {
    if (progressTimer.current) {
      window.clearInterval(progressTimer.current);
      progressTimer.current = null;
    }
    setProgress(value);
  }

  function scheduleStageUpdates() {
    stageTimers.current.forEach((timer) => window.clearTimeout(timer));
    stageTimers.current = [
      window.setTimeout(() => setProgressStage("autodl_starting"), 3000),
      window.setTimeout(() => setProgressStage("musetalk_loading"), 12000),
      window.setTimeout(() => setProgressStage("video_generating"), 36000),
      window.setTimeout(() => setProgressStage("uploading_result"), 90000),
    ];
  }

  function clearStageUpdates() {
    stageTimers.current.forEach((timer) => window.clearTimeout(timer));
    stageTimers.current = [];
  }

  function handleTtsLanguageChange(value: string) {
    const language = value as DubbingLanguageCode;
    setTtsLanguage(language);
    setSelectedVoiceType(getDefaultVoiceForLanguage(voiceRegistry, language));
    setPreviewAudioUrl("");
    setPreviewError("");
    setPreviewState("idle");
  }

  async function handlePreviewAudio() {
    const text = scriptText.trim();
    if (!text || previewState === "generating" || enabledVoices.length === 0) return;
    setPreviewState("generating");
    setPreviewAudioUrl("");
    setPreviewError("");

    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      setPreviewState("failed");
      setPreviewError(current.login);
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/avatar/tts-preview`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          language: ttsLanguage,
          voice: selectedVoiceType,
          speed: ttsSpeedRatio,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
        throw new Error(detail || current.ttsPreviewFailed);
      }
      setPreviewAudioUrl(payload.audio_url || "");
      setPreviewState("completed");
    } catch (err) {
      setPreviewState("failed");
      setPreviewError(err instanceof Error ? err.message : current.ttsPreviewFailed);
    }
  }

  async function handleGenerate() {
    setError("");
    setResultUrl("");
    setResultSubtitleStatus("unknown");
    setCopied(false);
    if (avatarHealthStatus !== "ready") {
      setError(current.healthUnavailable);
      return;
    }
    const text = scriptText.trim();
    const useCustomVideo = Boolean(videoFile);
    if ((!useCustomVideo && !text) || (useCustomVideo && !audioFile && !text)) {
      setState("failed");
      setProgressStage("failed");
      setError(current.empty);
      return;
    }
    if (usage?.remaining !== null && usage?.remaining !== undefined && usage.remaining <= 0) {
      setState("failed");
      setProgressStage("failed");
      setError(current.quotaEmpty);
      return;
    }
    if (!useCustomVideo && enabledVoices.length === 0) {
      setState("failed");
      setProgressStage("failed");
      setError(current.languageUnavailable);
      return;
    }

    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      setState("failed");
      setProgressStage("failed");
      setError(current.login);
      return;
    }

    try {
      setState("queued");
      setProgressStage("waiting_gpu");
      startProgress();
      scheduleStageUpdates();
      const runningTimer = window.setTimeout(() => {
        setState((value) => (value === "queued" ? "running" : value));
        setProgressStage((value) => (value === "waiting_gpu" ? "autodl_starting" : value));
      }, 400);
      stageTimers.current.push(runningTimer);
      const response = useCustomVideo
        ? await fetch(`${API_URL}/api/avatar/generate`, {
            method: "POST",
            headers: { Authorization: `Bearer ${session.access_token}` },
            body: (() => {
              const formData = new FormData();
              formData.set("video_file", videoFile as File);
              if (audioFile) formData.set("audio_file", audioFile);
              if (text) formData.set("script_text", text);
              formData.set("language", ttsLanguage);
              formData.set("voice", selectedVoiceType);
              formData.set("voice_type", selectedVoiceType);
              formData.set("speed_ratio", String(ttsSpeedRatio));
              return formData;
            })(),
          })
        : await fetch(`${API_URL}/api/avatar/template-generate`, {
            method: "POST",
            headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" },
            body: JSON.stringify({
              avatar_template_id: avatarTemplateId,
              script_text: text,
              language: ttsLanguage,
              voice: selectedVoiceType,
              voice_type: selectedVoiceType,
              speed_ratio: ttsSpeedRatio,
            }),
          });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
        throw new Error(detail || current.failed);
      }
      const immediateResult = payload.result_video_url || payload.video_url || payload.task?.result_video_url || payload.task?.result_url || "";
      const taskId = payload.task_id || payload.task?.id;
      const immediateSubtitleStatus = normalizeSubtitleStatus(payload.subtitle_status || payload.task?.subtitle_status);
      const finalResult = immediateResult
        ? { url: immediateResult, subtitleStatus: immediateSubtitleStatus }
        : taskId
          ? await pollTaskUntilDone(taskId, session.access_token)
          : { url: "", subtitleStatus: "unknown" as AvatarSubtitleStatus };
      setResultUrl(finalResult.url);
      setResultSubtitleStatus(finalResult.subtitleStatus);
      clearStageUpdates();
      setState("completed");
      setProgressStage("completed");
      stopProgress(100);
      await refreshTasks();
      await refreshUsage();
    } catch (err) {
      clearStageUpdates();
      setState("failed");
      setProgressStage("failed");
      stopProgress(0);
      setError(classifyError(err instanceof Error ? err.message : String(err)));
      await refreshTasks();
      await refreshUsage();
    }
  }

  async function copyResultLink(url: string) {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function classifyError(message: string) {
    const lower = message.toLowerCase();
    if (lower.includes("quota") || lower.includes("insufficient") || lower.includes("limit") || lower.includes("exceeded") || lower.includes("额度已用完")) {
      return current.quotaEmpty;
    }
    if (lower.includes("login") || lower.includes("unauthorized") || lower.includes("auth") || lower.includes("token")) {
      return current.authExpired;
    }
    if (lower.includes("autodl") || lower.includes("musetalk") || lower.includes("gpu") || lower.includes("health") || lower.includes("timeout") || lower.includes("timed out")) {
      return current.serviceUnavailable;
    }
    if (lower.includes("unsupported") || lower.includes("file format") || lower.includes("invalid file") || lower.includes("format") || lower.includes("content type")) {
      return current.fileUnsupported;
    }
    return current.genericError;
  }

  async function handleDeleteTask(taskId: string) {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      const error = new Error(current.deleteLogin) as DeleteTaskError;
      error.status = 401;
      throw error;
    }
    const response = await fetch(`${API_URL}/api/avatar/tasks/${taskId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      const error = new Error(current.deleteFailed) as DeleteTaskError;
      error.status = response.status;
      throw error;
    }
    setTasks((items) => items.filter((item) => item.id !== taskId));
  }

  const isGenerating = state === "queued" || state === "running";
  const isAvatarHealthChecking = avatarHealthStatus === "checking";
  const isAvatarHealthUnavailable = avatarHealthStatus === "unavailable";
  const isGenerateDisabled = isGenerating || avatarHealthStatus !== "ready";
  const generateButtonLabel = isGenerating
    ? current.generating
    : isAvatarHealthChecking
      ? current.healthCheckingButton
      : isAvatarHealthUnavailable
        ? current.healthUnavailableButton
        : current.generate;
  const stageText = getStageLabel(progressStage, current);
  const statusText = getStatusLabel(state, current);
  const subtitleNotice = getSubtitleNotice(resultSubtitleStatus, current);

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[0.92fr_1.08fr]">
      <section className="space-y-5">
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">
          <Film size={15} />
          MuseTalk
        </div>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.title}</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">{current.subtitle}</p>
        </div>
        <div className="rounded-md border border-blue-100 bg-blue-50/70 p-4">
          <h2 className="text-sm font-semibold text-slate-900">{current.realismTitle}</h2>
          <div className="mt-3 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
            <TipList items={current.realismVideoTips} />
            <TipList items={current.realismScriptTips} />
          </div>
        </div>
        <div className="grid gap-2 rounded-md border border-slate-200 bg-white p-3 shadow-sm sm:grid-cols-3">
          {current.steps.map((step, index) => (
            <div key={step} className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-blue-600 text-xs text-white">{index + 1}</span>
              {step}
            </div>
          ))}
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">{current.quotaTitle}</p>
              <p className="mt-1 text-sm text-slate-500">
                {!usage
                  ? current.quotaLoading
                  : usage.remaining === null
                    ? current.quotaUnlimited
                    : current.quotaSummary(usage.remaining, usage.used, usage.monthly_quota ?? 0)}
              </p>
              <p className="mt-1 text-xs text-slate-400">{current.cost}</p>
            </div>
            {usage?.remaining !== null && usage?.remaining !== undefined && usage.remaining <= 0 ? (
              <Link className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500" href="/pricing">
                {current.upgrade}
              </Link>
            ) : null}
          </div>
        </div>
        <div
          data-checked-at={avatarHealthCheckedAt?.toISOString()}
          className={
            avatarHealthStatus === "ready"
              ? "rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700"
              : avatarHealthStatus === "checking"
                ? "rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm"
                : "rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p>
              {avatarHealthStatus === "checking"
                ? current.healthChecking
                : avatarHealthMessage || (avatarHealthStatus === "ready" ? current.healthReady : current.healthUnavailable)}
            </p>
            {avatarHealthStatus === "unavailable" ? (
              <button
                type="button"
                onClick={() => void checkAvatarHealth()}
                className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-800 transition hover:bg-amber-100"
              >
                {current.healthRetry}
              </button>
            ) : null}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-slate-900">{current.template}</h2>
            <p className="mt-1 text-sm text-slate-500">{current.templateHint}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {avatarTemplates.map((template) => {
              const isSelected = avatarTemplateId === template.id;
              const templateCopy = avatarTemplateCopy[template.id as keyof typeof avatarTemplateCopy]?.[selectedLocale];
              const templateName = templateCopy?.name ?? template.name;
              const templateSecondary = templateCopy?.secondary ?? template.englishName;
              const templateDescription = templateCopy?.description ?? template.description;
              const templateUseCases = templateCopy?.useCases ?? template.useCases;
              return (
                <label key={template.id} className="cursor-pointer">
                  <input
                    type="radio"
                    name="avatar_template_id"
                    value={template.id}
                    checked={isSelected}
                    onChange={() => setAvatarTemplateId(template.id)}
                    className="sr-only"
                  />
                  <div className={`h-full overflow-hidden rounded-md border transition ${isSelected ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-white hover:border-blue-200"}`}>
                    <div className="aspect-video overflow-hidden bg-slate-100">
                      {template.preview_video_url ? (
                        <video className="h-full w-full object-cover" src={template.preview_video_url} poster={template.avatar_image} muted loop playsInline autoPlay preload="metadata" />
                      ) : (
                        <Image className="object-cover" src={template.avatar_image} alt={templateName} fill sizes="(max-width: 640px) 100vw, 320px" />
                      )}
                    </div>
                    <div className="space-y-2 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">{templateName}</p>
                          <p className="text-sm font-medium text-blue-700">{templateSecondary}</p>
                        </div>
                        {isSelected ? (
                          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-blue-600 text-white">
                            <Check size={14} />
                          </span>
                        ) : null}
                      </div>
                      <p className="text-sm leading-6 text-slate-600">{templateDescription}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {templateUseCases.map((useCase) => (
                          <span key={useCase} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                            {useCase}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
        <div className="grid gap-4">
          <FilePicker
            title={current.video}
            hint={current.videoHint}
            accept="video/mp4,video/quicktime,video/webm"
            file={videoFile}
            onChange={setVideoFile}
          />
          <label className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition focus-within:border-blue-300 hover:border-blue-200 hover:bg-blue-50/30">
            <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Film size={17} className="text-blue-600" />
              {current.script}
            </span>
            <span className="mt-1 block text-sm text-slate-500">{current.scriptHint}</span>
            <span className="mt-1 block text-xs text-slate-400">{current.scriptLengthHint}</span>
            <textarea
              className="mt-3 min-h-28 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 caret-blue-600 outline-none transition placeholder:text-slate-500 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-700 dark:bg-white dark:text-slate-950 dark:placeholder:text-slate-500"
              maxLength={1200}
              placeholder={current.scriptPlaceholder}
              value={scriptText}
              onChange={(event) => setScriptText(event.target.value)}
            />
          </label>
          <label className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition focus-within:border-blue-300 hover:border-blue-200 hover:bg-blue-50/30">
            <span className="block text-sm font-semibold text-slate-900">{current.ttsLanguage}</span>
            <span className="mt-1 block text-sm text-slate-500">{current.ttsLanguageHint}</span>
            <select
              className="mt-3 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-500"
              value={ttsLanguage}
              disabled={Boolean(videoFile)}
              onChange={(event) => handleTtsLanguageChange(event.target.value)}
            >
              {voiceRegistry.map((option) => (
                <option key={option.code} value={option.code} disabled={!option.enabled}>
                  {option.nativeLabel} / {option.label}
                  {option.comingSoon ? ` (${current.comingSoon})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition focus-within:border-blue-300 hover:border-blue-200 hover:bg-blue-50/30">
            <span className="block text-sm font-semibold text-slate-900">{current.ttsVoice}</span>
            <span className="mt-1 block text-sm text-slate-500">{current.ttsVoiceHint}</span>
            <select
              className="mt-3 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-500"
              value={selectedVoiceType}
              disabled={Boolean(videoFile) || enabledVoices.length === 0}
              onChange={(event) => setSelectedVoiceType(event.target.value)}
            >
              {enabledVoices.length > 0 ? (
                enabledVoices.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label} ({option.id})
                  </option>
                ))
              ) : (
                <option>{current.unsupportedTtsVoice}</option>
              )}
            </select>
            {enabledVoices.length === 0 ? <span className="mt-2 block text-xs text-amber-600">{current.englishVoiceUnavailable}</span> : null}
          </label>
          <label className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition focus-within:border-blue-300 hover:border-blue-200 hover:bg-blue-50/30">
            <span className="block text-sm font-semibold text-slate-900">{current.ttsSpeed}</span>
            <span className="mt-1 block text-sm text-slate-500">{current.ttsSpeedHint}</span>
            <select
              className="mt-3 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-500"
              value={ttsSpeedRatio}
              disabled={Boolean(videoFile)}
              onChange={(event) => setTtsSpeedRatio(Number(event.target.value))}
            >
              {TTS_SPEED_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {current.ttsSpeedOptions[option.labelKey]} ({option.value.toFixed(1)}x)
                </option>
              ))}
            </select>
          </label>
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <button
              type="button"
              disabled={previewState === "generating" || !scriptText.trim() || Boolean(videoFile) || enabledVoices.length === 0}
              onClick={handlePreviewAudio}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-200 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            >
              {previewState === "generating" ? <Loader2 className="animate-spin" size={16} /> : null}
              {previewState === "generating" ? current.ttsPreviewGenerating : current.ttsPreview}
            </button>
            {previewState === "completed" && previewAudioUrl ? <p className="mt-2 text-xs text-emerald-700">{current.ttsPreviewReady}</p> : null}
            {previewError ? <p className="mt-2 rounded-md border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">{previewError}</p> : null}
            {previewAudioUrl ? <audio className="mt-3 w-full" src={previewAudioUrl} controls preload="metadata" /> : null}
          </div>
          <FilePicker
            title={current.audio}
            hint={current.audioHint}
            accept="audio/wav,audio/mpeg,audio/mp3,audio/mp4,audio/aac"
            file={audioFile}
            onChange={setAudioFile}
          />
        </div>
        <button
          type="button"
          disabled={isGenerateDisabled}
          onClick={handleGenerate}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-blue-300 sm:w-auto"
        >
          {isGenerating ? <Loader2 className="animate-spin" size={18} /> : <Video size={18} />}
          {generateButtonLabel}
        </button>
        {statusText ? (
          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-slate-800">{statusText}</span>
              <span className="text-slate-500">{progress}%</span>
            </div>
            {stageText ? <p className="mt-2 text-xs text-slate-500">{stageText}</p> : null}
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
          </div>
        ) : null}
        {error ? <p className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">{current.result}</h2>
          {resultUrl ? (
            <div className="flex items-center gap-2">
              <button className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" type="button" onClick={() => copyResultLink(resultUrl)}>
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? current.copied : current.copyLink}
              </button>
              <a className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" href={resultUrl} download="kaiqiang-avatar-video.mp4">
                <Download size={16} />
                {current.download}
              </a>
            </div>
          ) : null}
        </div>
        {resultUrl ? (
          <p className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {current.resultReady}
            {subtitleNotice ? ` ${subtitleNotice}` : ""}
          </p>
        ) : null}
        <div className="grid min-h-[420px] place-items-center overflow-hidden rounded-md bg-slate-100">
          {resultUrl ? (
            <video className="h-full max-h-[680px] w-full bg-black object-contain" src={resultUrl} controls playsInline />
          ) : (
            <div className="grid place-items-center gap-3 text-center text-slate-500">
              <UploadCloud size={32} />
              <p className="text-sm">{current.subtitle}</p>
            </div>
          )}
        </div>
        <div className="mt-5 border-t border-slate-200 pt-4">
          <h3 className="text-sm font-semibold text-slate-900">{current.history}</h3>
          <div className="mt-3 space-y-3">
            {tasks.length === 0 ? <p className="text-sm text-slate-500">{current.noHistory}</p> : null}
            {tasks.map((task) => (
              <TaskHistoryItem key={task.id} task={task} labels={current} classifyError={classifyError} onDelete={handleDeleteTask} />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function TaskHistoryItem({
  task,
  labels,
  classifyError,
  onDelete,
}: {
  task: AvatarTask;
  labels: AvatarCopy;
  classifyError: (message: string) => string;
  onDelete: (taskId: string) => Promise<void>;
}) {
  const resultUrl = task.result_video_url || task.result_url;
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  async function handleDeleteClick() {
    setDeleteError("");
    if (!window.confirm(labels.deleteConfirm)) return;
    setIsDeleting(true);
    try {
      await onDelete(task.id);
    } catch (error) {
      const status = (error as DeleteTaskError).status;
      if (status === 401) setDeleteError(labels.deleteLogin);
      else if (status === 404) setDeleteError(labels.deleteNotFound);
      else if (status === 409) setDeleteError(labels.deleteRunning);
      else setDeleteError(labels.deleteFailed);
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="grid gap-3 rounded-md border border-slate-200 p-3 sm:grid-cols-[96px_1fr]">
      <div className="grid aspect-video min-h-14 place-items-center overflow-hidden rounded bg-slate-100">
        {resultUrl ? <video className="h-full w-full object-cover" src={resultUrl} muted playsInline /> : <Film size={22} className="text-slate-400" />}
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-slate-800">{getStatusLabel(task.status, labels)}</p>
            {task.status === "completed" && getSubtitleNotice(normalizeSubtitleStatus(task.subtitle_status), labels) ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                {getSubtitleNotice(normalizeSubtitleStatus(task.subtitle_status), labels)}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <p className="text-xs text-slate-500">{formatDate(task.created_at)}</p>
            <button
              type="button"
              disabled={isDeleting}
              onClick={() => void handleDeleteClick()}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              {isDeleting ? labels.deletingTask : labels.deleteTask}
            </button>
          </div>
        </div>
        {task.status === "failed" ? <p className="mt-1 line-clamp-2 text-xs text-rose-600">{classifyError(task.error_message || labels.genericError)}</p> : null}
        {deleteError ? <p className="mt-1 text-xs text-rose-600">{deleteError}</p> : null}
        {resultUrl ? (
          <div className="mt-2 flex flex-wrap gap-2">
            <a className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50" href={resultUrl} target="_blank" rel="noreferrer">
              <Video size={13} />
              {labels.preview}
            </a>
            <a className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50" href={resultUrl} download="kaiqiang-avatar-video.mp4">
              <Download size={13} />
              MP4
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function formatDate(value?: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function getStatusLabel(status: GenerateState | AvatarTask["status"], current: AvatarCopy) {
  if (status === "queued") return current.queued;
  if (status === "running") return current.running;
  if (status === "completed") return current.completed;
  if (status === "failed") return current.failed;
  return "";
}

function getStageLabel(stage: ProgressStage, current: AvatarCopy) {
  if (stage === "waiting_gpu") return current.waitingGpu;
  if (stage === "autodl_starting" || stage === "gpu_starting") return current.autodlStarting;
  if (stage === "musetalk_loading" || stage === "model_loading") return current.musetalkLoading;
  if (stage === "video_generating") return current.videoGenerating;
  if (stage === "uploading_result") return current.uploadingResult;
  if (stage === "completed") return current.completed;
  if (stage === "failed") return current.failed;
  return "";
}

function normalizeSubtitleStatus(status?: string): AvatarSubtitleStatus {
  if (status === "burned" || status === "fallback_original" || status === "disabled") return status;
  return "unknown";
}

function getSubtitleNotice(status: AvatarSubtitleStatus, current: AvatarCopy) {
  if (status === "burned") return current.subtitleBurned;
  if (status === "fallback_original") return current.subtitleFallbackOriginal;
  if (status === "disabled") return current.subtitleDisabled;
  return current.subtitleUnknown;
}

function TipList({ items }: { items: readonly string[] }) {
  return (
    <ul className="grid gap-1.5">
      {items.map((item) => (
        <li key={item} className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-blue-500" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function FilePicker({
  title,
  hint,
  accept,
  file,
  onChange,
}: {
  title: string;
  hint: string;
  accept: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <label className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-200 hover:bg-blue-50/30">
      <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
        <UploadCloud size={17} className="text-blue-600" />
        {title}
      </span>
      <span className="mt-1 block text-sm text-slate-500">{hint}</span>
      <input className="mt-3 block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-blue-500" type="file" accept={accept} onChange={(event) => onChange(event.target.files?.[0] ?? null)} />
      {file ? <span className="mt-2 block truncate text-xs text-slate-500">{file.name}</span> : null}
    </label>
  );
}
