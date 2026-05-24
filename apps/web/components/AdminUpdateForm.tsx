"use client";

import { ChangeEvent, useActionState, useState } from "react";
import { Upload } from "lucide-react";

import { updateTaskAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import type { VideoTask } from "@/lib/types";
import { cn } from "@/lib/utils";

const initialState = { ok: false, message: "" };
const statusStyles = {
  waiting: "border-amber-300/30 bg-amber-300/10 text-amber-100",
  generating_script: "border-fuchsia-300/30 bg-fuchsia-300/10 text-fuchsia-100",
  generating_voice: "border-blue-300/30 bg-blue-300/10 text-blue-100",
  generating_avatar: "border-violet-300/30 bg-violet-300/10 text-violet-100",
  rendering: "border-cyan/30 bg-cyan/10 text-cyan",
  success: "border-lime/30 bg-lime/10 text-lime",
  pending: "border-amber-300/30 bg-amber-300/10 text-amber-100",
  scripting: "border-fuchsia-300/30 bg-fuchsia-300/10 text-fuchsia-100",
  producing: "border-cyan/30 bg-cyan/10 text-cyan",
  processing: "border-cyan/30 bg-cyan/10 text-cyan",
  completed: "border-lime/30 bg-lime/10 text-lime",
  failed: "border-rose-300/30 bg-rose-400/10 text-rose-100",
};
const MAX_VIDEO_BYTES = 200 * 1024 * 1024;

export function AdminUpdateForm({ task }: { task: VideoTask }) {
  const [state, action] = useActionState(updateTaskAction, initialState);
  const [status, setStatus] = useState(task.status);
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
    <form action={action} className="grid gap-3 md:grid-cols-[160px_1fr_auto]">
      <input type="hidden" name="task_id" value={task.id} />
      <select
        name="status"
        value={status}
        onChange={(event) => setStatus(event.target.value as VideoTask["status"])}
        className={cn("h-10 rounded-md border px-3 text-sm outline-none ring-cyan/40 focus:ring-2", statusStyles[status])}
      >
        <option value="waiting">waiting</option>
        <option value="generating_script">generating_script</option>
        <option value="generating_voice">generating_voice</option>
        <option value="generating_avatar">generating_avatar</option>
        <option value="rendering">rendering</option>
        <option value="success">success</option>
        <option value="pending">pending</option>
        <option value="scripting">scripting</option>
        <option value="producing">producing</option>
        <option value="completed">completed</option>
        <option value="failed">failed</option>
      </select>
      <label className="flex h-10 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-slate-300">
        <Upload size={15} />
        <input name="result_video" type="file" accept="video/mp4,.mp4" onChange={validateVideo} className="min-w-0 text-xs" />
      </label>
      <SubmitButton label="更新" pendingLabel="更新中" />
      {clientError ? <p className="text-sm text-rose-200 md:col-span-3">{clientError}</p> : null}
      {state.message ? (
        <p className={state.ok ? "text-sm text-lime md:col-span-3" : "text-sm text-rose-200 md:col-span-3"}>
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
