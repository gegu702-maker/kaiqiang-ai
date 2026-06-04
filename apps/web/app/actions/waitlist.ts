"use server";

import type { ActionState } from "@/lib/types";
import { createClient } from "@/lib/supabase/server";

export async function joinWaitlistAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const industry = String(formData.get("industry") ?? "").trim();
  const useCase = String(formData.get("use_case") ?? "").trim();
  const locale = String(formData.get("locale") ?? "zh");

  if (!email || !industry || !useCase) {
    return {
      ok: false,
      message: locale === "en" ? "Please complete all fields." : "请填写完整信息。",
    };
  }

  const supabase = await createClient();
  const { error } = await supabase.from("waitlist").insert({
    email,
    industry,
    use_case: useCase,
  });

  if (error) {
    return {
      ok: false,
      message: error.message,
    };
  }

  return {
    ok: true,
    message: locale === "en" ? "Successfully joined the waitlist." : "已加入等待名单。",
  };
}
