"use client";

import { useActionState } from "react";
import { RefreshCw } from "lucide-react";

import { retryAdminTaskAction } from "@/app/actions/admin";

const initialState = { ok: false, message: "" };

export function AdminTaskRetryForm({ taskId }: { taskId: string }) {
  const [state, action] = useActionState(retryAdminTaskAction, initialState);

  return (
    <form action={action} className="space-y-2">
      <input type="hidden" name="task_id" value={taskId} />
      <button className="inline-flex items-center gap-2 rounded-md border border-cyan/30 px-3 py-2 text-sm text-cyan hover:bg-cyan/10">
        <RefreshCw size={15} />
        重试生成
      </button>
      {state.message ? <p className={state.ok ? "text-xs text-lime" : "text-xs text-rose-200"}>{state.message}</p> : null}
    </form>
  );
}
