"use client";

import { useActionState } from "react";
import { Save } from "lucide-react";

import { updateTaskAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { VideoTask } from "@/lib/types";

const initialState = { ok: false, message: "" };

export function StudioNotesForm({ task }: { task: VideoTask }) {
  const [state, action] = useActionState(updateTaskAction, initialState);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Save size={17} />
          管理员备注
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form action={action} className="space-y-3">
          <input type="hidden" name="task_id" value={task.id} />
          <textarea
            name="admin_notes"
            defaultValue={task.admin_notes}
            rows={7}
            placeholder="记录海螺 prompt、视频风格、镜头要求、问题备注..."
            className="w-full resize-none rounded-md border border-white/10 bg-white/5 px-3 py-3 text-sm leading-6 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className={state.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{state.message}</p>
            <SubmitButton label="保存备注" pendingLabel="保存中" />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
