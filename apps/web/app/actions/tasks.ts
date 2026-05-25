"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createVideoTask } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { ActionState } from "@/lib/types";

export async function submitTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/studio");
  }

  formData.set("user_email", session.user.email ?? "");

  try {
    await createVideoTask(formData, session.access_token);
    revalidatePath("/tasks");
    revalidatePath("/account");
    return { ok: true, message: "AI 带货方案已生成，管理员制作后可在任务页下载视频。" };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "提交失败，请检查后端服务和环境变量。",
    };
  }
}
