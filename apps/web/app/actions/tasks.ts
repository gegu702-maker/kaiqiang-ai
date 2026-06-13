"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createVideoTask } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { ActionState } from "@/lib/types";

const SERVER_SUPPORTED_LOCALES = new Set(["zh", "en", "ja", "ko", "es", "fr", "ru"]);

export async function submitTaskAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const rawLocale = String(formData.get("ui_locale") ?? "zh");
  const locale = SERVER_SUPPORTED_LOCALES.has(rawLocale) ? rawLocale : "zh";
  const messageLocale = locale === "zh" ? "zh" : "en";
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
    return {
      ok: true,
      message: messageLocale === "en" ? "Your AI product video workflow has been generated. Download the final video from Tasks after delivery." : "AI 带货方案已生成，管理员制作后可在任务页下载视频。",
    };
  } catch (error) {
    console.error("[submitTaskAction] task submission failed", {
      message: error instanceof Error ? error.message : String(error),
      formKeys: Array.from(formData.keys()),
    });
    return {
      ok: false,
      message: error instanceof Error ? error.message : messageLocale === "en" ? "Submission failed. Please check the backend service and environment variables." : "提交失败，请检查后端服务和环境变量。",
    };
  }
}
