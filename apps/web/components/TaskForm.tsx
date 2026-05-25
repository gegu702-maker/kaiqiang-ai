"use client";

import { ChangeEvent, useActionState, useEffect, useRef, useState } from "react";
import { ImagePlus, Mail, Package, ScrollText, Target, Video } from "lucide-react";

import { submitTaskAction } from "@/app/actions/tasks";
import { useLanguage } from "@/components/LanguageProvider";
import { SubmitButton } from "@/components/SubmitButton";
import { VoiceUpload } from "@/components/VoiceUpload";
import { Card } from "@/components/ui/card";
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
    chooseFile: "选择文件",
    noFile: "未选择任何文件",
    clonedVoice: "使用我的克隆声音",
    cloneUpsell: "升级到 Pro 解锁声音克隆，后续视频可直接使用你的专属 voice_id。",
    loginHint: "可以先填写和上传素材，点击生成时再登录，登录后回到工作台。",
    draftRestored: "已恢复上次填写的工作台草稿。",
    businessQuota: "Business 套餐：自定义额度",
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
    chooseFile: "Choose File",
    noFile: "No file selected",
    clonedVoice: "Use my cloned voice",
    cloneUpsell: "Upgrade to Pro to unlock voice cloning and reuse your dedicated voice_id in future videos.",
    loginHint: "You can fill in details and upload assets first. Sign in when you click generate, then return to the studio.",
    draftRestored: "Your previous studio draft has been restored.",
    businessQuota: "Business plan: custom quota",
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

type TaskFormProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
};

export function TaskForm({ userEmail, remainingQuota, voiceCloneEnabled = false, voiceClones = [] }: TaskFormProps) {
  const { locale } = useLanguage();
  const current = copy[locale];
  const [state, action] = useActionState(submitTaskAction, initialState);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const personalImageInputRef = useRef<HTMLInputElement>(null);
  const [imageError, setImageError] = useState("");
  const [personalImageError, setPersonalImageError] = useState("");
  const [imageName, setImageName] = useState("");
  const [personalImageName, setPersonalImageName] = useState("");
  const [draftRestored, setDraftRestored] = useState(false);

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
            return;
          }
          if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement) {
            if (field.type !== "file" && field.name !== "user_email") field.value = value;
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

  return (
    <form id="task-submit-form" action={action} className="space-y-4">
      <input type="hidden" name="ui_locale" value={locale} />
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
            <input type="radio" name="use_digital_human" value="true" defaultChecked />
            {current.yesDigitalHuman}
          </label>
          <label className="flex h-11 cursor-pointer items-center gap-3 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-slate-300">
            <input type="radio" name="use_digital_human" value="false" />
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

      <label className="space-y-2">
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <ImagePlus size={15} /> {current.personalImage}
        </span>
        <input
          ref={personalImageInputRef}
          required
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

      <input type="hidden" name="avatar_id" value="heygen_custom" />
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
            {userEmail
              ? remainingQuota === null
                ? current.businessQuota
                : current.remaining(Math.max(remainingQuota ?? 0, 0))
              : current.loggedOutQuota}
          </p>
        </div>
        <SubmitButton label={userEmail ? current.submit : current.loginSubmit} pendingLabel={userEmail ? current.pending : current.loginPending} />
      </div>
      </Card>
    </form>
  );
}
