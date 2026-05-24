"use server";

import { redirect } from "next/navigation";

import { createPlaceholderOrder } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { ActionState } from "@/lib/types";

export async function createPlaceholderOrderAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/pricing");
  }

  try {
    const result = await createPlaceholderOrder(formData, session.access_token);
    return { ok: true, message: result.message };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "订单创建失败，请稍后重试。",
    };
  }
}
