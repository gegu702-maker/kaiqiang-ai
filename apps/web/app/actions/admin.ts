"use server";

import { revalidatePath } from "next/cache";

import { cloneVoice, markAdminOrderPaid, retryAdminTask, updateAdminTask, updateAdminUser } from "@/lib/api";
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

export async function updateAdminUserAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const userId = String(formData.get("user_id") ?? "");
  formData.delete("user_id");
  for (const key of Array.from(formData.keys())) {
    if (String(formData.get(key) ?? "") === "") {
      formData.delete(key);
    }
  }

  try {
    await updateAdminUser(userId, formData);
    revalidatePath("/admin/billing");
    return { ok: true, message: "用户额度已更新。" };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "用户更新失败。",
    };
  }
}

export async function markOrderPaidAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const orderId = String(formData.get("order_id") ?? "");
  formData.delete("order_id");

  try {
    await markAdminOrderPaid(orderId, formData);
    revalidatePath("/admin/billing");
    return { ok: true, message: "订单已标记支付，并已升级套餐。" };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "订单处理失败。",
    };
  }
}

export async function retryAdminTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const taskId = String(formData.get("task_id") ?? "");
  try {
    await retryAdminTask(taskId);
    revalidatePath("/admin");
    revalidatePath(`/admin/tasks/${taskId}`);
    return { ok: true, message: "任务已重新进入队列。" };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : "重试失败。" };
  }
}
