"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { deleteTask, retryTask } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { ActionState } from "@/lib/types";

export async function deleteTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const taskId = String(formData.get("task_id") ?? "");
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) redirect("/login?next=/tasks");
  try {
    await deleteTask(taskId, session.access_token);
    revalidatePath("/tasks");
    revalidatePath("/account");
    return { ok: true, message: "任务已删除。" };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : "删除失败。" };
  }
}

export async function retryTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const taskId = String(formData.get("task_id") ?? "");
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) redirect("/login?next=/tasks");
  try {
    await retryTask(taskId, session.access_token);
    revalidatePath("/tasks");
    revalidatePath(`/tasks/${taskId}`);
    return { ok: true, message: "任务已重新进入队列。" };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : "重试失败。" };
  }
}
