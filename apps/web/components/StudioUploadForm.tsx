"use client";

import { ChangeEvent, useActionState, useState } from "react";
import { CheckCircle2, UploadCloud } from "lucide-react";

import { updateTaskAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { VideoTask } from "@/lib/types";

const initialState = { ok: false, message: "" };
const MAX_VIDEO_BYTES = 200 * 1024 * 1024;

export function StudioUploadForm({ task }: { task: VideoTask }) {
  const [state, action] = useActionState(updateTaskAction, initialState);
  const [fileName, setFileName] = useState("");
  const [clientError, setClientError] = useState("");

  function validateVideo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setClientError("");
    setFileName("");
    if (!file) return;

    if (file.type !== "video/mp4" && !file.name.toLowerCase().endsWith(".mp4")) {
      setClientError("只支持上传 mp4 视频。");
      event.target.value = "";
      return;
    }

    if (file.size > MAX_VIDEO_BYTES) {
      setClientError("视频最大支持 200MB。");
      event.target.value = "";
      return;
    }

    setFileName(file.name);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UploadCloud size={17} />
          最终视频上传
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form action={action} className="space-y-4">
          <input type="hidden" name="task_id" value={task.id} />
          <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-white/15 bg-white/[0.04] px-4 py-6 text-center transition hover:border-cyan/40 hover:bg-cyan/5">
            <span className="grid size-11 place-items-center rounded-lg bg-cyan/10 text-cyan">
              <UploadCloud size={20} />
            </span>
            <span className="text-sm font-medium text-white">{fileName || "选择最终 MP4 文件"}</span>
            <span className="text-xs text-slate-500">上传后自动写入 URL，并将状态更新为 completed</span>
            <input name="result_video" type="file" accept="video/mp4,.mp4" onChange={validateVideo} className="sr-only" />
          </label>
          {clientError ? <p className="text-sm text-rose-200">{clientError}</p> : null}
          {task.result_video_url ? (
            <p className="flex items-center gap-2 text-sm text-lime">
              <CheckCircle2 size={16} />
              当前已有最终视频，可重新上传覆盖 URL。
            </p>
          ) : null}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{state.message}</p>
            <SubmitButton label="上传并完成任务" pendingLabel="上传中" />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
