"use client";

import { Check, Copy, Download, Film, Loader2, Trash2, UploadCloud, Video } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";
import {
  buildTemplateGenerateRequest,
  deriveAvatarGenerationCapabilities,
  getAvatarGenerationAction,
  getAvatarGenerationButtonLabelKey,
  parsePreviewTtsReadyResponse,
  type AvatarGenerationCapabilities,
} from "@/lib/avatarGenerationReadiness";
import { avatarTemplates } from "@/lib/avatarTemplates";
import { avatarVoiceGroups, avatarVoiceOptions, DEFAULT_AVATAR_VOICE_KEY, getAvatarVoiceLanguage, type AvatarVoiceKey } from "@/lib/avatarVoiceOptions";
import { isPreviewEnvironment } from "@/lib/runtimeEnvironment";
import { createClient } from "@/lib/supabase/client";
import type { UsageSummary } from "@/lib/types";

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
  video_generation?: {
    status?: string;
  };
  preview_tts_only?: {
    status?: string;
  };
  musetalk?: {
    status?: string;
    message?: string;
    status_code?: number;
  };
};
type DeleteTaskError = Error & { status?: number };

const EMPTY_CAPABILITIES: AvatarGenerationCapabilities = {
  previewSafeMode: false,
  previewTtsOnlyReady: false,
  videoGenerationReady: false,
};
const TTS_SPEED_OPTIONS = [
  { value: 0.9, label: { zh: "舒缓", en: "Relaxed" } },
  { value: 1, label: { zh: "标准", en: "Standard" } },
  { value: 1.1, label: { zh: "稍快", en: "Slightly faster" } },
];

const copy = {
  zh: {
    title: "基础数字人口播",
    subtitle: "选择模板、音色和语速，将文案生成口播视频。适合产品讲解、知识分享和短视频内容制作。",
    template: "数字人模板",
    templateHint: "选择本次出镜的商务数字人。",
    video: "使用自拍视频作为口播模板",
    script: "口播文案",
    audio: "口播音频",
    videoHint: "建议上传单人正脸、光线均匀、画面稳定且嘴部无遮挡的视频。",
    scriptHint: "输入文案后，系统会生成语音、驱动数字人，并默认添加中文字幕。",
    scriptLengthHint: "建议文案时长 15–60 秒。标准语速通常能获得更稳定的口型效果。",
    scriptPlaceholder: "输入要数字人口播的文案...",
    audioHint: "上传音频后，将优先使用你的音频；未上传音频时会自动生成语音。支持 wav / mp3 / m4a。",
    ttsLanguage: "配音语言",
    ttsLanguageHint: "语言选择只影响配音音色，不会自动翻译文案；默认中文流程不变。",
    ttsVoice: "配音音色",
    ttsVoiceHint: "仅展示当前明确开放的音色。",
    englishVoiceUnavailable: "英文配音音色尚未配置，请先使用中文普通话。",
    ttsPreview: "试听配音",
    ttsPreviewGenerating: "试听生成中",
    ttsPreviewFailed: "试听生成失败",
    ttsPreviewReady: "试听音频已生成",
    unsupportedTtsVoice: "当前语言暂无可用音色。",
    comingSoon: "即将上线",
    realismTitle: "真实度建议",
    realismVideoTips: ["正脸出镜", "1080p 或更高", "光线稳定", "背景干净", "脸部占画面足够大", "头部动作不要太大"],
    realismScriptTips: ["句子不要太长", "多用标点制造自然停顿", "15-60 秒更稳", "语速不要太快"],
    ttsSpeed: "TTS 语速",
    ttsSpeedHint: "推荐使用标准语速，过快或过慢可能影响口型自然度。",
    steps: ["选择商务模板", "输入口播文案", "生成并下载 MP4"],
    generate: "生成口播视频",
    generating: "生成中",
    previewTtsGenerate: "生成语音预览",
    previewTtsGenerating: "正在生成语音预览",
    previewTtsReady: "语音预览已生成。",
    previewTtsUnavailable: "语音服务未就绪",
    previewTtsHealthReady: "Preview 语音服务已就绪，视频生成保持禁用。",
    previewTtsHealthUnavailable: "Preview 语音服务暂未就绪。",
    previewMediaBlocked: "Preview 语音模式不支持上传视频或使用已有音频。",
    downloadAudio: "下载 MP3",
    login: "登录状态已失效，请重新登录后再试。",
    waitingGpu: "正在检查生成服务",
    autodlStarting: "正在准备生成服务",
    musetalkLoading: "正在准备视频",
    videoGenerating: "正在生成口播视频",
    uploadingResult: "正在处理成片",
    queued: "排队中",
    running: "生成中",
    completed: "已完成",
    failed: "失败",
    download: "下载 MP4",
    copyLink: "复制链接",
    copied: "已复制",
    result: "生成结果",
    resultReady: "视频已生成。",
    subtitleBurned: "已添加中文字幕",
    subtitleFallbackOriginal: "字幕处理失败，已保留原视频",
    subtitleDisabled: "未开启字幕",
    subtitleUnknown: "",
    preview: "预览",
    empty: "请选择模板并输入口播文案。",
    quotaTitle: "生成额度",
    quotaLoading: "正在读取额度",
    quotaUnlimited: "当前套餐不限额度",
    quotaSummary: (remaining: number, used: number, total: number) => `剩余 ${remaining} 次，本月已用 ${used}/${total} 次`,
    cost: "本次生成预计消耗 1 次额度",
    quotaEmpty: "本月生成次数已用完，请升级套餐或联系管理员。",
    upgrade: "升级套餐",
    healthChecking: "正在检查数字人生成服务状态...",
    healthReady: "数字人生成服务已就绪。",
    healthUnavailable: "视频生成服务暂未就绪，请稍后重新检查。",
    healthRetry: "重新检查服务状态",
    healthCheckingButton: "检查服务中...",
    healthUnavailableButton: "服务未就绪",
    selectedTemplate: "已选择模板",
    templateComingSoon: "该模板视频即将上线，请先手动上传人物视频。",
    history: "最近任务",
    noHistory: "暂无历史任务。",
    deleteTask: "删除",
    deletingTask: "删除中",
    deleteConfirm: "确认删除这条历史任务吗？视频文件不会立即从存储中物理删除。",
    deleteRunning: "任务仍在生成中，暂不能删除。",
    deleteLogin: "请先登录后再删除。",
    deleteNotFound: "任务不存在或已删除。",
    deleteFailed: "删除失败，请稍后重试。",
    autoSubtitle: "自动字幕",
    authExpired: "登录状态已失效，请重新登录后再试。",
    serviceUnavailable: "视频生成服务当前不可用，本次不会扣除生成次数。请稍后重试。",
    languageUnavailable: "英文配音音色尚未配置，请先使用中文普通话。",
    fileUnsupported: "文件格式暂不支持，请上传 MP4/MOV/WebM 视频或 WAV/MP3/M4A 音频。",
    genericError: "生成失败，请稍后重试或联系管理员。",
  },
  en: {
    title: "Avatar Video Generator",
    subtitle: "Choose a template, voice, and speed to turn your script into a talking video.",
    template: "Avatar Template",
    templateHint: "Choose the business presenter for this video.",
    video: "Custom Person Video",
    script: "Voiceover Script",
    audio: "Voice Audio",
    videoHint: "Optional. Upload a custom video to override the selected business template.",
    scriptHint: "Enter a script to synthesize speech, drive the avatar, and add Chinese subtitles by default.",
    scriptLengthHint: "15-60 seconds is recommended. Keep sentences short, use punctuation for natural pauses, and avoid speaking too fast.",
    scriptPlaceholder: "Enter the script for the avatar...",
    audioHint: "Uploaded audio takes priority. Without audio, speech is generated automatically. wav / mp3 / m4a supported.",
    ttsLanguage: "Voice language",
    ttsLanguageHint: "Language only affects the voiceover voice. It does not translate your script. Chinese remains the default.",
    ttsVoice: "Voice",
    ttsVoiceHint: "Choose from clearly grouped Chinese, English, and Japanese voices.",
    englishVoiceUnavailable: "English voiceover is not configured yet. Please use Mandarin Chinese.",
    ttsPreview: "Preview voice",
    ttsPreviewGenerating: "Generating preview",
    ttsPreviewFailed: "Preview failed",
    ttsPreviewReady: "Preview audio is ready",
    unsupportedTtsVoice: "No enabled voices are available for this language.",
    comingSoon: "Coming soon",
    realismTitle: "Realism tips",
    realismVideoTips: ["Front-facing shot", "1080p or higher", "Stable lighting", "Clean background", "Face large enough in frame", "Avoid large head motion"],
    realismScriptTips: ["Keep sentences short", "Use punctuation for pauses", "15-60 seconds is steadier", "Avoid fast delivery"],
    ttsSpeed: "TTS speed",
    ttsSpeedHint: "Applies only to template text-to-speech. Uploaded audio and custom video keep their original rhythm.",
    steps: ["Choose template", "Enter script", "Generate MP4"],
    generate: "Generate Avatar Video",
    generating: "Generating",
    previewTtsGenerate: "Generate voice preview",
    previewTtsGenerating: "Generating voice preview",
    previewTtsReady: "Voice preview is ready.",
    previewTtsUnavailable: "Voice service unavailable",
    previewTtsHealthReady: "Preview voice service is ready. Video generation remains disabled.",
    previewTtsHealthUnavailable: "The Preview voice service is not ready yet.",
    previewMediaBlocked: "Preview voice mode does not accept uploaded video or existing audio.",
    downloadAudio: "Download MP3",
    login: "Your login session expired. Please sign in again and retry.",
    waitingGpu: "Checking generation service",
    autodlStarting: "Preparing generation service",
    musetalkLoading: "Preparing video",
    videoGenerating: "Generating talking video",
    uploadingResult: "Processing final video",
    queued: "Queued",
    running: "Generating",
    completed: "Completed",
    failed: "Failed",
    download: "Download MP4",
    copyLink: "Copy link",
    copied: "Copied",
    result: "Result",
    resultReady: "Video generated.",
    subtitleBurned: "Chinese subtitles added",
    subtitleFallbackOriginal: "Subtitle processing failed; original video preserved",
    subtitleDisabled: "Subtitles not enabled",
    subtitleUnknown: "",
    preview: "Preview",
    empty: "Choose a template and enter a script.",
    quotaTitle: "Generation credits",
    quotaLoading: "Loading credits",
    quotaUnlimited: "Current plan has custom credits",
    quotaSummary: (remaining: number, used: number, total: number) => `${remaining} left, ${used}/${total} used this month`,
    cost: "This generation costs 1 credit",
    quotaEmpty: "Monthly generations are used up. Please upgrade your plan or contact an administrator.",
    upgrade: "Upgrade",
    healthChecking: "Checking avatar generation service...",
    healthReady: "Avatar generation service is ready.",
    healthUnavailable: "The video generation service is not ready yet. Please check again shortly.",
    healthRetry: "Recheck service status",
    healthCheckingButton: "Checking service...",
    healthUnavailableButton: "Service unavailable",
    selectedTemplate: "Selected template",
    templateComingSoon: "This template video is coming soon. Upload a person video for now.",
    history: "Recent tasks",
    noHistory: "No recent tasks.",
    deleteTask: "Delete",
    deletingTask: "Deleting",
    deleteConfirm: "Delete this history task? The video file will not be physically removed from storage immediately.",
    deleteRunning: "This task is still generating and cannot be deleted yet.",
    deleteLogin: "Please sign in before deleting.",
    deleteNotFound: "This task does not exist or was already deleted.",
    deleteFailed: "Delete failed. Please retry later.",
    autoSubtitle: "Auto subtitles",
    authExpired: "Your login session expired. Please sign in again and retry.",
    serviceUnavailable: "The video generation service is unavailable. Failed generations do not use a credit.",
    languageUnavailable: "English voiceover is not configured yet. Please use Mandarin Chinese.",
    fileUnsupported: "This file format is not supported. Upload MP4/MOV/WebM video or WAV/MP3/M4A audio.",
    genericError: "Generation failed. Please retry later or contact an administrator.",
  },
};

export function AvatarVideoGenerator({
  initialTemplateId,
  initialScriptText = "",
}: {
  initialTemplateId?: string;
  initialScriptText?: string;
}) {
  const { locale } = useLanguage();
  const current = copy[locale === "zh" ? "zh" : "en"];
  const supabase = useMemo(() => createClient(), []);
  const initialAvatarTemplate = initialTemplateId && avatarTemplates.some((template) => template.id === initialTemplateId) ? initialTemplateId : "business_female_01";
  const [avatarTemplateId, setAvatarTemplateId] = useState(initialAvatarTemplate);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [scriptText, setScriptText] = useState(initialScriptText);
  const [state, setState] = useState<GenerateState>("idle");
  const [progressStage, setProgressStage] = useState<ProgressStage>("waiting_gpu");
  const [progress, setProgress] = useState(0);
  const [resultUrl, setResultUrl] = useState("");
  const [audioPreviewUrl, setAudioPreviewUrl] = useState("");
  const [resultSubtitleStatus, setResultSubtitleStatus] = useState<AvatarSubtitleStatus>("unknown");
  const [error, setError] = useState("");
  const [selectedVoice, setSelectedVoice] = useState<AvatarVoiceKey>(DEFAULT_AVATAR_VOICE_KEY);
  const ttsLanguage = getAvatarVoiceLanguage(selectedVoice);
  const [ttsSpeedRatio, setTtsSpeedRatio] = useState(1);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [tasks, setTasks] = useState<AvatarTask[]>([]);
  const [copied, setCopied] = useState(false);
  const [avatarHealthStatus, setAvatarHealthStatus] = useState<AvatarHealthStatus>("checking");
  const [generationCapabilities, setGenerationCapabilities] = useState<AvatarGenerationCapabilities>(EMPTY_CAPABILITIES);
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
      const capabilities = deriveAvatarGenerationCapabilities({
        previewEnvironment: isPreviewEnvironment,
        responseOk: response.ok,
        musetalkStatus: payload?.musetalk?.status,
        videoGenerationStatus: payload?.video_generation?.status,
        previewTtsOnlyStatus: payload?.preview_tts_only?.status,
      });
      setGenerationCapabilities(capabilities);
      setAvatarHealthStatus(capabilities.videoGenerationReady ? "ready" : "unavailable");
      setAvatarHealthMessage(
        capabilities.previewSafeMode
          ? capabilities.previewTtsOnlyReady
            ? current.previewTtsHealthReady
            : current.previewTtsHealthUnavailable
          : capabilities.videoGenerationReady
            ? current.healthReady
            : current.healthUnavailable,
      );
    } catch {
      setGenerationCapabilities(EMPTY_CAPABILITIES);
      setAvatarHealthStatus("unavailable");
      setAvatarHealthMessage(current.healthUnavailable);
    } finally {
      setAvatarHealthCheckedAt(new Date());
    }
  }, [current.healthReady, current.healthUnavailable, current.previewTtsHealthReady, current.previewTtsHealthUnavailable]);

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

  const isGenerating = state === "queued" || state === "running";
  const generationAction = getAvatarGenerationAction({
    capabilities: generationCapabilities,
    isGenerating,
    hasText: Boolean(scriptText.trim()),
    hasTemplate: Boolean(avatarTemplateId),
    hasVoice: Boolean(selectedVoice),
    hasVideoFile: Boolean(videoFile),
    hasAudioFile: Boolean(audioFile),
  });
  const isPreviewTtsOnly = generationAction.mode === "preview_tts";

  async function handleGenerate() {
    setError("");
    setResultUrl("");
    setAudioPreviewUrl("");
    setResultSubtitleStatus("unknown");
    setCopied(false);
    if (!generationAction.enabled) {
      setError(
        isPreviewTtsOnly
          ? videoFile || audioFile
            ? current.previewMediaBlocked
            : current.previewTtsHealthUnavailable
          : current.healthUnavailable,
      );
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
      setState(isPreviewTtsOnly ? "running" : "queued");
      setProgressStage("waiting_gpu");
      startProgress();
      if (!isPreviewTtsOnly) {
        scheduleStageUpdates();
        const runningTimer = window.setTimeout(() => {
          setState((value) => (value === "queued" ? "running" : value));
          setProgressStage((value) => (value === "waiting_gpu" ? "autodl_starting" : value));
        }, 400);
        stageTimers.current.push(runningTimer);
      }
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
              formData.set("voice", selectedVoice);
              formData.set("speed_ratio", String(ttsSpeedRatio));
              return formData;
            })(),
          })
        : await fetch(`${API_URL}/api/avatar/template-generate`, {
            method: "POST",
            headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" },
            body: JSON.stringify(
              buildTemplateGenerateRequest({
                avatarTemplateId,
                scriptText: text,
                language: ttsLanguage,
                voice: selectedVoice,
                speedRatio: ttsSpeedRatio,
              }),
            ),
          });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
        throw new Error(detail || current.failed);
      }
      if (isPreviewTtsOnly) {
        const ttsResult = parsePreviewTtsReadyResponse(payload);
        if (!ttsResult) throw new Error(current.genericError);
        setAudioPreviewUrl(ttsResult.audioUrl);
        clearStageUpdates();
        setState("completed");
        setProgressStage("completed");
        stopProgress(100);
        return;
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

  const effectiveHealthStatus = isPreviewTtsOnly
    ? generationCapabilities.previewTtsOnlyReady
      ? "ready"
      : avatarHealthStatus === "checking"
        ? "checking"
        : "unavailable"
    : avatarHealthStatus;
  const isAvatarHealthChecking = effectiveHealthStatus === "checking";
  const isAvatarHealthUnavailable = effectiveHealthStatus === "unavailable";
  const isGenerateDisabled = !generationAction.enabled;
  const generateButtonLabelKey = getAvatarGenerationButtonLabelKey({
    action: generationAction,
    isGenerating,
    healthChecking: isAvatarHealthChecking,
    healthUnavailable: isAvatarHealthUnavailable,
  });
  const generateButtonLabel = {
    generate_video: current.generate,
    generate_preview_tts: current.previewTtsGenerate,
    generating_video: current.generating,
    generating_preview_tts: current.previewTtsGenerating,
    health_checking: current.healthCheckingButton,
    video_unavailable: current.healthUnavailableButton,
    preview_tts_unavailable: current.previewTtsUnavailable,
  }[generateButtonLabelKey];
  const stageText = isPreviewTtsOnly ? "" : getStageLabel(progressStage, current);
  const statusText = isPreviewTtsOnly && isGenerating ? current.previewTtsGenerating : getStatusLabel(state, current);
  const subtitleNotice = getSubtitleNotice(resultSubtitleStatus, current);

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[0.92fr_1.08fr]">
      <section className="space-y-5">
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">
          <Film size={15} />
          {current.title}
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
            effectiveHealthStatus === "ready"
              ? "rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700"
              : effectiveHealthStatus === "checking"
                ? "rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm"
                : "rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p>
              {effectiveHealthStatus === "checking"
                ? current.healthChecking
                : avatarHealthMessage || (effectiveHealthStatus === "ready" ? current.healthReady : current.healthUnavailable)}
            </p>
            {effectiveHealthStatus === "unavailable" ? (
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
                        <Image className="object-cover" src={template.avatar_image} alt={template.name} fill sizes="(max-width: 640px) 100vw, 320px" />
                      )}
                    </div>
                    <div className="space-y-2 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">{template.name}</p>
                          <p className="text-sm font-medium text-blue-700">{template.englishName}</p>
                        </div>
                        {isSelected ? (
                          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-blue-600 text-white">
                            <Check size={14} />
                          </span>
                        ) : null}
                      </div>
                      <p className="text-sm leading-6 text-slate-600">{template.description}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {template.useCases.map((useCase) => (
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
            disabled={isPreviewEnvironment}
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
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <span className="block text-sm font-semibold text-slate-900">{current.ttsVoice}</span>
            <span className="mt-1 block text-sm text-slate-500">{current.ttsVoiceHint}</span>
            <div className="mt-3 space-y-4">
              {avatarVoiceGroups.map((group) => (
                <fieldset key={group.key}>
                  <legend className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">{group.name[locale === "zh" ? "zh" : "en"]}</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {avatarVoiceOptions.filter((option) => option.group === group.key).map((option) => (
                      <label key={option.key} className={`cursor-pointer rounded-md border p-3 transition ${selectedVoice === option.key ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:border-blue-200"}`}>
                        <input className="sr-only" type="radio" name="voice" value={option.key} checked={selectedVoice === option.key} onChange={() => setSelectedVoice(option.key)} />
                        <span className="flex items-center justify-between gap-3">
                          <span className="font-semibold text-slate-900">{option.name[locale === "zh" ? "zh" : "en"]}</span>
                          {option.recommended ? <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-semibold text-white">{locale === "zh" ? "推荐" : "Recommended"}</span> : null}
                        </span>
                        <span className="mt-1 block text-sm text-slate-500">{option.description[locale === "zh" ? "zh" : "en"]}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
          </div>
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
                  {option.label[locale === "zh" ? "zh" : "en"]} ({option.value.toFixed(1)}x)
                </option>
              ))}
            </select>
          </label>
          <FilePicker
            title={current.audio}
            hint={current.audioHint}
            accept="audio/wav,audio/mpeg,audio/mp3,audio/mp4,audio/aac"
            file={audioFile}
            onChange={setAudioFile}
            disabled={isPreviewEnvironment}
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
        <p className="text-xs text-slate-500">{locale === "zh" ? "生成失败不会扣除次数。" : "Failed generations do not use a credit."}</p>
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
          {resultUrl || audioPreviewUrl ? (
            <div className="flex items-center gap-2">
              <button className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" type="button" onClick={() => copyResultLink(audioPreviewUrl || resultUrl)}>
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? current.copied : current.copyLink}
              </button>
              <a className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" href={audioPreviewUrl || resultUrl} download={audioPreviewUrl ? "kaiqiang-preview-voice.mp3" : "kaiqiang-avatar-video.mp4"}>
                <Download size={16} />
                {audioPreviewUrl ? current.downloadAudio : current.download}
              </a>
            </div>
          ) : null}
        </div>
        {resultUrl || audioPreviewUrl ? (
          <p className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {audioPreviewUrl ? current.previewTtsReady : current.resultReady}
            {!audioPreviewUrl && subtitleNotice ? ` ${subtitleNotice}` : ""}
          </p>
        ) : null}
        <div className="grid min-h-[420px] place-items-center overflow-hidden rounded-md bg-slate-100">
          {audioPreviewUrl ? (
            <audio className="w-full max-w-xl" src={audioPreviewUrl} controls preload="metadata" />
          ) : resultUrl ? (
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
  labels: (typeof copy)["zh"];
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

function getStatusLabel(status: GenerateState | AvatarTask["status"], current: (typeof copy)["zh"]) {
  if (status === "queued") return current.queued;
  if (status === "running") return current.running;
  if (status === "completed") return current.completed;
  if (status === "failed") return current.failed;
  return "";
}

function getStageLabel(stage: ProgressStage, current: (typeof copy)["zh"]) {
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

function getSubtitleNotice(status: AvatarSubtitleStatus, current: (typeof copy)["zh"]) {
  if (status === "burned") return current.subtitleBurned;
  if (status === "fallback_original") return current.subtitleFallbackOriginal;
  if (status === "disabled") return current.subtitleDisabled;
  return current.subtitleUnknown;
}

function TipList({ items }: { items: string[] }) {
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
  disabled = false,
}: {
  title: string;
  hint: string;
  accept: string;
  file: File | null;
  onChange: (file: File | null) => void;
  disabled?: boolean;
}) {
  return (
    <label className={`block rounded-lg border border-slate-200 p-4 shadow-sm transition ${disabled ? "cursor-not-allowed bg-slate-50 opacity-70" : "bg-white hover:border-blue-200 hover:bg-blue-50/30"}`}>
      <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
        <UploadCloud size={17} className="text-blue-600" />
        {title}
      </span>
      <span className="mt-1 block text-sm text-slate-500">{hint}</span>
      <input className="mt-3 block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-blue-500 disabled:cursor-not-allowed" type="file" accept={accept} disabled={disabled} onChange={(event) => onChange(event.target.files?.[0] ?? null)} />
      {file ? <span className="mt-2 block truncate text-xs text-slate-500">{file.name}</span> : null}
    </label>
  );
}
