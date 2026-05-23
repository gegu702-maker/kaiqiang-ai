"use client";

import { useActionState } from "react";
import { ExternalLink, Save } from "lucide-react";

import { updateTaskAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { VideoTask } from "@/lib/types";

const initialState = { ok: false, message: "" };

export function HeyGenProductionForm({ task }: { task: VideoTask }) {
  const [state, action] = useActionState(updateTaskAction, initialState);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <Save size={17} />
            HeyGen 生产记录
          </CardTitle>
          <Button asChild variant="outline" size="sm">
            <a href="https://app.heygen.com/" target="_blank" rel="noreferrer">
              <ExternalLink size={15} />
              打开 HeyGen
            </a>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <form action={action} className="space-y-4">
          <input type="hidden" name="task_id" value={task.id} />
          <div className="grid gap-3 sm:grid-cols-2">
            <StudioInput label="HeyGen avatar_id" name="heygen_avatar_id" defaultValue={task.heygen_avatar_id} />
            <StudioInput label="HeyGen voice_id" name="heygen_voice_id" defaultValue={task.heygen_voice_id} />
            <StudioInput label="HeyGen video_id" name="heygen_video_id" defaultValue={task.heygen_video_id} />
            <StudioInput label="HeyGen video_url" name="heygen_video_url" defaultValue={task.heygen_video_url} />
          </div>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-200">处理备注</span>
            <textarea
              name="admin_notes"
              defaultValue={task.admin_notes}
              rows={6}
              placeholder="记录 HeyGen 角色、声音选择、提示词、失败原因、待补素材..."
              className="w-full resize-none rounded-md border border-white/10 bg-white/5 px-3 py-3 text-sm leading-6 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
            />
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{state.message}</p>
            <SubmitButton label="保存 HeyGen 信息" pendingLabel="保存中" />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function StudioInput({
  defaultValue,
  label,
  name,
}: {
  defaultValue: string;
  label: string;
  name: string;
}) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-200">{label}</span>
      <input
        name={name}
        defaultValue={defaultValue}
        placeholder={label}
        className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 text-sm outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
      />
    </label>
  );
}
