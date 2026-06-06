"use client";

import { ChangeEvent, useActionState, useState } from "react";
import { ChevronDown, Upload } from "lucide-react";

import { updateTaskAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import { StatusBadge, statusLabels } from "@/components/StatusBadge";
import type { VideoTask } from "@/lib/types";

const initialState = { ok: false, message: "" };
const MAX_VIDEO_BYTES = 200 * 1024 * 1024;
const statusOptions: VideoTask["status"][] = [
  "waiting",
  "generating_script",
  "cloning_voice",
  "generating_voice",
  "generating_avatar",
  "rendering",
  "success",
  "completed",
  "failed",
];

export function AdminUpdateForm({ task }: { task: VideoTask }) {
  const [state, action] = useActionState(updateTaskAction, initialState);
  const [status, setStatus] = useState(task.status);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [clientError, setClientError] = useState("");

  function validateVideo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setClientError("");
    if (!file) return;

    if (file.type !== "video/mp4" && !file.name.toLowerCase().endsWith(".mp4")) {
      setClientError("只支持上传 mp4 视频。");
      event.target.value = "";
      return;
    }

    if (file.size > MAX_VIDEO_BYTES) {
      setClientError("视频最大支持 200MB。");
      event.target.value = "";
    }
  }

  return (
    <form action={action} className="grid gap-3">
      <input type="hidden" name="task_id" value={task.id} />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] p-3">
        <div>
          <p className="text-xs text-slate-500">当前状态</p>
          <div className="mt-2">
            <StatusBadge status={task.status} />
          </div>
        </div>
        <p className="text-xs leading-5 text-slate-500">默认只读，避免误操作。</p>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_auto]">
        <label className="flex min-h-10 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300">
          <Upload size={15} />
          <input name="result_video" type="file" accept="video/mp4,.mp4" onChange={validateVideo} className="min-w-0 text-xs text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-cyan file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-ink hover:file:bg-cyan/90" />
        </label>
        <SubmitButton label="更新视频" pendingLabel="更新中" />
      </div>

      <details
        className="rounded-md border border-amber-300/20 bg-amber-300/[0.035] p-3"
        onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
      >
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-amber-100">
          高级操作
          <ChevronDown size={16} className={advancedOpen ? "rotate-180 transition" : "transition"} />
        </summary>
        <div className="mt-3 grid gap-3 md:grid-cols-[180px_1fr]">
          <label className="grid gap-2 text-xs font-medium text-slate-400">
            手动状态
            <select
              name="status"
              value={status}
              disabled={!advancedOpen}
              onChange={(event) => setStatus(event.target.value as VideoTask["status"])}
              className="h-10 rounded-md border border-white/10 bg-slate-950 px-3 text-sm text-slate-100 outline-none ring-cyan/40 focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {statusOptions.map((option) => (
                <option key={option} value={option} className="bg-slate-950 text-slate-100">
                  {statusLabels[option]}
                </option>
              ))}
            </select>
          </label>
          <p className="self-end text-xs leading-5 text-slate-500">
            仅在任务异常排查或人工补录结果时使用。展开后提交会同步修改任务状态。
          </p>
        </div>
      </details>

      {clientError ? <p className="text-sm text-rose-200">{clientError}</p> : null}
      {state.message ? (
        <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
