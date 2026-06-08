import { StudioWorkspace } from "@/components/StudioWorkspace";
import { getDebugConfig, getUsageSummary, getVoiceClones } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

export default async function StudioPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const accessToken = session?.access_token;
  const [usageSummary, voiceClones, debugConfig] = await Promise.all([
    getUsageSummary(accessToken).catch(() => null),
    getVoiceClones(accessToken).catch(() => []),
    getDebugConfig().catch(() => ({
      avatar_motion_provider: undefined,
      liveportrait_api_configured: false,
      replicate_api_configured: false,
    })),
  ]);

  return (
    <StudioWorkspace
      userEmail={session?.user.email}
      remainingQuota={usageSummary?.remaining}
      quotaLoadFailed={Boolean(accessToken && !usageSummary)}
      voiceCloneEnabled={Boolean(usageSummary?.voice_clone_enabled)}
      voiceClones={voiceClones}
      livePortraitEnabled={
        (debugConfig.avatar_motion_provider === "liveportrait" && Boolean(debugConfig.liveportrait_api_configured)) ||
        (debugConfig.avatar_motion_provider === "replicate" && Boolean(debugConfig.replicate_api_configured))
      }
    />
  );
}
