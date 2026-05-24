"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createVoiceClone, deleteVoiceClone, uploadVoiceClone } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { ActionState } from "@/lib/types";

export async function uploadVoiceCloneAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) redirect("/login?next=/account");

  try {
    const uploaded = await uploadVoiceClone(formData, session.access_token);
    const createForm = new FormData();
    createForm.set("voice_clone_id", uploaded.id);
    await createVoiceClone(createForm, session.access_token);
    revalidatePath("/account");
    return { ok: true, message: "声音克隆已创建，可在视频任务中使用。" };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : "声音克隆创建失败。" };
  }
}

export async function deleteVoiceCloneAction(
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) redirect("/login?next=/account");

  try {
    await deleteVoiceClone(String(formData.get("voice_clone_id") ?? ""), session.access_token);
    revalidatePath("/account");
    return { ok: true, message: "声音已删除。" };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : "删除失败。" };
  }
}
