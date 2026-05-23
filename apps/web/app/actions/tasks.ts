"use server";

import { revalidatePath } from "next/cache";

import { createVideoTask } from "@/lib/api";
import type { ActionState } from "@/lib/types";

export async function submitTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  try {
    await createVideoTask(formData);
    revalidatePath("/tasks");
    return { ok: true, message: "AI 带货方案已生成，管理员制作后可在任务页下载视频。" };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "提交失败，请检查后端服务和环境变量。",
    };
  }
}
