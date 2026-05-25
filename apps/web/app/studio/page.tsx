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
  let voiceCloneEnabled = false;
  let voiceClones: VoiceClone[] = [];

  if (session?.access_token) {
    try {
      const usage = await getUsageSummary(session.access_token);
      remainingQuota = usage?.remaining ?? null;
      voiceCloneEnabled = Boolean(usage?.voice_clone_enabled);
      voiceClones = await getVoiceClones(session.access_token);
    } catch {
      remainingQuota = undefined;
    }
  }

  return <StudioWorkspace userEmail={session?.user.email} remainingQuota={remainingQuota} voiceCloneEnabled={voiceCloneEnabled} voiceClones={voiceClones} />;
}
