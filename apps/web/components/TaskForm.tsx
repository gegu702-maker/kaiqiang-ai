"use client";

import { ChangeEvent, useActionState, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Check, Download, ImagePlus, Loader2, Mail, Mic2, Package, ScrollText, Target, Video } from "lucide-react";

import { submitTaskAction } from "@/app/actions/tasks";
import { useLanguage } from "@/components/LanguageProvider";
import { SubmitButton } from "@/components/SubmitButton";
import { VoiceUpload } from "@/components/VoiceUpload";
import { Card } from "@/components/ui/card";
import { trackEvent } from "@/lib/analytics";
import { avatarTemplates } from "@/lib/avatarTemplates";
import { cn } from "@/lib/utils";
import type { VoiceClone } from "@/lib/types";

const initialState = { ok: false, message: "" };
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const copy = {
  zh: {
    imageType: "图片仅支持 jpg、png、webp。",
    imageSize: "图片最大支持 10MB。",
    email: "邮箱",
    productName: "产品名称",
    productPlaceholder: "智能补光化妆镜",
    highlights: "产品卖点",
    highlightsPlaceholder: "例如：便携、防水、续航长、适合户外、质感高级、价格有优势...",
    audience: "目标人群",
    audiencePlaceholder: "例如：露营爱好者、宝妈、通勤上班族",
    style: "视频风格",
    useDigitalHuman: "是否使用数字人",
    yesDigitalHuman: "是，生成数字人口播工作流",
    noDigitalHuman: "否，只生成素材和剪辑清单",
    productImage: "产品图片",
    personalImage: "个人形象素材",
    optional: "可选",
    chooseFile: "选择文件",
    noFile: "未选择任何文件",
    clonedVoice: "使用我的克隆声音",
    voiceType: "火山引擎音色",
    ttsTitle: "语音试听",
    ttsDescription: "输入口播文案，先生成一段可播放的 MP3。",
    ttsText: "口播文案",
    ttsPlaceholder: "你好，我是凯强 AI 数字人",
    ttsGenerate: "生成语音",
    ttsGenerating: "生成中",
    ttsSuccess: "语音已生成",
    ttsFailed: "TTS 失败",
    ttsNetworkError: "网络错误，请稍后重试。",
    ttsProviderError: "provider 错误，请检查 Volcengine 配置。",
    ttsDownload: "下载 MP3",
    avatarTemplate: "数字人模板",
    avatarTemplateHint: "普通会员可选择固定模板，Pro 后续开放自定义形象。",
    recommended: "推荐场景",
    videoTitle: "静态头像口播视频",
    videoDescription: "把当前文案合成为 1080x1920 竖屏 MP4。",
    videoGenerate: "生成视频",
    videoGenerating: "视频生成中",
    videoProcessing: "processing",
    videoSuccess: "视频已生成",
    videoFailed: "视频生成失败",
    videoDownload: "下载 MP4",
    videoMode: "视频模式",
    staticMode: "静态视频",
    dynamicMode: "动态数字人",
    livePortraitUnavailable: "动态数字人暂未开通，请配置 Replicate API。",
    voiceTypes: {
      BV001_streaming: "女声（BV001_streaming）",
      BV002_streaming: "男声（BV002_streaming）",
    },
    cloneUpsell: "升级到 Pro 解锁声音克隆，后续视频可直接使用你的专属 voice_id。",
    loginHint: "可以先填写和上传素材，点击生成时再登录，登录后回到工作台。",
    draftRestored: "已恢复上次填写的工作台草稿。",
    businessQuota: "Business 套餐：自定义额度",
    quotaLoadFailed: "额度加载失败，请刷新后重试。",
    remaining: (quota: number) => `本月剩余 ${quota} 次生成`,
    loggedOutQuota: "登录后可生成，每月免费 3 次。",
    submit: "生成带货视频方案",
    loginSubmit: "登录并生成",
    pending: "正在生成",
    loginPending: "正在跳转登录",
    emailPlaceholder: "提交生成时登录后自动填入",
    styles: {
      hard_sell: "硬核带货",
      emotional_seed: "情绪种草",
      premium: "高端质感",
      factory_boss: "工厂老板风",
      tiktok: "TikTok 风格",
      review: "测评解说",
      story: "剧情短片",
    },
  },
  en: {
    imageType: "Images support jpg, png, and webp only.",
    imageSize: "Images can be up to 10MB.",
    email: "Email",
    productName: "Product Name",
    productPlaceholder: "Smart fill-light makeup mirror",
    highlights: "Product Highlights",
    highlightsPlaceholder: "e.g. portable, waterproof, long battery life, outdoor-friendly, premium texture, price advantage...",
    audience: "Target Audience",
    audiencePlaceholder: "e.g. campers, moms, commuters",
    style: "Video Style",
    useDigitalHuman: "Use Digital Human",
    yesDigitalHuman: "Yes, generate a digital human talking-video workflow",
    noDigitalHuman: "No, generate assets and an editing checklist only",
    productImage: "Product Image",
    personalImage: "Personal Avatar Asset",
    optional: "Optional",
    chooseFile: "Choose File",
    noFile: "No file selected",
    clonedVoice: "Use my cloned voice",
    voiceType: "Volcengine Voice",
    ttsTitle: "Voice Preview",
    ttsDescription: "Generate a playable MP3 from your talking script.",
    ttsText: "Script",
    ttsPlaceholder: "Hello, I am Kaiqiang AI digital human.",
    ttsGenerate: "Generate Voice",
    ttsGenerating: "Generating",
    ttsSuccess: "Voice generated",
    ttsFailed: "TTS failed",
    ttsNetworkError: "Network error. Please try again.",
    ttsProviderError: "Provider error. Please check Volcengine settings.",
    ttsDownload: "Download MP3",
    avatarTemplate: "Avatar Template",
    avatarTemplateHint: "Members can use fixed templates. Custom avatars will come with Pro.",
    recommended: "Recommended",
    videoTitle: "Static Avatar Video",
    videoDescription: "Render the current script into a 1080x1920 MP4.",
    videoGenerate: "Generate Video",
    videoGenerating: "Generating Video",
    videoProcessing: "processing",
    videoSuccess: "Video generated",
    videoFailed: "Video generation failed",
    videoDownload: "Download MP4",
    videoMode: "Video Mode",
    staticMode: "Static Video",
    dynamicMode: "Dynamic Avatar",
    livePortraitUnavailable: "Dynamic avatar is not enabled. Configure the Replicate API first.",
    voiceTypes: {
      BV001_streaming: "Female (BV001_streaming)",
      BV002_streaming: "Male (BV002_streaming)",
    },
    cloneUpsell: "Upgrade to Pro to unlock voice cloning and reuse your dedicated voice_id in future videos.",
    loginHint: "You can fill in details and upload assets first. Sign in when you click generate, then return to the studio.",
    draftRestored: "Your previous studio draft has been restored.",
    businessQuota: "Business plan: custom quota",
    quotaLoadFailed: "Quota failed to load. Please refresh and try again.",
    remaining: (quota: number) => `${quota} generations left this month`,
    loggedOutQuota: "Sign in to generate. Free plan includes 3 generations per month.",
    submit: "Generate Now",
    loginSubmit: "Sign in and Generate",
    pending: "Generating",
    loginPending: "Redirecting to login",
    emailPlaceholder: "Auto-filled after login when submitting",
    styles: {
      hard_sell: "Hard-sell Product Video",
      emotional_seed: "Emotional Seeding",
      premium: "Premium Look",
      factory_boss: "Factory Founder Style",
      tiktok: "TikTok Style",
      review: "Review Explainer",
      story: "Story Short",
    },
  },
};

type TTSStatus = "idle" | "generating" | "success" | "failed";

type TTSTestResponse = {
  success: boolean;
  audio_url?: string;
  provider?: string;
  voice_type?: string;
  detail?: unknown;
  error?: string;
  message?: string;
};

type AvatarVideoTestResponse = TTSTestResponse & {
  video_url?: string;
  dynamic_avatar_video_url?: string;
  final_video_url?: string;
  avatar_template_id?: string;
  avatar_template_name?: string;
};

type TaskFormProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  quotaLoadFailed?: boolean;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
  livePortraitEnabled?: boolean;
  initialScriptText?: string;
};

export function TaskForm({ userEmail, remainingQuota, quotaLoadFailed = false, voiceCloneEnabled = false, voiceClones = [], livePortraitEnabled = false, initialScriptText = "" }: TaskFormProps) {
  const { locale } = useLanguage();
  const current = copy[locale];
  const displayedRemainingQuota = userEmail && remainingQuota === undefined ? 3 : remainingQuota;
  const [state, action] = useActionState(submitTaskAction, initialState);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const personalImageInputRef = useRef<HTMLInputElement>(null);
  const lastTrackedMessageRef = useRef("");
  const [imageError, setImageError] = useState("");
  const [personalImageError, setPersonalImageError] = useState("");
  const [imageName, setImageName] = useState("");
  const [personalImageName, setPersonalImageName] = useState("");
  const [useDigitalHuman, setUseDigitalHuman] = useState(true);
  const [draftRestored, setDraftRestored] = useState(false);
  const [ttsText, setTtsText] = useState(initialScriptText || current.ttsPlaceholder);
  const [ttsVoiceType, setTtsVoiceType] = useState("BV001_streaming");
  const [avatarTemplateId, setAvatarTemplateId] = useState("business_female_01");
  const [ttsStatus, setTtsStatus] = useState<TTSStatus>("idle");
  const [ttsError, setTtsError] = useState("");
  const [ttsAudioUrl, setTtsAudioUrl] = useState("");
  const [ttsProvider, setTtsProvider] = useState("");
  const [videoStatus, setVideoStatus] = useState<TTSStatus>("idle");
  const [videoError, setVideoError] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [videoProgress, setVideoProgress] = useState(0);
  const [videoMode, setVideoMode] = useState<"static" | "liveportrait">("static");

  useEffect(() => {
    if (initialScriptText) setTtsText(initialScriptText);
  }, [initialScriptText]);

  useEffect(() => {
    const form = document.getElementById("task-submit-form") as HTMLFormElement | null;
    if (!form) return;

    const draft = window.sessionStorage.getItem("kaiqiang-studio-draft");
    if (draft) {
      try {
        const values = JSON.parse(draft) as Record<string, string>;
        Object.entries(values).forEach(([name, value]) => {
          const field = form.elements.namedItem(name);
          if (!field) return;
          if (field instanceof RadioNodeList) {
            const radio = Array.from(field).find((item) => item instanceof HTMLInputElement && item.value === value);
            if (radio instanceof HTMLInputElement) radio.checked = true;
            if (name === "use_digital_human") setUseDigitalHuman(value !== "false");
            return;
          }
          if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement) {
            if (field.type !== "file" && field.name !== "user_email") field.value = value;
            if (field.name === "avatar_template_id") {
              const template = avatarTemplates.find((item) => item.id === value);
              if (template) {
                setAvatarTemplateId(template.id);
                setTtsVoiceType(template.voice_type);
              }
            }
          }
        });
        setDraftRestored(true);
      } catch {
        window.sessionStorage.removeItem("kaiqiang-studio-draft");
      }
    }

    const saveDraft = () => {
      const data = new FormData(form);
      const values: Record<string, string> = {};
      data.forEach((value, key) => {
        if (typeof value === "string" && key !== "user_email") {
          values[key] = value;
        }
      });
      window.sessionStorage.setItem("kaiqiang-studio-draft", JSON.stringify(values));
    };

    form.addEventListener("input", saveDraft);
    form.addEventListener("change", saveDraft);
    return () => {
      form.removeEventListener("input", saveDraft);
      form.removeEventListener("change", saveDraft);
    };
  }, []);

  useEffect(() => {
    if (!state.message || state.message === lastTrackedMessageRef.current) return;
    lastTrackedMessageRef.current = state.message;
    if (state.ok) {
      trackEvent("submit_video_task", {
        use_digital_human: useDigitalHuman,
        voice_clone_enabled: voiceCloneEnabled,
      });
      return;
    }
    if (/额度|quota|用完|exhausted|upgrade/i.test(state.message)) {
      trackEvent("quota_exhausted", { message: state.message });
    }
  }, [state.message, state.ok, useDigitalHuman, voiceCloneEnabled]);

  function validateImageFile(event: ChangeEvent<HTMLInputElement>, setError: (message: string) => void, setName: (name: string) => void) {
    const file = event.target.files?.[0];
    setError("");
    setName("");
    if (!file) return;

    const validExtension = /\.(jpe?g|png|webp)$/i.test(file.name);
    if (!IMAGE_TYPES.includes(file.type) && !validExtension) {
      setError(current.imageType);
      event.target.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setError(current.imageSize);
      event.target.value = "";
      return;
    }

    setName(file.name);
  }

  async function generateTTSPreview() {
    const text = ttsText.trim();
    if (!text || ttsStatus === "generating") return;

    setTtsStatus("generating");
    setTtsError("");
    setTtsAudioUrl("");
    setTtsProvider("");

    try {
      const response = await fetch("/api/debug/tts-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice_type: ttsVoiceType }),
      });
      const payload = (await response.json().catch(() => ({}))) as TTSTestResponse;
      if (!response.ok || !payload.success || !payload.audio_url) {
        const detail = readApiError(payload);
        const isProviderError = /provider|VOLCENGINE|quota|permission|voice_type|invalid/i.test(detail);
        throw new Error(detail || (isProviderError ? current.ttsProviderError : current.ttsFailed));
      }
      setTtsAudioUrl(payload.audio_url);
      setTtsProvider(payload.provider || "volcengine");
      setTtsStatus("success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      setTtsError(message || current.ttsNetworkError);
      setTtsStatus("failed");
    }
  }

  async function downloadTTSAudio() {
    if (!ttsAudioUrl) return;

    try {
      const response = await fetch(ttsAudioUrl);
      if (!response.ok) throw new Error(current.ttsNetworkError);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `kaiqiang-tts-${ttsVoiceType}.mp3`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setTtsStatus("failed");
      setTtsError(error instanceof Error ? error.message : current.ttsNetworkError);
    }
  }

  async function generateAvatarVideo() {
    const text = ttsText.trim();
    if (!text || videoStatus === "generating") return;

    setVideoStatus("generating");
    setVideoError("");
    setVideoUrl("");
    setVideoProgress(18);

    let progressTimer: number | undefined;
    try {
      progressTimer = window.setInterval(() => {
        setVideoProgress((currentProgress) => Math.min(currentProgress + 9, 82));
      }, 2500);
      const response = await fetch(videoMode === "liveportrait" ? "/api/debug/liveportrait-test" : "/api/avatar/static-video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice_type: ttsVoiceType, avatar_template_id: avatarTemplateId }),
      });
      const payload = (await response.json().catch(() => ({}))) as AvatarVideoTestResponse;
      const resolvedVideoUrl = payload.final_video_url || payload.video_url || payload.dynamic_avatar_video_url;
      if (!response.ok || !payload.success || !resolvedVideoUrl) {
        throw new Error(readApiError(payload) || current.videoFailed);
      }
      setVideoUrl(resolvedVideoUrl);
      if (payload.audio_url) setTtsAudioUrl(payload.audio_url);
      if (payload.provider) setTtsProvider(payload.provider);
      setVideoProgress(100);
      setVideoStatus("success");
    } catch (error) {
      setVideoProgress(0);
      setVideoError(error instanceof Error ? error.message : current.ttsNetworkError);
      setVideoStatus("failed");
    } finally {
      if (progressTimer) window.clearInterval(progressTimer);
    }
  }

  async function downloadAvatarVideo() {
    if (!videoUrl) return;

    try {
      const response = await fetch(videoUrl);
      if (!response.ok) throw new Error(current.ttsNetworkError);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `kaiqiang-avatar-video-${ttsVoiceType}.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setVideoStatus("failed");
      setVideoError(error instanceof Error ? error.message : current.ttsNetworkError);
    }
  }

  return (
    <form
      id="task-submit-form"
      action={action}
      className="space-y-4"
      onSubmit={() =>
        trackEvent("click_generate_video", {
          logged_in: Boolean(userEmail),
          use_digital_human: useDigitalHuman,
          voice_clone_enabled: voiceCloneEnabled,
        })
      }
    >
      <input type="hidden" name="ui_locale" value={locale} />
      <Card className="space-y-4 p-4">
        <section className="space-y-3">
          <div>
            <h2 className="text-base font-semibold text-white">{current.avatarTemplate}</h2>
            <p className="mt-1 text-sm text-slate-400">{current.avatarTemplateHint}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {avatarTemplates.map((template) => {
              const isSelected = avatarTemplateId === template.id;
              return (
                <label key={template.id} className="cursor-pointer">
                  <input
                    type="radio"
                    name="avatar_template_id"
                    value={template.id}
                    checked={isSelected}
                    onChange={() => {
                      setAvatarTemplateId(template.id);
                      setTtsVoiceType(template.voice_type);
                    }}
                    className="sr-only"
                  />
                  <div
                    className={cn(
                      "relative h-full overflow-hidden rounded-md border bg-white/[0.03] p-3 transition",
                      isSelected ? "border-cyan bg-cyan/10" : "border-white/10 hover:border-white/25 hover:bg-white/[0.06]",
                    )}
                  >
                    <div className="relative mb-3 aspect-square overflow-hidden rounded-md border border-white/10 bg-black/20">
                      <Image src={template.avatar_image} alt={template.name} fill className="object-cover" />
                    </div>
                    <div className="space-y-1">
                      <p className="font-semibold text-white">{template.name}</p>
                      <p className="text-xs leading-5 text-slate-400">{template.description}</p>
                      <p className="text-xs text-slate-500">
                        {current.recommended} · {template.style} · {template.voice_type}
                      </p>
                    </div>
                    {isSelected ? (
                      <span className="absolute right-3 top-3 grid size-6 place-items-center rounded-full bg-cyan text-ink">
                        <Check size={14} />
                      </span>
                    ) : null}
                  </div>
                </label>
              );
            })}
          </div>
        </section>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-white">{current.ttsTitle}</h2>
            <p className="text-sm text-slate-400">{current.ttsDescription}</p>
          </div>
          {ttsStatus === "success" ? <span className="rounded-md border border-lime/30 bg-lime/10 px-2.5 py-1 text-xs text-lime">{current.ttsSuccess}</span> : null}
        </div>
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <ScrollText size={15} /> {current.ttsText}
          </span>
          <textarea
            name="tts_preview_text"
            rows={4}
            value={ttsText}
            onChange={(event) => setTtsText(event.target.value)}
            placeholder={current.ttsPlaceholder}
            className="w-full resize-none rounded-md border border-white/10 bg-white/5 px-3 py-3 leading-6 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <label className="space-y-2">
            <span className="flex items-center gap-2 text-sm text-slate-300">
              <Mic2 size={15} /> {current.voiceType}
            </span>
            <select
              value={ttsVoiceType}
              onChange={(event) => setTtsVoiceType(event.target.value)}
              className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2"
            >
              {Object.entries(current.voiceTypes).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={generateTTSPreview}
            disabled={ttsStatus === "generating" || !ttsText.trim()}
            className="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-md bg-cyan px-5 text-sm font-semibold text-ink transition hover:bg-cyan/90 disabled:pointer-events-none disabled:opacity-60"
          >
            {ttsStatus === "generating" ? <Loader2 className="animate-spin" size={16} /> : <Mic2 size={16} />}
            {ttsStatus === "generating" ? current.ttsGenerating : current.ttsGenerate}
          </button>
        </div>
        {ttsStatus === "failed" ? (
          <p className="rounded-md border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
            {current.ttsFailed}：{ttsError || current.ttsProviderError}
          </p>
        ) : null}
        {ttsAudioUrl ? (
          <div className="space-y-3 rounded-md border border-white/10 bg-black/20 p-3">
            <audio className="w-full" src={ttsAudioUrl} controls preload="metadata" />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-slate-500">
                {ttsProvider || "volcengine"} · {ttsVoiceType}
              </p>
              <button
                type="button"
                onClick={downloadTTSAudio}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10"
              >
                <Download size={15} />
                {current.ttsDownload}
              </button>
            </div>
          </div>
        ) : null}
        <div className="space-y-3 rounded-md border border-white/10 bg-white/[0.03] p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Video size={15} /> {current.videoTitle}
              </h3>
              <p className="text-xs text-slate-500">{current.videoDescription}</p>
            </div>
            {videoStatus === "success" ? <span className="rounded-md border border-lime/30 bg-lime/10 px-2.5 py-1 text-xs text-lime">{current.videoSuccess}</span> : null}
          </div>
          <fieldset className="space-y-2">
            <legend className="text-sm text-slate-300">{current.videoMode}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className={cn("flex h-11 cursor-pointer items-center gap-3 rounded-md border px-3 text-sm", videoMode === "static" ? "border-cyan/30 bg-cyan/10 text-slate-100" : "border-white/10 bg-white/5 text-slate-300")}>
                <input type="radio" name="video_motion_mode" value="static" checked={videoMode === "static"} onChange={() => setVideoMode("static")} />
                {current.staticMode}
              </label>
              <label className={cn("flex h-11 items-center gap-3 rounded-md border px-3 text-sm", livePortraitEnabled ? "cursor-pointer" : "cursor-not-allowed opacity-60", videoMode === "liveportrait" ? "border-cyan/30 bg-cyan/10 text-slate-100" : "border-white/10 bg-white/5 text-slate-300")}>
                <input
                  type="radio"
                  name="video_motion_mode"
                  value="liveportrait"
                  checked={videoMode === "liveportrait"}
                  disabled={!livePortraitEnabled}
                  onChange={() => setVideoMode("liveportrait")}
                />
                {current.dynamicMode}
              </label>
            </div>
            {!livePortraitEnabled ? <p className="text-xs text-slate-500">{current.livePortraitUnavailable}</p> : null}
          </fieldset>
          {videoStatus === "generating" ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>{current.videoProcessing}</span>
                <span>{videoProgress}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-cyan transition-all" style={{ width: `${videoProgress}%` }} />
              </div>
            </div>
          ) : null}
          <button
            type="button"
            onClick={generateAvatarVideo}
            disabled={videoStatus === "generating" || !ttsText.trim()}
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-cyan/30 bg-cyan/10 px-5 text-sm font-semibold text-cyan transition hover:bg-cyan/15 disabled:pointer-events-none disabled:opacity-60 sm:w-auto"
          >
            {videoStatus === "generating" ? <Loader2 className="animate-spin" size={16} /> : <Video size={16} />}
            {videoStatus === "generating" ? current.videoGenerating : current.videoGenerate}
          </button>
          {videoStatus === "failed" ? (
            <p className="rounded-md border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
              {current.videoFailed}：{videoError || current.ttsProviderError}
            </p>
          ) : null}
          {videoUrl ? (
            <div className="space-y-3">
              <video className="aspect-[9/16] max-h-[620px] w-full rounded-md border border-white/10 bg-black object-contain sm:w-[320px]" src={videoUrl} controls preload="metadata" />
              <button
                type="button"
                onClick={downloadAvatarVideo}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10"
              >
                <Download size={15} />
                {current.videoDownload}
              </button>
            </div>
          ) : null}
        </div>
      </Card>
      <Card className="space-y-4 p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Mail size={15} /> {current.email}
          </span>
          <input
            type="email"
            name="user_email"
            value={userEmail ?? ""}
            readOnly
            placeholder={current.emailPlaceholder}
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Package size={15} /> {current.productName}
          </span>
          <input
            required
            name="product_name"
            placeholder={current.productPlaceholder}
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
      </div>

      <label className="space-y-2">
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <ScrollText size={15} /> {current.highlights}
        </span>
        <textarea
          required
          name="product_highlights"
          rows={4}
          placeholder={current.highlightsPlaceholder}
          className="w-full resize-none rounded-md border border-white/10 bg-white/5 px-3 py-3 leading-6 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Target size={15} /> {current.audience}
          </span>
          <input
            required
            name="target_audience"
            placeholder={current.audiencePlaceholder}
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Video size={15} /> {current.style}
          </span>
          <select
            required
            name="video_style"
            defaultValue="hard_sell"
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2"
          >
            {Object.entries(current.styles).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm text-slate-300">{current.useDigitalHuman}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex h-11 cursor-pointer items-center gap-3 rounded-md border border-cyan/30 bg-cyan/10 px-3 text-sm text-slate-100">
            <input type="radio" name="use_digital_human" value="true" checked={useDigitalHuman} onChange={() => setUseDigitalHuman(true)} />
            {current.yesDigitalHuman}
          </label>
          <label className="flex h-11 cursor-pointer items-center gap-3 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-slate-300">
            <input
              type="radio"
              name="use_digital_human"
              value="false"
              checked={!useDigitalHuman}
              onChange={() => {
                setUseDigitalHuman(false);
                setPersonalImageError("");
              }}
            />
            {current.noDigitalHuman}
          </label>
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <ImagePlus size={15} /> {current.productImage}
          </span>
          <input
            ref={imageInputRef}
            required
            type="file"
            name="image"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            onChange={(event) => validateImageFile(event, setImageError, setImageName)}
            className="sr-only"
          />
          <button
            type="button"
            onClick={() => imageInputRef.current?.click()}
            className="flex h-11 w-full items-center overflow-hidden rounded-md border border-white/10 bg-white/5 text-left text-sm"
          >
            <span className="flex h-full shrink-0 items-center bg-cyan px-4 font-semibold text-ink">{current.chooseFile}</span>
            <span className="truncate px-3 text-slate-300">{imageName || current.noFile}</span>
          </button>
          {imageError ? <span className="block text-xs text-rose-200">{imageError}</span> : null}
        </label>
      </div>

      <label className={useDigitalHuman ? "space-y-2" : "space-y-2 opacity-75"}>
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <ImagePlus size={15} /> {current.personalImage} {!useDigitalHuman ? <span className="text-xs text-slate-500">({current.optional})</span> : null}
        </span>
        <input
          ref={personalImageInputRef}
          required={useDigitalHuman}
          type="file"
          name="personal_image"
          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
          onChange={(event) => validateImageFile(event, setPersonalImageError, setPersonalImageName)}
          className="sr-only"
        />
        <button
          type="button"
          onClick={() => personalImageInputRef.current?.click()}
          className="flex h-11 w-full items-center overflow-hidden rounded-md border border-white/10 bg-white/5 text-left text-sm"
        >
          <span className="flex h-full shrink-0 items-center bg-cyan px-4 font-semibold text-ink">{current.chooseFile}</span>
          <span className="truncate px-3 text-slate-300">{personalImageName || current.noFile}</span>
        </button>
        {personalImageError ? <span className="block text-xs text-rose-200">{personalImageError}</span> : null}
      </label>

      <input type="hidden" name="avatar_id" value={avatarTemplateId} />
      <label className="space-y-2">
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <Mic2 size={15} /> {current.voiceType}
        </span>
        <select
          name="voice_type"
          value={ttsVoiceType}
          onChange={(event) => setTtsVoiceType(event.target.value)}
          className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2"
        >
          {Object.entries(current.voiceTypes).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {voiceCloneEnabled && voiceClones.length > 0 ? (
        <div className="rounded-md border border-cyan/20 bg-cyan/[0.06] p-3">
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="use_cloned_voice" value="true" />
            {current.clonedVoice}
          </label>
          <select name="voice_clone_id" className="mt-3 h-10 w-full rounded-md border border-white/10 bg-ink/70 px-3 text-sm">
            {voiceClones.map((clone) => (
              <option key={clone.id} value={clone.id}>
                {clone.name} · {clone.voice_id || clone.status}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <p className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-500">
          {current.cloneUpsell}
        </p>
      )}
      <VoiceUpload />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{state.message}</p>
          {!userEmail ? <p className="text-xs text-cyan">{current.loginHint}</p> : null}
          {draftRestored ? <p className="text-xs text-lime">{current.draftRestored}</p> : null}
          <p className="text-xs text-slate-500">
            {quotaLoadFailed
              ? current.quotaLoadFailed
              : userEmail
              ? displayedRemainingQuota === null
                ? current.businessQuota
                : current.remaining(Math.max(displayedRemainingQuota ?? 3, 0))
              : current.loggedOutQuota}
          </p>
        </div>
        <SubmitButton label={userEmail ? current.submit : current.loginSubmit} pendingLabel={userEmail ? current.pending : current.loginPending} />
      </div>
      </Card>
    </form>
  );
}

function readApiError(payload: TTSTestResponse): string {
  if (payload.message) return payload.message;
  if (payload.error) return payload.error;
  if (typeof payload.detail === "string") return payload.detail;
  if (payload.detail && typeof payload.detail === "object") {
    const detail = payload.detail as { message?: unknown; error?: unknown; detail?: unknown };
    return String(detail.message ?? detail.error ?? detail.detail ?? "");
  }
  return "";
}
