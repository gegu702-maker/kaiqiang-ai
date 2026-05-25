"use client";

import { ChangeEvent, useActionState, useEffect, useState } from "react";
import { ImagePlus, Mail, Package, ScrollText, Target, Video } from "lucide-react";

import { submitTaskAction } from "@/app/actions/tasks";
import { SubmitButton } from "@/components/SubmitButton";
import { VoiceUpload } from "@/components/VoiceUpload";
import { Card } from "@/components/ui/card";
import type { VoiceClone } from "@/lib/types";

const initialState = { ok: false, message: "" };
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

type TaskFormProps = {
  userEmail?: string | null;
  remainingQuota?: number | null;
  voiceCloneEnabled?: boolean;
  voiceClones?: VoiceClone[];
};

export function TaskForm({ userEmail, remainingQuota, voiceCloneEnabled = false, voiceClones = [] }: TaskFormProps) {
  const [state, action] = useActionState(submitTaskAction, initialState);
  const [imageError, setImageError] = useState("");
  const [personalImageError, setPersonalImageError] = useState("");
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

  function validateImageFile(event: ChangeEvent<HTMLInputElement>, setError: (message: string) => void) {
    const file = event.target.files?.[0];
    setError("");
    if (!file) return;

    const validExtension = /\.(jpe?g|png|webp)$/i.test(file.name);
    if (!IMAGE_TYPES.includes(file.type) && !validExtension) {
      setError("图片仅支持 jpg、png、webp。");
      event.target.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setError("图片最大支持 10MB。");
      event.target.value = "";
    }
  }

  return (
    <form id="task-submit-form" action={action} className="space-y-4">
      <Card className="space-y-4 p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Mail size={15} /> 邮箱
          </span>
          <input
            type="email"
            name="user_email"
            value={userEmail ?? ""}
            readOnly
            placeholder="提交生成时登录后自动填入"
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Package size={15} /> 产品名称
          </span>
          <input
            required
            name="product_name"
            placeholder="智能补光化妆镜"
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
      </div>

      <label className="space-y-2">
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <ScrollText size={15} /> 产品卖点
        </span>
        <textarea
          required
          name="product_highlights"
          rows={4}
          placeholder="例如：便携、防水、续航长、适合户外、质感高级、价格有优势..."
          className="w-full resize-none rounded-md border border-white/10 bg-white/5 px-3 py-3 leading-6 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Target size={15} /> 目标人群
          </span>
          <input
            required
            name="target_audience"
            placeholder="例如：露营爱好者、宝妈、通勤女生"
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </label>
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <Video size={15} /> 视频风格
          </span>
          <select
            required
            name="video_style"
            defaultValue="hard_sell"
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2"
          >
            <option value="hard_sell">硬核带货</option>
            <option value="emotional_seed">情绪种草</option>
            <option value="premium">高端质感</option>
            <option value="factory_boss">工厂老板风</option>
            <option value="tiktok">TikTok 风格</option>
            <option value="review">测评解说</option>
            <option value="story">剧情短片</option>
          </select>
        </label>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm text-slate-300">是否使用数字人</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex h-11 cursor-pointer items-center gap-3 rounded-md border border-cyan/30 bg-cyan/10 px-3 text-sm text-slate-100">
            <input type="radio" name="use_digital_human" value="true" defaultChecked />
            是，生成数字人口播工作流
          </label>
          <label className="flex h-11 cursor-pointer items-center gap-3 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-slate-300">
            <input type="radio" name="use_digital_human" value="false" />
            否，只生成素材和剪辑清单
          </label>
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2">
          <span className="flex items-center gap-2 text-sm text-slate-300">
            <ImagePlus size={15} /> 产品图片
          </span>
          <input
            required
            type="file"
            name="image"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            onChange={(event) => validateImageFile(event, setImageError)}
            className="block h-11 w-full cursor-pointer rounded-md border border-white/10 bg-white/5 text-sm file:mr-4 file:h-full file:border-0 file:bg-cyan file:px-4 file:font-semibold file:text-ink"
          />
          {imageError ? <span className="block text-xs text-rose-200">{imageError}</span> : null}
        </label>
      </div>

      <label className="space-y-2">
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <ImagePlus size={15} /> 个人形象素材
        </span>
        <input
          required
          type="file"
          name="personal_image"
          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
          onChange={(event) => validateImageFile(event, setPersonalImageError)}
          className="block h-11 w-full cursor-pointer rounded-md border border-white/10 bg-white/5 text-sm file:mr-4 file:h-full file:border-0 file:bg-cyan file:px-4 file:font-semibold file:text-ink"
        />
        {personalImageError ? <span className="block text-xs text-rose-200">{personalImageError}</span> : null}
      </label>

      <input type="hidden" name="avatar_id" value="heygen_custom" />
      {voiceCloneEnabled && voiceClones.length > 0 ? (
        <div className="rounded-md border border-cyan/20 bg-cyan/[0.06] p-3">
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" name="use_cloned_voice" value="true" />
            使用我的克隆声音
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
          升级到 Pro 解锁声音克隆，后续视频可直接使用你的专属 voice_id。
        </p>
      )}
      <VoiceUpload />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{state.message}</p>
          {!userEmail ? <p className="text-xs text-cyan">可以先填写和上传素材，点击生成时再登录，登录后回到工作台。</p> : null}
          {draftRestored ? <p className="text-xs text-lime">已恢复上次填写的工作台草稿。</p> : null}
          <p className="text-xs text-slate-500">
            {userEmail
              ? remainingQuota === null
                ? "Business 套餐：自定义额度"
                : `本月剩余 ${Math.max(remainingQuota ?? 0, 0)} 次生成`
              : "登录后可生成，每月免费 3 次。"}
          </p>
        </div>
        <SubmitButton label={userEmail ? "生成带货视频方案" : "登录并生成"} pendingLabel={userEmail ? "正在生成" : "正在跳转登录"} />
      </div>
      </Card>
    </form>
  );
}
