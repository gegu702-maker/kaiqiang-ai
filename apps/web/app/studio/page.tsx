import { StudioWorkspace } from "@/components/StudioWorkspace";
import { getUsageSummary, getVoiceClones } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { VoiceClone } from "@/lib/types";

export default async function StudioPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  let remainingQuota: number | null | undefined = undefined;
  let quotaLoadFailed = false;
  let voiceCloneEnabled = false;
  let voiceClones: VoiceClone[] = [];

  if (session?.access_token) {
    try {
      const usage = await getUsageSummary(session.access_token);
      remainingQuota = usage?.remaining ?? 3;
      voiceCloneEnabled = Boolean(usage?.voice_clone_enabled);
    } catch (err) {
      console.error("[StudioPage] usage fallback", err);
      remainingQuota = 3;
      quotaLoadFailed = true;
    }
    try {
      voiceClones = await getVoiceClones(session.access_token);
    } catch (err) {
      console.error("[StudioPage] voice clones failed", err);
    }
  }

  return (
    <StudioWorkspace
      userEmail={session?.user.email}
      remainingQuota={remainingQuota}
      quotaLoadFailed={quotaLoadFailed}
      voiceCloneEnabled={voiceCloneEnabled}
      voiceClones={voiceClones}
    />
  );
}
