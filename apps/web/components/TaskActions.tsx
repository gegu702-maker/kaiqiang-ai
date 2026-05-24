"use client";

import { useActionState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";

import { deleteTaskAction, retryTaskAction } from "@/app/actions/userTasks";

const initialState = { ok: false, message: "" };

export function TaskActions({ taskId }: { taskId: string }) {
  const [deleteState, deleteAction] = useActionState(deleteTaskAction, initialState);
  const [retryState, retryAction] = useActionState(retryTaskAction, initialState);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <form action={retryAction}>
        <input type="hidden" name="task_id" value={taskId} />
        <button className="inline-flex items-center gap-1.5 rounded-md border border-cyan/30 px-3 py-2 text-xs text-cyan hover:bg-cyan/10">
          <RefreshCw size={14} />
          重新生成
        </button>
      </form>
      <form action={deleteAction}>
        <input type="hidden" name="task_id" value={taskId} />
        <button className="inline-flex items-center gap-1.5 rounded-md border border-rose-300/30 px-3 py-2 text-xs text-rose-100 hover:bg-rose-400/10">
          <Trash2 size={14} />
          删除
        </button>
      </form>
      {(deleteState.message || retryState.message) ? (
        <p className={deleteState.ok || retryState.ok ? "text-xs text-lime" : "text-xs text-rose-200"}>
          {deleteState.message || retryState.message}
        </p>
      ) : null}
    </div>
  );
}
