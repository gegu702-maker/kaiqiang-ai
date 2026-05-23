"use client";

import { ChangeEvent, useActionState, useState } from "react";
import { ImagePlus, Mail, Package, ScrollText, Target, Video } from "lucide-react";

import { submitTaskAction } from "@/app/actions/tasks";
import { SubmitButton } from "@/components/SubmitButton";
import { VoiceUpload } from "@/components/VoiceUpload";
import { Card } from "@/components/ui/card";

const initialState = { ok: false, message: "" };
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

export function TaskForm() {
  const [state, action] = useActionState(submitTaskAction, initialState);
  const [imageError, setImageError] = useState("");
  const [personalImageError, setPersonalImageError] = useState("");

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
            required
            type="email"
            name="user_email"
            placeholder="you@company.com"
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
      <VoiceUpload />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{state.message}</p>
        <SubmitButton label="生成带货视频方案" pendingLabel="正在生成" />
      </div>
      </Card>
    </form>
  );
}
