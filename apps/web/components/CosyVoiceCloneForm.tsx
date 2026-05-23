"use client";

import { ChangeEvent, FormEvent, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileAudio2,
  Link2,
  Loader2,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { CosyVoiceStatus, VideoTask } from "@/lib/types";

const CLONE_ENDPOINT = "/api/cosyvoice/clone";
const MAX_AUDIO_BYTES = 20 * 1024 * 1024;
const SUPPORTED_TYPES = new Set([
  "audio/mpeg",
  "audio/mp3",
  "audio/wav",
  "audio/x-wav",
  "audio/wave",
  "audio/m4a",
  "audio/x-m4a",
  "audio/mp4",
]);

type CloneResponse = {
  audio_url?: string;
  cloned_voice_url?: string;
  local_path?: string;
  cosyvoice_status?: CosyVoiceStatus;
  task?: VideoTask | null;
  detail?: unknown;
  error?: string;
};

function formatCloneError(payload: CloneResponse | null, fallback: string) {
  if (!payload) return fallback;
  const detail = payload.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail) return JSON.stringify(detail);
  if (payload.error) return payload.error;
  return fallback;
}

const statusStyles: Record<CosyVoiceStatus, string> = {
  pending: "border-white/10 bg-white/[0.04] text-slate-300",
  generating: "border-cyan/30 bg-cyan/10 text-cyan",
  completed: "border-lime/30 bg-lime/10 text-lime",
  failed: "border-rose-300/30 bg-rose-400/10 text-rose-100",
};

const statusLabels: Record<CosyVoiceStatus, string> = {
  pending: "pending",
  generating: "generating",
  completed: "completed",
  failed: "failed",
};

export function CosyVoiceCloneForm({ task }: { task: VideoTask }) {
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState("");
  const [text, setText] = useState(task.script);
  const [promptText, setPromptText] = useState("");
  const [audioUrl, setAudioUrl] = useState(task.cloned_voice_url || "");
  const [status, setStatus] = useState<CosyVoiceStatus>(task.cosyvoice_status || "pending");
  const [message, setMessage] = useState("");
  const [clientError, setClientError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formStatus = useMemo<CosyVoiceStatus>(() => {
    if (isGenerating) return "generating";
    return status;
  }, [isGenerating, status]);

  function validateAudio(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] || null;
    setClientError("");
    setFile(null);
    setFileName("");
    setFileSize("");
    if (!selectedFile) return;

    const lowerName = selectedFile.name.toLowerCase();
    const hasSupportedExtension =
      lowerName.endsWith(".mp3") || lowerName.endsWith(".wav") || lowerName.endsWith(".m4a");
    if (!SUPPORTED_TYPES.has(selectedFile.type) && !hasSupportedExtension) {
      setClientError("支持 mp3 / wav / m4a 格式");
      event.target.value = "";
      return;
    }

    if (selectedFile.size > MAX_AUDIO_BYTES) {
      setClientError("参考声音最大支持 20MB。");
      event.target.value = "";
      return;
    }

    setFile(selectedFile);
    setFileName(selectedFile.name);
    setFileSize(`${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`);
  }

  function clearFile() {
    if (fileInputRef.current) fileInputRef.current.value = "";
    setFile(null);
    setFileName("");
    setFileSize("");
    setClientError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");

    const trimmedText = text.trim();
    if (!trimmedText) {
      setClientError("请输入要生成的文本。");
      setStatus("failed");
      return;
    }

    if (!file) {
      setClientError("请上传参考声音。");
      setStatus("failed");
      return;
    }

    const formData = new FormData();
    formData.append("task_id", task.id);
    formData.append("text", trimmedText);
    formData.append("reference_audio", file);
    formData.append("prompt_text", promptText.trim());

    const formDataKeys = Array.from(formData.keys());
    console.debug("[CosyVoiceClone] request", {
      url: CLONE_ENDPOINT,
      keys: formDataKeys,
      file: { name: file.name, type: file.type, size: file.size },
    });

    setClientError("");
    setStatus("generating");
    setIsGenerating(true);

    try {
      const response = await fetch(CLONE_ENDPOINT, {
        method: "POST",
        body: formData,
        cache: "no-store",
      });
      const rawText = await response.text();
      console.debug("[CosyVoiceClone] response", {
        url: CLONE_ENDPOINT,
        status: response.status,
        ok: response.ok,
        body: rawText,
      });

      let payload: CloneResponse | null = null;
      try {
        payload = rawText ? (JSON.parse(rawText) as CloneResponse) : null;
      } catch {
        throw new Error(rawText || `Clone voice failed with status ${response.status}`);
      }

      if (!response.ok) {
        throw new Error(formatCloneError(payload, rawText || `Clone voice failed with status ${response.status}`));
      }

      const nextAudioUrl = payload?.audio_url || payload?.cloned_voice_url || payload?.task?.cloned_voice_url || "";
      if (!nextAudioUrl) {
        throw new Error(rawText || "Clone voice 成功响应缺少 audio_url。");
      }

      const nextStatus = payload?.cosyvoice_status || payload?.task?.cosyvoice_status || "completed";
      setAudioUrl(nextAudioUrl);
      setStatus(nextStatus);
      setMessage("Clone voice 已生成，可以试听和下载。");
    } catch (error) {
      console.error("[CosyVoiceClone] fetch failed", {
        url: CLONE_ENDPOINT,
        keys: formDataKeys,
        error,
      });
      setStatus("failed");
      setMessage(error instanceof Error ? error.message : JSON.stringify(error));
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <Card className="overflow-hidden border-cyan/15 bg-gradient-to-b from-cyan/10 via-panel/90 to-panel/80">
      <CardHeader className="border-b border-white/10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <span className="grid size-9 place-items-center rounded-md bg-cyan/10 text-cyan">
              <Wand2 size={17} />
            </span>
            Voice Clone 工作台
          </CardTitle>
          <StatusPill status={formStatus} />
        </div>
        <p className="text-sm leading-6 text-slate-400">
          上传参考声音，输入要生成的口播文本，系统会调用本地 CosyVoice 并自动上传到 Supabase。
        </p>
      </CardHeader>
      <CardContent className="pt-5">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-200">生成文本</label>
            <textarea
              name="text"
              rows={5}
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="w-full resize-none rounded-lg border border-white/10 bg-ink/70 px-3 py-3 text-sm leading-6 text-slate-100 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
              placeholder="输入要用克隆声音朗读的内容。"
              required
            />
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <label className="block text-sm font-medium text-slate-200">参考声音</label>
              <span className="text-xs text-slate-500">mp3 / wav / m4a，最大 20MB</span>
            </div>
            <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-white/15 bg-white/[0.04] px-4 py-6 text-center transition hover:border-cyan/40 hover:bg-cyan/5">
              <span className="grid size-12 place-items-center rounded-lg bg-cyan/10 text-cyan">
                <FileAudio2 size={21} />
              </span>
              <span className="text-sm font-medium text-white">{fileName || "上传参考声音"}</span>
              <span className="text-xs text-slate-500">
                {fileName ? `${fileSize} · 已准备生成` : "建议 10-30 秒清晰人声，环境噪音越少越好"}
              </span>
              <input
                ref={fileInputRef}
                name="reference_audio"
                type="file"
                accept="audio/mp3,audio/mpeg,audio/wav,audio/x-wav,audio/m4a,audio/x-m4a,audio/mp4,.mp3,.wav,.m4a"
                onChange={validateAudio}
                className="sr-only"
                required
              />
            </label>
            {fileName ? (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-ink/60 px-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm text-slate-100">{fileName}</p>
                  <p className="text-xs text-slate-500">{fileSize}</p>
                </div>
                <Button type="button" variant="ghost" size="sm" onClick={clearFile}>
                  <Trash2 size={15} />
                  删除
                </Button>
              </div>
            ) : null}
            {clientError ? (
              <p className="mt-2 flex items-center gap-2 text-sm text-rose-200">
                <AlertTriangle size={15} />
                {clientError}
              </p>
            ) : null}
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-200">参考声音对应文本</label>
            <textarea
              name="prompt_text"
              rows={3}
              value={promptText}
              onChange={(event) => setPromptText(event.target.value)}
              placeholder="如果参考音频里说的是固定句子，填在这里；留空则使用默认提示文本。"
              className="w-full resize-none rounded-lg border border-white/10 bg-ink/70 px-3 py-3 text-sm leading-6 text-slate-100 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
            />
          </div>

          <CloneProgress pending={isGenerating} />

          {audioUrl ? (
            <div className="rounded-lg border border-lime/20 bg-lime/5 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-lime">
                <CheckCircle2 size={16} />
                Clone voice 已生成
              </div>
              <audio controls src={audioUrl} className="w-full" />
              <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto]">
                <div className="flex min-w-0 items-center gap-2 rounded-md border border-white/10 bg-ink/70 px-3 py-2 text-xs text-slate-400">
                  <Link2 size={14} className="shrink-0 text-cyan" />
                  <span className="truncate">{audioUrl}</span>
                </div>
                <Button asChild variant="outline" size="sm">
                  <a href={audioUrl} target="_blank" rel="noreferrer" download>
                    <Download size={15} />
                    下载
                  </a>
                </Button>
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
            <p className={status === "completed" ? "text-sm text-lime" : "text-sm text-rose-200"}>{message}</p>
            <CloneSubmitButton pending={isGenerating} hasClientError={Boolean(clientError)} />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function StatusPill({ status }: { status: CosyVoiceStatus }) {
  return (
    <span className={cn("rounded-full border px-3 py-1 text-xs font-semibold", statusStyles[status])}>
      {statusLabels[status]}
    </span>
  );
}

function CloneProgress({ pending }: { pending: boolean }) {
  return (
    <div className="rounded-lg border border-white/10 bg-ink/50 p-3">
      <div className="mb-2 flex items-center justify-between gap-3 text-xs text-slate-400">
        <span>{pending ? "generating · 正在上传并生成音频" : "pending · 等待生成"}</span>
        {pending ? <Loader2 className="animate-spin text-cyan" size={14} /> : <Sparkles className="text-slate-500" size={14} />}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className={cn(
            "h-full rounded-full bg-cyan transition-all",
            pending ? "w-2/3 animate-pulse" : "w-0",
          )}
        />
      </div>
    </div>
  );
}

function CloneSubmitButton({ pending, hasClientError }: { pending: boolean; hasClientError: boolean }) {
  return (
    <Button type="submit" disabled={pending || hasClientError}>
      {pending ? <Loader2 className="animate-spin" size={16} /> : <Wand2 size={16} />}
      {pending ? "生成中" : "生成 Clone Voice"}
    </Button>
  );
}
