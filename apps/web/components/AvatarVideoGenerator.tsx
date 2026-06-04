"use client";

import { Check, Copy, Download, Film, Loader2, UploadCloud, Video } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ContactActions } from "@/components/ContactActions";
import { useLanguage } from "@/components/LanguageProvider";
import { findAvatarStudioTemplate, sceneLabel } from "@/lib/avatarTemplates";
import { createClient } from "@/lib/supabase/client";
import type { UsageSummary } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type GenerateState = "idle" | "queued" | "running" | "completed" | "failed";
type ProgressStage = "waiting_gpu" | "autodl_starting" | "musetalk_loading" | "video_generating" | "uploading_result" | "completed" | "failed";
type AvatarTask = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress_stage?: string;
  video_url?: string;
  audio_url?: string;
  result_url?: string;
  error_message?: string;
  created_at?: string;
};

const copy = {
  zh: {
    title: "数字人口播生成器",
    subtitle: "上传一段真人视频和一段配音，MuseTalk 会自动生成人像口播视频。",
    video: "人物视频",
    audio: "口播音频",
    videoHint: "支持 mp4 / mov / webm，建议正脸、光线清晰。",
    audioHint: "支持 wav / mp3 / m4a，建议 16kHz 单声道 wav。",
    generate: "生成口播视频",
    generating: "生成中",
    login: "请先登录后再生成。",
    waitingGpu: "等待 GPU",
    autodlStarting: "AutoDL 启动中",
    musetalkLoading: "MuseTalk 加载中",
    videoGenerating: "视频生成中",
    uploadingResult: "上传结果中",
    queued: "queued",
    running: "running",
    completed: "已完成",
    failed: "failed",
    download: "下载 MP4",
    copyLink: "复制链接",
    copied: "已复制",
    result: "生成结果",
    empty: "请选择人物视频和音频。",
    quotaTitle: "生成额度",
    quotaLoading: "正在读取额度",
    quotaUnlimited: "当前套餐不限额度",
    quotaSummary: (remaining: number, used: number, total: number) => `剩余 ${remaining} 次，本月已用 ${used}/${total} 次`,
    cost: "本次生成预计消耗 1 次额度",
    quotaEmpty: "免费额度已用完，请升级套餐。",
    upgrade: "升级套餐",
    supportTitle: "联系支持",
    supportText: "生成遇到问题、需要模板或商务支持，可以直接联系。",
    selectedTemplate: "已选择模板",
    templateComingSoon: "该模板视频即将上线，请先手动上传人物视频。",
    history: "最近任务",
    noHistory: "暂无历史任务。",
    uploadFailedVideo: "视频上传失败",
    uploadFailedAudio: "音频上传失败",
    gpuFailed: "GPU 启动失败",
    musetalkTimeout: "MuseTalk 超时",
    autodlUnreachable: "AutoDL 不可达",
    supabaseFailed: "Supabase 上传失败",
  },
  en: {
    title: "Avatar Video Generator",
    subtitle: "Upload a person video and a voiceover. MuseTalk will generate a talking avatar video.",
    video: "Person Video",
    audio: "Voice Audio",
    videoHint: "mp4 / mov / webm. Use a clear frontal face when possible.",
    audioHint: "wav / mp3 / m4a. 16kHz mono wav is recommended.",
    generate: "Generate Avatar Video",
    generating: "Generating",
    login: "Sign in before generating.",
    waitingGpu: "Waiting for GPU",
    autodlStarting: "Starting AutoDL",
    musetalkLoading: "Loading MuseTalk",
    videoGenerating: "Generating video",
    uploadingResult: "Uploading result",
    queued: "queued",
    running: "running",
    completed: "completed",
    failed: "failed",
    download: "Download MP4",
    copyLink: "Copy link",
    copied: "Copied",
    result: "Result",
    empty: "Choose a person video and an audio file.",
    quotaTitle: "Generation credits",
    quotaLoading: "Loading credits",
    quotaUnlimited: "Current plan has custom credits",
    quotaSummary: (remaining: number, used: number, total: number) => `${remaining} left, ${used}/${total} used this month`,
    cost: "This generation costs 1 credit",
    quotaEmpty: "Free credits are used up. Please upgrade your plan.",
    upgrade: "Upgrade",
    supportTitle: "Contact support",
    supportText: "Reach out for generation issues, templates, or business support.",
    selectedTemplate: "Selected template",
    templateComingSoon: "This template video is coming soon. Upload a person video for now.",
    history: "Recent tasks",
    noHistory: "No recent tasks.",
    uploadFailedVideo: "Video upload failed",
    uploadFailedAudio: "Audio upload failed",
    gpuFailed: "GPU startup failed",
    musetalkTimeout: "MuseTalk timed out",
    autodlUnreachable: "AutoDL unreachable",
    supabaseFailed: "Supabase upload failed",
  },
};

export function AvatarVideoGenerator({ initialTemplateId }: { initialTemplateId?: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];
  const supabase = useMemo(() => createClient(), []);
  const selectedTemplate = useMemo(() => findAvatarStudioTemplate(initialTemplateId), [initialTemplateId]);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [state, setState] = useState<GenerateState>("idle");
  const [progressStage, setProgressStage] = useState<ProgressStage>("waiting_gpu");
  const [progress, setProgress] = useState(0);
  const [resultUrl, setResultUrl] = useState("");
  const [error, setError] = useState("");
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [tasks, setTasks] = useState<AvatarTask[]>([]);
  const [copied, setCopied] = useState(false);
  const progressTimer = useRef<number | null>(null);
  const stageTimers = useRef<number[]>([]);

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
        if (task.status === "completed" && task.result_url) {
          return task.result_url;
        }
        if (task.status === "failed") {
          throw new Error(task.error_message || current.failed);
        }
        await new Promise((resolve) => window.setTimeout(resolve, 5000));
      }
      throw new Error(current.musetalkTimeout);
    },
    [current.failed, current.musetalkTimeout],
  );

  useEffect(() => {
    void refreshTasks();
    void refreshUsage();
    return () => {
      if (progressTimer.current) window.clearInterval(progressTimer.current);
      stageTimers.current.forEach((timer) => window.clearTimeout(timer));
    };
  }, [refreshTasks, refreshUsage]);

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

  async function handleGenerate() {
    setError("");
    setResultUrl("");
    setCopied(false);
    if (!videoFile || !audioFile) {
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

    const formData = new FormData();
    formData.set("video_file", videoFile);
    formData.set("audio_file", audioFile);

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
      const response = await fetch(`${API_URL}/api/avatar/generate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
        throw new Error(detail || current.failed);
      }
      const immediateResult = payload.result_video_url || payload.video_url || payload.task?.result_url || "";
      const taskId = payload.task_id || payload.task?.id;
      const finalUrl = immediateResult || (taskId ? await pollTaskUntilDone(taskId, session.access_token) : "");
      setResultUrl(finalUrl);
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
    if (lower.includes("video") && (lower.includes("upload") || lower.includes("上传"))) return current.uploadFailedVideo;
    if (lower.includes("audio") && (lower.includes("upload") || lower.includes("上传"))) return current.uploadFailedAudio;
    if (lower.includes("gpu") || lower.includes("power_on") || lower.includes("started but")) return current.gpuFailed;
    if (lower.includes("timeout") || lower.includes("timed out")) return current.musetalkTimeout;
    if (lower.includes("autodl") || lower.includes("connection") || lower.includes("connect")) return current.autodlUnreachable;
    if (lower.includes("supabase") || lower.includes("storage") || lower.includes("bucket")) return current.supabaseFailed;
    if (lower.includes("insufficient_credits") || lower.includes("额度已用完")) return current.quotaEmpty;
    return message || current.failed;
  }

  const isGenerating = state === "queued" || state === "running";
  const stageText =
    progressStage === "waiting_gpu"
      ? current.waitingGpu
      : progressStage === "autodl_starting"
        ? current.autodlStarting
        : progressStage === "musetalk_loading"
          ? current.musetalkLoading
        : progressStage === "video_generating"
          ? current.videoGenerating
          : progressStage === "uploading_result"
            ? current.uploadingResult
            : progressStage === "completed"
              ? current.completed
              : progressStage === "failed"
                ? current.failed
                : "";
  const statusText =
    state === "queued"
      ? current.queued
      : state === "running"
        ? current.running
        : state === "completed"
          ? "completed"
          : state === "failed"
            ? "failed"
            : "";

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
        <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3">
            <p className="text-sm font-semibold text-slate-900">{current.supportTitle}</p>
            <p className="mt-1 text-sm leading-6 text-slate-500">{current.supportText}</p>
          </div>
          <ContactActions compact embedded />
        </div>
        {selectedTemplate ? (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-4">
            <p className="text-sm font-semibold text-blue-950">{current.selectedTemplate}</p>
            <p className="mt-1 text-sm text-blue-800">
              {selectedTemplate.name[locale]} · {sceneLabel(selectedTemplate.scene, locale)} · {selectedTemplate.language.toUpperCase()}
            </p>
            {!selectedTemplate.videoUrl ? <p className="mt-2 text-sm text-amber-700">{current.templateComingSoon}</p> : null}
          </div>
        ) : null}
        <div className="grid gap-4">
          <FilePicker
            title={current.video}
            hint={current.videoHint}
            accept="video/mp4,video/quicktime,video/webm"
            file={videoFile}
            onChange={setVideoFile}
          />
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
          disabled={isGenerating}
          onClick={handleGenerate}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-blue-300 sm:w-auto"
        >
          {isGenerating ? <Loader2 className="animate-spin" size={18} /> : <Video size={18} />}
          {isGenerating ? current.generating : current.generate}
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
              <a className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" href={resultUrl} download>
                <Download size={16} />
                {current.download}
              </a>
            </div>
          ) : null}
        </div>
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
              <div key={task.id} className="grid gap-3 rounded-md border border-slate-200 p-3 sm:grid-cols-[96px_1fr]">
                <div className="grid aspect-video place-items-center overflow-hidden rounded bg-slate-100">
                  {task.result_url ? <video className="h-full w-full object-cover" src={task.result_url} muted playsInline /> : <Film size={22} className="text-slate-400" />}
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium text-slate-800">{task.status}</p>
                    <p className="text-xs text-slate-500">{formatDate(task.created_at)}</p>
                  </div>
                  {task.error_message ? <p className="mt-1 line-clamp-2 text-xs text-rose-600">{task.error_message}</p> : null}
                  {task.result_url ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <a className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50" href={task.result_url} target="_blank" rel="noreferrer">
                        <Video size={13} />
                        Preview
                      </a>
                      <a className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50" href={task.result_url} download>
                        <Download size={13} />
                        MP4
                      </a>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function formatDate(value?: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
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
