"use server";

import { revalidatePath } from "next/cache";

import { cloneVoice, updateAdminTask } from "@/lib/api";
import type { ActionState } from "@/lib/types";

export async function updateTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const taskId = String(formData.get("task_id") ?? "");
  formData.delete("task_id");

  try {
    await updateAdminTask(taskId, formData);
    revalidatePath("/admin");
    revalidatePath(`/admin/tasks/${taskId}`);
    revalidatePath(`/admin/studio/${taskId}`);
    revalidatePath(`/tasks/${taskId}`);
    revalidatePath("/tasks");
    return { ok: true, message: "任务已更新。" };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "更新失败，请检查管理员密钥和后端服务。",
    };
  }
}

export async function cloneVoiceAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const taskId = String(formData.get("task_id") ?? "");

  try {
    const result = await cloneVoice(formData);
    revalidatePath("/admin");
    revalidatePath(`/admin/tasks/${taskId}`);
    revalidatePath(`/admin/studio/${taskId}`);
    revalidatePath(`/tasks/${taskId}`);
    return {
      ok: true,
      message: "Clone voice 已生成并上传。",
      audioUrl: result.audio_url,
      cosyvoiceStatus: "completed",
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Clone voice 生成失败，请检查 CosyVoice 服务。",
      cosyvoiceStatus: "failed",
    };
  }
}
