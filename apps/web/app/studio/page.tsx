import { StudioWorkspace } from "@/components/StudioWorkspace";
import { getUsageSummary, getVoiceClones } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

export default async function StudioPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const accessToken = session?.access_token;
  const [usageSummary, voiceClones] = await Promise.all([
    getUsageSummary(accessToken).catch(() => null),
    getVoiceClones(accessToken).catch(() => []),
  ]);

  return (
    <StudioWorkspace
      userEmail={session?.user.email}
      remainingQuota={usageSummary?.remaining}
      quotaLoadFailed={Boolean(accessToken && !usageSummary)}
      voiceCloneEnabled={Boolean(usageSummary?.voice_clone_enabled)}
      voiceClones={voiceClones}
    />
  );
}
